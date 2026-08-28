from __future__ import annotations

import uuid
import json
import logging
import random
import time
from pathlib import Path
from typing import Optional, Callable

from google import genai
from google.genai import errors as genai_errors

from tools import TOOL_DEFINITIONS, TOOLS

from .cache import PromptCache
from .config import (
    DEFAULT_CACHE_PATH,
    DEFAULT_MODEL,
    DEFAULT_TRACE_LOG_PATH,
    DEFAULT_USAGE_LOG_PATH,
    RETRYABLE_ERRORS,
)
from .model_routing import all_terminal
from .models import GeminiResponse

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

# Tools cujo retorno pode conter um arquivo gerado (ex: PNG de gráfico) a ser propagado até quem consome o GeminiResponse (ex: gemini_terminal.py decide se mantém ou descarta o arquivo).
PLOT_TOOL_NAMES = {"plot_sheet_data", "plot_table_data"}


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
        max_retries: int = 3,
        use_cache: bool = True,
        cache_path: Path | str = DEFAULT_CACHE_PATH,
        fallback_models: Optional[list[str]] = None,
        cheap_model: Optional[str] = None,
    ):
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self.default_model = default_model
        self.cheap_model = cheap_model
        self.fallback_models = fallback_models or [
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
            "gemini-3-flash",
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]

        # gemini_usage_log.jsonl — 1 linha por generate() COMPLETO, com tokens agregados de todas as tentativas internas. Fonte de custo/consumo (alimenta session_summary()/`/tokens`). Ver _log_usage().
        self.usage_log_path = Path(usage_log_path)
        # interaction_trace_log.jsonl — 1 linha por TENTATIVA individual de chamada ao modelo dentro de _create_with_fallback (início e depois sucesso/erro), correlacionadas por call_id. Existe só para diagnóstico de latência/hang entre chamadas — NÃO é fonte de custo (isso é o usage log acima) e é sempre gravado, independente do nível do logger (`/logs` oculto não afeta este arquivo). Ver _log_trace_attempt().
        self.trace_log_path = Path(trace_log_path)
        self.max_retries = max_retries
        self.cache = PromptCache(cache_path) if use_cache else None
        self._thought_callback: Optional[Callable[[str], None]] = None
        self.show_thoughts: bool = False

        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._session_calls = 0
        self._session_cache_hits = 0

        # Reiniciado a cada generate() — arquivos gerados por tools nesta chamada.
        self._current_generated_files: list[Path] = []
        self._created_files_this_session: set[Path] = set()

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

    def _execute_tool_call(self, step) -> object:
        tool_name = step.name
        arguments = step.arguments or {}

        logger.info("Gemini solicitou ferramenta '%s' com argumentos: %s", tool_name, arguments)

        if tool_name not in TOOLS:
            raise ValueError(
                f"Ferramenta '{tool_name}' não está registrada. "
                f"Disponíveis: {list(TOOLS)}"
            )

        function = TOOLS[tool_name]

        try:
            # run_script só pode executar arquivos criados nesta sessão através de create_file.
            if tool_name == "run_script":
                requested_path = Path(arguments.get("path", "")).resolve()

                if requested_path not in self._created_files_this_session:
                    return {
                        "error": (
                            "Execução bloqueada. Só é permitido executar scripts "
                            "criados nesta sessão através da ferramenta create_file."
                        )
                    }

            result = function(**arguments)

            logger.info("Ferramenta '%s' executada com sucesso.", tool_name)

            # Registra arquivos criados pelo create_file
            if (tool_name == "create_file" and isinstance(result, dict) and result.get("success") and result.get("file_path")):
                created_path = Path(result["file_path"]).resolve()

                self._created_files_this_session.add(created_path)

                logger.info(
                    "Arquivo criado nesta sessão registrado: %s",
                    created_path,
                )

            # Gerar arquivos de ferramentas de plotagem (ex: gráficos) para propagar no GeminiResponse.
            if (tool_name in PLOT_TOOL_NAMES and isinstance(result, dict) and result.get("file_path")):
                file_path = Path(result["file_path"])
                self._current_generated_files.append(file_path)

                logger.info("Arquivo gerado por '%s' registrado: %s", tool_name, file_path)

            return result

        except Exception as e:
            logger.exception("Erro ao executar ferramenta '%s'.", tool_name)
            return {"error": str(e)}

    def _is_rate_limit_error(self, error: Exception) -> bool:
        error_str = str(error).lower()
        return (
            "429" in error_str
            or "resources exhausted" in error_str
            or "resource_exhausted" in error_str
            or "rate limit" in error_str
            or "rate_limit" in error_str
        )

    def _create_interaction(
        self,
        *,
        model: str,
        input,
        tools=None,
        previous_interaction_id=None,
        system_instruction=None,
        generation_config=None,
        max_retries: int = 2,
    ):
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                create_kwargs = {
                    "model": model,
                    "input": input,
                    "tools": tools,
                    "previous_interaction_id": previous_interaction_id,
                }

                if system_instruction is not None:
                    create_kwargs["system_instruction"] = system_instruction
                if generation_config:
                    create_kwargs["generation_config"] = generation_config

                interaction = self.client.interactions.create(**create_kwargs)
                return interaction

            except Exception as error:
                last_error = error
                if not self._is_rate_limit_error(error):
                    raise
                if attempt >= max_retries:
                    raise

                delay = min(2 ** attempt, 10) + random.uniform(0, 0.5)
                print(
                    f"[Gemini] Modelo {model} atingiu limite. "
                    f"Tentativa {attempt + 1}/{max_retries}. "
                    f"Aguardando {delay:.2f}s..."
                )
                time.sleep(delay)

        raise last_error

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
        last_error = None
        models_to_try = []

        for candidate in [preferred_model, self.default_model, *self.fallback_models]:
            if candidate and candidate not in models_to_try:
                models_to_try.append(candidate)

        for model in models_to_try:
            if call_id:
                self._log_trace_attempt(call_id=call_id, stage=stage, model=model, phase="start")
            try:
                print(f"[Gemini] Tentando modelo: {model}")
                interaction = self._create_interaction(
                    model=model,
                    input=input,
                    tools=tools,
                    previous_interaction_id=previous_interaction_id,
                    system_instruction=system_instruction,
                    generation_config=generation_config,
                )
                print(f"[Gemini] Modelo utilizado: {model}")

                if call_id:
                    self._log_trace_attempt(call_id=call_id, stage=stage, model=model, phase="success")
                return interaction, model
            
            except Exception as error:
                last_error = error
                if call_id:
                    self._log_trace_attempt(call_id=call_id, stage=stage, model=model, phase="failure", error=str(error))
                if self._is_rate_limit_error(error):
                    print(
                        f"[Gemini] {model} indisponível por limite de uso. "
                        "Tentando próximo modelo..."
                    )
                    continue
                raise

        raise RuntimeError(
            "Todos os modelos configurados atingiram o limite de uso."
        ) from last_error

    def set_thought_callback(self, callback: Callable[[str], None]) -> None:
        """
        Registra um callback chamado a cada thought summary capturado durante
        generate(). Existe para permitir que a UI (ex: gemini_terminal.py) exiba o
        raciocínio do modelo em tempo real, sem acoplar esta camada a nenhuma
        biblioteca de terminal (mesmo padrão de confirm_action/set_confirm_callback).
        """
        self._thought_callback = callback

    def set_thinking_enabled(self, enabled: bool) -> None:
        """
        Liga/desliga o pedido de thought summaries nas próximas chamadas de 
        generate(). Desligado por padrão — aumenta latência e custo de tokens.
        """
        self.show_thoughts = enabled

    def count_tokens(self, prompt: str, model: Optional[str] = None) -> int:
        """Conta o número de tokens que seriam usados para gerar uma resposta."""
        model = model or self.default_model
        result = self.client.models.count_tokens(model=model, contents=prompt)
        return result.total_tokens

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
                    raw=None,
                )
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
            self._current_generated_files = []
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

                    logger.info("Gemini solicitou %d ferramenta(s).", len(function_calls))
                    function_results = []
                    tool_names_this_round = []

                    for step in function_calls:
                        result = self._execute_tool_call(step)
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
                    generated_files=list(self._current_generated_files),
                    thoughts=accumulated_thoughts,
                )

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
                raise

            except RETRYABLE_ERRORS as e:
                if attempt > self.max_retries:
                    logger.error(
                        "Excedeu %d tentativas. Desistindo. Último erro: %s",
                        self.max_retries,
                        e,
                    )
                    raise
                wait = 2 ** attempt
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
            raw=interaction,
        )

    def _log_trace_attempt(self, *, call_id: str, stage: str, model: str, phase: str, error: Optional[str] = None) -> None:
        """
        Grava uma tentativa individual de chamada ao modelo no trace log.
        stage identifica em qual ponto do fluxo de generate() a tentativa
        ocorreu: "initial", "tool_continuation", "cheap_synthesis" ou
        "strong_fallback". phase é "start", "success" ou "error".
        """
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "call_id": call_id,
            "stage": stage,
            "model": model,
            "phase": phase,
        }
        if error is not None:
            entry['error'] = error

        try:
            self.trace_log_path.parent.mkdir(parents = True, exist_ok = True)
            with open(self.trace_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii = False, default = str) + '\n')
        except OSError as e:
            logger.warning("Não consegui gravar o log de rastreio em %s: %s", self.trace_log_path, e)

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