from __future__ import annotations

import uuid
import json
import logging
import time
from pathlib import Path
from typing import Optional, Callable

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from tools import TOOL_DEFINITIONS, TOOL_POLICIES
from tools.confirmation import confirm_action

from .cache import PromptCache
from .config import (
    DEFAULT_API_CALL_TIMEOUT_SECONDS,
    MAX_TOOL_ROUNDS,
    MAX_TOOL_EXEC_SECONDS,
    DEFAULT_CACHE_PATH,
    DEFAULT_MODEL,
    DEFAULT_TRACE_LOG_PATH,
    DEFAULT_USAGE_LOG_PATH,
    DEFAULT_QUOTA_PATH,
    RETRYABLE_ERRORS,
)
from .exceptions import GeminiTimeoutError
from .model_routing import all_terminal
from .models import ActivityEvent, GeminiResponse
from .quota_tracker import QuotaTracker
from .activity import ActivityRecorder
from .model_gateway import ModelGateway, ModelRequest
from .tool_executor import ToolExecutor, ToolExecutionContext

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("gemini_client")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

class GeminiClient:
    """
    Wrapper sobre google.genai.Client com:
    - retry automático com backoff exponencial para erros transitórios do servidor
    - contagem/registro de uso de tokens (por chamada e acumulado na sessão)
    - log estruturado em arquivo (JSON Lines) para auditar gasto entre execuções
    - rastreamento de arquivos gerados por tools (ex: gráficos) durante uma chamada
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = DEFAULT_MODEL,
        usage_log_path: Path | str = DEFAULT_USAGE_LOG_PATH,
        trace_log_path: Path | str = DEFAULT_TRACE_LOG_PATH,
        quota_path: Path | str = DEFAULT_QUOTA_PATH,
        max_retries: int = 3,
        use_cache: bool = True,
        cache_path: Path | str = DEFAULT_CACHE_PATH,
        fallback_models: Optional[list[str]] = None,
        cheap_model: Optional[str] = None,
        api_client=None,
    ):
        sdk_client = api_client or (
            genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=DEFAULT_API_CALL_TIMEOUT_SECONDS * 1000  # HttpOptions é em ms
                ),
            )
            if api_key
            else genai.Client(
                http_options=types.HttpOptions(
                    timeout=DEFAULT_API_CALL_TIMEOUT_SECONDS * 1000
                )
            )
        )
        self.default_model = default_model
        self.cheap_model = cheap_model
        self.fallback_models = fallback_models or [
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3-flash",
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]

        # gemini_usage_log.jsonl — 1 linha por generate() COMPLETO, com tokens agregados de todas as tentativas internas. Fonte de custo/consumo (alimenta session_summary()/`/tokens`). Ver _log_usage().
        self.usage_log_path = Path(usage_log_path)
        # gemini_trace_log.jsonl — 1 linha por tentativa individual de chamada ao modelo, gravada pelo ActivityRecorder e correlacionada por call_id.
        self.quota = QuotaTracker(quota_path)
        self.max_retries = max_retries
        self.cache = PromptCache(cache_path) if use_cache else None
        self._thought_callback: Optional[Callable[[str], None]] = None
        self.activity_recorder = ActivityRecorder(trace_log_path)
        self.show_thoughts: bool = False

        self.model_gateway = ModelGateway(
            api_client=sdk_client,
            default_model=self.default_model,
            fallback_models=self.fallback_models,
            quota_tracker=self.quota,
            emit_activity=self._emit_activity,
            trace_attempt=self.activity_recorder.trace_model_attempt,
            confirm_quota_override=confirm_action,
            request_timeout=DEFAULT_API_CALL_TIMEOUT_SECONDS,
            sleep=time.sleep,
        )

        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._session_calls = 0
        self._session_cache_hits = 0

        self.tool_executor = ToolExecutor(
            policies = TOOL_POLICIES,
            emit_activity = self._emit_activity,
            default_timeout = MAX_TOOL_EXEC_SECONDS,
        )
        # context.created_files vive durante toda a sessão do client;
        # context.generated_files é reiniciado a cada tentativa dentro de
        # generate() (ver loop de retry abaixo) — mesmo objeto, ciclos de vida
        # diferentes por campo (ver docstring de ToolExecutionContext).
        self._tool_context = ToolExecutionContext()

    @property
    def client(self):
        """Compatibilidade temporária: cliente SDK utilizado pelo ModelGateway."""
        return self.model_gateway.api_client

    @client.setter
    def client(self, api_client) -> None:
        """Permite substituir o SDK sem criar uma referência divergente."""
        self.model_gateway.api_client = api_client

    @property
    def last_activities(self) -> list[ActivityEvent]:
        """Eventos emitidos durante a última chamada a generate() (delegado ao ActivityRecorder)."""
        return self.activity_recorder.last_activities

    @last_activities.setter
    def last_activities(self, activities: list[ActivityEvent]) -> None:
        """Mantém compatibilidade com consumidores que substituem a lista diretamente."""
        self.activity_recorder.last_activities = activities

    @property
    def trace_log_path(self) -> Path:
        """Caminho do trace, cuja fonte de verdade pertence ao ActivityRecorder."""
        return self.activity_recorder.trace_log_path

    @trace_log_path.setter
    def trace_log_path(self, path: Path | str) -> None:
        """Atualiza o destino utilizado pelo recorder para as próximas tentativas."""
        self.activity_recorder.trace_log_path = Path(path)

    def _emit_activity(self, event_type: str, message: str, **kwargs) -> ActivityEvent:
        """Wrapper sobre ActivityRecorder.emit — mantém as chamadas internas existentes sem alteração."""
        return self.activity_recorder.emit(event_type, message, **kwargs)

    def _process_thoughts(self, interaction) -> list[str]:
        """
        Extrai os thought summaries de uma interação (steps do tipo 'thought')
        e notifica o callback registrado, se houver. Retorna os textos capturados
        NESTA interação — quem chama é responsável por acumular entre rodadas.
        """
        thoughts = []

        for step in interaction.steps:
            if getattr(step, 'type', None) != 'thought':
                continue

            summary_blocks = getattr(step, 'summary', None) or []
            texts = [
                block.text
                for block in summary_blocks
                if getattr(block, "type", None) == "text" and getattr(block, "text", None)
            ]

            if not texts:
                continue

            thought_text = "\n".join(texts)
            thoughts.append(thought_text)
            if self._thought_callback:
                self._thought_callback(thought_text)
        return thoughts

    def _get_function_calls(self, interaction) -> list:
        """Retorna todas as chamadas de ferramentas presentes na interação."""
        return [
            step
            for step in interaction.steps
            if getattr(step, "type", None) == "function_call"
        ]

    def _create_with_fallback(
        self,
        *,
        input,
        tools=None,
        previous_interaction_id=None,
        preferred_model: Optional[str] = None,
        system_instruction=None,
        generation_config=None,
        call_id: Optional[str] = None,
        stage: str = 'unknown',
    ):
        result = self.model_gateway.create(
            ModelRequest(
                input=input,
                tools=tools,
                preferred_model=preferred_model,
                previous_interaction_id=previous_interaction_id,
                system_instruction=system_instruction,
                generation_config=generation_config,
                call_id=call_id,
                stage=stage,
            )
        )
        return result.interaction, result.model

    def set_thought_callback(self, callback: Callable[[str], None]) -> None:
        """
        Registra um callback chamado a cada thought summary capturado durante
        generate(). Existe para permitir que a UI (ex: gemini_terminal.py) exiba o
        raciocínio do modelo em tempo real, sem acoplar esta camada a nenhuma
        biblioteca de terminal (mesmo padrão de confirm_action/set_confirm_callback).
        """
        self._thought_callback = callback


    def set_activity_callback(self, callback: Optional[Callable[[ActivityEvent], None]]) -> None:
        """Registra o consumidor dos eventos operacionais de ``generate``."""
        self.activity_recorder.set_callback(callback)

    def set_thinking_enabled(self, enabled: bool) -> None:
        """
        Liga/desliga o pedido de thought summaries nas próximas chamadas de 
        generate(). Desligado por padrão — aumenta latência e custo de tokens.
        """
        self.show_thoughts = enabled

    def close(self, wait: bool = True) -> None:
        """Libera os recursos internos usados para execução de ferramentas."""
        self.tool_executor.close(wait=wait)

    def __enter__(self) -> "GeminiClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def count_tokens(self, prompt: str, model: Optional[str] = None) -> int:
        """Conta o número de tokens que seriam usados para gerar uma resposta."""
        return self.model_gateway.count_tokens(prompt, model)

    def generate(
        self,
        prompt: str,
        previous_interaction_id: Optional[str] = None,
        system: Optional[str] = None,
        model: Optional[str] = None,
        process_name: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_cache: Optional[bool] = None,
    ) -> GeminiResponse:
        generate_started_at = time.perf_counter()
        self.activity_recorder.reset()
        self._emit_activity("request_started", "Preparando solicitacao")
        if not prompt or not prompt.strip():
            raise ValueError("O prompt não pode ser vazio.")

        model = model or self.default_model
        cache_enabled = self.cache is not None and (use_cache if use_cache is not None else True)

        cache_key_params = dict(
            model=model,
            prompt=prompt,
            system=system,
            previous_interaction_id=previous_interaction_id,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        if cache_enabled:
            cached = self.cache.get(**cache_key_params)
            if cached is not None:
                self._session_cache_hits += 1
                logger.info(
                    "Cache hit para processo '%s' — nenhuma chamada de API feita.",
                    process_name or "avulso",
                )
                self._emit_activity("cache_hit", "Resposta recuperada do cache")
                response = GeminiResponse(
                    text=cached["text"],
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    model=cached.get("model", model),
                    interaction_id=cached.get("interaction_id"),
                    process_name=process_name,
                    api_calls=0,
                    generated_files=[],
                    activities=self.last_activities,
                    duration=time.perf_counter() - generate_started_at,
                    cached=True,
                    raw=None,
                )
                self._emit_activity(
                    "response_completed",
                    "Resposta concluida",
                    model=response.model,
                    duration=response.duration,
                )
                response.activities = list(self.last_activities)
                self._log_usage(response, cached=True)
                return response

        generation_config = {}
        if max_output_tokens is not None:
            generation_config["max_output_tokens"] = max_output_tokens
        if temperature is not None:
            generation_config["temperature"] = temperature
        if self.show_thoughts:
            generation_config["thinking_summaries"] = "auto"

        call_id = uuid.uuid4().hex[:12]
        attempt = 0
        while True:
            attempt += 1
            # Reinicia o rastreamento de arquivos gerados a cada tentativa — se essa tentativa falhar e for reexecutada, não queremos arrastar arquivos órfãos de uma tentativa anterior que não chegou a completar.
            self._tool_context.generated_files = []
            tool_rounds = 0
            tool_round_limit = MAX_TOOL_ROUNDS
            try:
                accumulated_input_tokens = 0
                accumulated_output_tokens = 0
                accumulated_total_tokens = 0
                api_calls_made = 0
                accumulated_thoughts: list[str] = []

                def _accumulate_usage(interaction) -> None:
                    nonlocal accumulated_input_tokens, accumulated_output_tokens
                    nonlocal accumulated_total_tokens, api_calls_made
                    usage = getattr(interaction, "usage", None)
                    accumulated_input_tokens += getattr(usage, "total_input_tokens", 0) or 0
                    accumulated_output_tokens += getattr(usage, "total_output_tokens", 0) or 0
                    accumulated_total_tokens += getattr(usage, "total_tokens", 0) or 0
                    api_calls_made += 1

                interaction, current_model = self._create_with_fallback(
                    input=prompt,
                    tools=TOOL_DEFINITIONS,
                    previous_interaction_id=previous_interaction_id,
                    preferred_model=model,
                    system_instruction=system,
                    generation_config=generation_config or None,
                    call_id=call_id,
                    stage="initial",
                )
                _accumulate_usage(interaction)
                accumulated_thoughts.extend(self._process_thoughts(interaction))

                while True:
                    function_calls = self._get_function_calls(interaction)
                    if not function_calls:
                        break

                    tool_rounds += 1
                    tool_round_limit = self._check_tool_round_budget(
                        tool_rounds=tool_rounds,
                        current_limit=tool_round_limit,
                    )

                    logger.info("Gemini solicitou %d ferramenta(s).", len(function_calls))
                    function_results = []
                    tool_names_this_round = []

                    for step in function_calls:
                        result = self.tool_executor.execute(step, self._tool_context)
                        tool_names_this_round.append(step.name)
                        function_results.append(
                            {
                                "type": "function_result",
                                "name": step.name,
                                "call_id": step.id,
                                "result": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(
                                            result,
                                            ensure_ascii=False,
                                            default=str,
                                        ),
                                    }
                                ],
                            }
                        )

                    # Roteamento multi-modelo: se TODAS as tools chamadas nesta rodada forem "terminais" (ver gemini/model_routing.py), a próxima chamada é candidata a rodar no modelo barato — o próximo passo esperado é sintetizar a resposta final, não decidir mais tool calls.
                    next_model_preference = current_model
                    used_cheap_model = False
                    if self.cheap_model and all_terminal(tool_names_this_round):
                        next_model_preference = self.cheap_model
                        used_cheap_model = True
                        self._emit_activity(
                            "synthesis_started",
                            f"Sintetizando resposta com {self.cheap_model}",
                            model=self.cheap_model,
                            stage="cheap_synthesis",
                        )

                    prior_interaction_id = interaction.id

                    interaction, current_model = self._create_with_fallback(
                        input=function_results,
                        tools=TOOL_DEFINITIONS,
                        previous_interaction_id=prior_interaction_id,
                        preferred_model=next_model_preference,
                        system_instruction=system,
                        stage="cheap_synthesis" if used_cheap_model else "tool_continuation",
                        call_id=call_id,
                    )
                    _accumulate_usage(interaction)
                    accumulated_thoughts.extend(self._process_thoughts(interaction))
                    # Rede de segurança: o modelo barato foi chamado pra sintetizar, mas pediu mais ferramentas em vez disso — a decisão de qual tool chamar não é confiável nesse modelo, então descarta essa resposta e refaz a MESMA rodada com o modelo forte, a partir do mesmo ponto da conversa (prior_interaction_id).
                    if used_cheap_model and self._get_function_calls(interaction):
                        logger.info(
                            "Modelo barato ('%s') pediu mais ferramentas em vez de "
                            "sintetizar; refazendo a rodada com o modelo forte.",
                            self.cheap_model,
                        )
                        interaction, current_model = self._create_with_fallback(
                            input=function_results,
                            tools=TOOL_DEFINITIONS,
                            previous_interaction_id=prior_interaction_id,
                            preferred_model=self.default_model,
                            system_instruction=system,
                            call_id=call_id,
                            stage="strong_fallback",
                        )
                        _accumulate_usage(interaction)
                        accumulated_thoughts.extend(self._process_thoughts(interaction))

                response = self._to_response(
                    interaction=interaction,
                    model=current_model,
                    process_name=process_name,
                    input_tokens=accumulated_input_tokens,
                    output_tokens=accumulated_output_tokens,
                    total_tokens=accumulated_total_tokens,
                    api_calls=api_calls_made,
                    generated_files=list(self._tool_context.generated_files),
                    thoughts=accumulated_thoughts,
                    duration=time.perf_counter() - generate_started_at,
                )

                self._emit_activity(
                    "response_completed",
                    "Resposta concluida",
                    model=response.model,
                    duration=response.duration,
                    details={
                        "api_calls": response.api_calls,
                        "total_tokens": response.total_tokens,
                    },
                )
                response.activities = list(self.last_activities)

                self._log_usage(response)

                if cache_enabled:
                    self.cache.set(
                        {
                            "text": response.text,
                            "model": response.model,
                            "interaction_id": response.interaction_id,
                        },
                        **cache_key_params,
                    )

                return response

            except genai_errors.ClientError as e:
                logger.error(f"Erro de cliente (não vou tentar de novo): {e}")
                self._emit_activity("request_failed", f"Solicitacao rejeitada: {e}")
                raise

            except RETRYABLE_ERRORS as e:
                if attempt > self.max_retries:
                    logger.error(
                        "Excedeu %d tentativas. Desistindo. Último erro: %s",
                        self.max_retries,
                        e,
                    )
                    self._emit_activity(
                        "request_failed",
                        f"Solicitacao falhou apos {attempt} tentativa(s): {e}",
                    )
                    raise
                wait = 2 ** attempt
                self._emit_activity(
                    "request_retrying",
                    f"Erro transitorio; nova tentativa em {wait}s",
                    details={"attempt": attempt, "wait_seconds": wait},
                )
                logger.warning(
                    "Erro transitório (tentativa %d/%d): %s. Aguardando %ds...",
                    attempt,
                    self.max_retries,
                    e,
                    wait,
                )
                time.sleep(wait)

    def _to_response(
        self,
        interaction,
        model: str,
        process_name: Optional[str],
        *,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        api_calls: int = 1,
        generated_files: Optional[list[Path]] = None,
        thoughts: Optional[list[str]] = None,
        duration: float = 0.0,
    ) -> GeminiResponse:
        return GeminiResponse(
            text=interaction.output_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=model,
            interaction_id=getattr(interaction, "id", None),
            process_name=process_name,
            api_calls=api_calls,
            generated_files=generated_files or [],
            thoughts=thoughts or [],
            activities=list(self.last_activities),
            duration=duration,
            raw=interaction,
        )

    def _check_tool_round_budget(self, *, tool_rounds: int, current_limit: int) -> int:
        """Impede loops de tools sem cronometrar ou interromper uma ferramenta."""
        if tool_rounds <= current_limit:
            return current_limit

        mensagem = (
            f"⚠ Esta resposta atingiu {tool_rounds} rodadas de ferramentas "
            f"(limite: {current_limit}).\n\nContinuar mesmo assim?"
        )
        self._emit_activity(
            "budget_exceeded",
            mensagem,
            details={"tool_rounds": tool_rounds, "tool_round_limit": current_limit},
        )

        if not confirm_action(mensagem):
            raise GeminiTimeoutError(
                f"Limite de {current_limit} rodadas de ferramentas excedido. "
                "Nenhuma nova tentativa automática será feita."
            )

        extended_limit = current_limit + MAX_TOOL_ROUNDS
        self._emit_activity(
            "budget_extended",
            f"Limite estendido pelo usuário para {extended_limit} rodadas",
            details={"tool_rounds": tool_rounds, "tool_round_limit": extended_limit},
        )
        return extended_limit

    def _log_usage(self, response: GeminiResponse, cached: bool = False) -> None:
        self._session_input_tokens += response.input_tokens
        self._session_output_tokens += response.output_tokens
        self._session_calls += response.api_calls

        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "process": response.process_name,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "api_calls": response.api_calls,
            "cached": cached,
        }
        try:
            with open(self.usage_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("Não consegui gravar o log de uso em %s: %s", self.usage_log_path, e)

    def session_summary(self) -> dict:
        return {
            "calls": self._session_calls,
            "cache_hits": self._session_cache_hits,
            "input_tokens": self._session_input_tokens,
            "output_tokens": self._session_output_tokens,
            "total_tokens": self._session_input_tokens + self._session_output_tokens,
        }


_PROCESS_REGISTRY: dict[str, dict] = {}


def register_process(name: str, system: str, model: Optional[str] = None) -> None:
    _PROCESS_REGISTRY[name] = {"system": system, "model": model}
    logger.info("Processo '%s' registrado com sucesso.", name)


def run_process(client: GeminiClient, name: str, prompt: str, **kwargs) -> GeminiResponse:
    if name not in _PROCESS_REGISTRY:
        raise KeyError(
            f"Processo '{name}' não encontrado. Disponíveis: {list(_PROCESS_REGISTRY)}"
        )
    process = _PROCESS_REGISTRY[name]
    return client.generate(
        prompt=prompt,
        system=process["system"],
        model=process.get("model"),
        process_name=name,
        **kwargs,
    )


def load_processes(path: Path | str = "processes.yaml") -> int:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de processos não encontrado: {path}")

    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as e:
            raise ImportError("Para carregar processos de YAML, instale: pip install pyyaml") from e
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Formato inválido em {path}: esperava um mapeamento nome -> config.")

    count = 0
    for name, cfg in data.items():
        if not isinstance(cfg, dict) or "system" not in cfg:
            logger.warning("Processo '%s' ignorado em %s: faltando campo 'system'.", name, path)
            continue
        register_process(name, system=cfg["system"], model=cfg.get("model"))
        count += 1

    logger.info("%d processo(s) carregado(s) de %s", count, path)
    return count


__all__ = [
    "GeminiClient",
    "register_process",
    "run_process",
    "load_processes",
]


if __name__ == "__main__":
    process_file = "processes.yaml" if Path("processes.yaml").exists() else "process.yaml"
    load_processes(process_file)

    client = GeminiClient()
    log_exemplo = """
    [2026-08-11 09:14:22] ERROR - Task 'fetch_ccee_data' failed.
    Traceback (most recent call last):
      File "consulta_consolidada.py", line 87, in <module>
        df['valor'] = df['valor'].astype(float)
    KeyError: 'valor'
    """

    resposta = run_process(client, "log_triage", log_exemplo)
    print(resposta.text)
    print("\nUso desta chamada:", resposta.total_tokens, "tokens")
    print("Resumo da sessão:", client.session_summary())
