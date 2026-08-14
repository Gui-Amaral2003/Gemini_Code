"""
Wrapper genérico e reutilizável em cima da API do Gemini (Interactions API),
pensado para uso em múltiplos processos de estudo/experimentação.

Uso básico:

    from gemini_client import GeminiClient, register_process, run_process

    client = GeminiClient()

    resp = client.generate("Explique o que é MS+7DU na CCEE, em uma frase.")
    print(resp.text)

Uso com processos nomeados (reutilizáveis entre scripts diferentes):

    register_process(
        "log_triage",
        system="Você é um assistente de triagem de logs de pipelines de dados. "
               "Responda em 3 partes: causa provável, tipo de erro "
               "(transitório/estrutural) e sugestão de correção.",
    )

    resp = run_process(client, "log_triage", log_exemplo)
    print(resp.text)

Uso com conversa (histórico gerenciado pelo servidor, via previous_interaction_id):

    session = ChatSession(client, system_instruction="Você é um tutor de SQL.")
    r1 = session.send("O que é uma CTE?")
    r2 = session.send("Me dá um exemplo com JOIN.")
"""
from __future__ import annotations
import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import time

from google import genai
import random
from google.genai import errors as genai_errors, types
from tools import TOOL_DEFINITIONS, TOOLS

try:
    from dotenv import load_dotenv
    load_dotenv()  # carrega variáveis de um arquivo .env no diretório atual, se existir
except ImportError:
    pass  # python-dotenv é opcional; sem ele, defina GEMINI_API_KEY no ambiente do jeito de sempre

# --------------------------------------------------------------------------- #
# Configuração de logging
# --------------------------------------------------------------------------- #
logger = logging.getLogger("gemini_client")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_USAGE_LOG_PATH = Path('gemini_usage_log.jsonl')
DEFAULT_CACHE_PATH = Path('gemini_cache.json')
DEFAULT_SESSIONS_PATH = Path('chat_sessions.json')

# Erros considerados transitórios (vale a pena tentar de novo).
# Erros de programação (TypeError, KeyError, etc.) NÃO entram aqui de propósito:
# tentar de novo não corrige um bug, só esconde o erro atrás de 3 tentativas lentas.
_RETRYABLE_ERRORS = (genai_errors.ServerError, ConnectionError, TimeoutError)


# --------------------------------------------------------------------------- #
# Tipos
# --------------------------------------------------------------------------- #
@dataclass
class GeminiResponse:
    """Resposta normalizada de uma chamada ao Gemini."""
    text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    process_name: Optional[str] = None
    interaction_id: Optional[str] = None
    raw: object = field(default=None, repr=False)

@dataclass
class Message:
    """Registro local de uma mensagem de uma conversa (só para exibição/histórico)."""
    role: str
    text: str


# --------------------------------------------------------------------------- #
# Cache de prompts
# --------------------------------------------------------------------------- #
class PromptCache:
    """
    Cache simples em disco (JSON) para respostas de prompts idênticos.
    Evita gastar chamada de novo quando você reexecuta o mesmo prompt —
    comum ao iterar em um system prompt e comparar resultado.

    A chave do cache inclui todos os parâmetros relevantes da chamada
    (model, system, prompt, previous_interaction_id, etc), então:
      - prompts em conversas (com previous_interaction_id) praticamente
        nunca repetem a chave, então nunca "colidem" indevidamente;
      - mudar o system prompt gera uma chave nova automaticamente.
    """

    def __init__(self, path: Path | str = DEFAULT_CACHE_PATH):
        self.path = Path(path)
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cache corrompido ou ilegível (%s). Começando vazio.", e)
            return {}

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("Não consegui salvar o cache em %s: %s", self.path, e)

    @staticmethod
    def _make_key(**kwargs) -> str:
        serialized = json.dumps(kwargs, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(self, **kwargs) -> Optional[dict]:
        return self._data.get(self._make_key(**kwargs))

    def set(self, value: dict, **kwargs) -> None:
        self._data[self._make_key(**kwargs)] = value
        self._save()

    def clear(self) -> None:
        self._data = {}
        self._save()

    def __len__(self) -> int:
        return len(self._data)


# --------------------------------------------------------------------------- #
# Cliente Gemini
# --------------------------------------------------------------------------- #
class GeminiClient:
    """
    Wrapper sobre google.genai.Client com:
     - retry automático com backoff exponencial para erros transitórios do servidor
     - contagem/registro de uso de tokens (por chamada e acumulado na sessão)
     - log estruturado em arquivo (JSON Lines) para auditar gasto entre execuções
    """
    def __init__(
            self,
            api_key: Optional[str] = None,
            default_model: str = DEFAULT_MODEL,
            usage_log_path: Path | str = DEFAULT_USAGE_LOG_PATH,
            max_retries: int = 3,
            use_cache: bool = True,
            cache_path: Path | str = DEFAULT_CACHE_PATH,
            fallback_models: Optional[list[str]] = None
    ):
        # NUNCA hardcode a chave aqui. Deixe None para o SDK ler de
        # GEMINI_API_KEY no ambiente (via .env ou export), ou passe
        # explicitamente na hora de instanciar.
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self.default_model = default_model
        self.fallback_models = fallback_models or ['gemini-3.6-flash', 'gemini-3.5-flash-lite', 'gemini-3-flash', 'gemini-3.1-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
        self.usage_log_path = Path(usage_log_path)
        self.max_retries = max_retries
        self.cache = PromptCache(cache_path) if use_cache else None

        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._session_calls = 0
        self._session_cache_hits = 0

    # --------------------------------------------------------------------------- #
    # Ferramentas (tools) que o Gemini pode chamar
    # --------------------------------------------------------------------------- #
    def _get_function_calls(self, interaction) -> list:
        """Retorna todas as chamadas de ferramentas presentes na interação."""

        return [
            step
            for step in interaction.steps
            if getattr(step, "type", None) == "function_call"
        ]
    
    def _execute_tool_call(self, step) -> object:
        """
        Executa uma ferramenta solicitada pelo Gemini.

        Parameters
        ----------
        step:
            Etapa function_call retornada pela Interactions API.
        """

        tool_name = step.name
        arguments = step.arguments or {}

        logger.info(
            "Gemini solicitou ferramenta '%s' com argumentos: %s",
            tool_name,
            arguments,
        )

        if tool_name not in TOOLS:
            raise ValueError(
                f"Ferramenta '{tool_name}' não está registrada. "
                f"Disponíveis: {list(TOOLS)}"
            )

        function = TOOLS[tool_name]

        try:
            result = function(**arguments)

            logger.info(
                "Ferramenta '%s' executada com sucesso.",
                tool_name,
            )

            return result

        except Exception as e:
            logger.exception(
                "Erro ao executar ferramenta '%s'.",
                tool_name,
            )

            return {
                "error": str(e)
            }

    # --------------------------------------------------------------------------- #
    # Troca de modelo em caso de estouro de uso
    # --------------------------------------------------------------------------- #
    def _is_rate_limit_error(self, error: Exception) -> bool:
        error_str = str(error).lower()

        return (
            '429' in error_str or
            'resources exhausted' in error_str or
            'resource_exhausted' in error_str or
            'rate limit' in error_str or 
            'rate_limit' in error_str
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
        """
        Cria uma Interaction com retry para erros transitórios.

        Retorna:
            interaction

        Levanta:
            Exception quando todas as tentativas do modelo falharem.
        """

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

                # Exponential backoff + jitter
                delay = min(
                    2 ** attempt,
                    10,
                ) + random.uniform(0, 0.5)

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
    ):
        """
        Tenta criar uma Interaction usando os modelos configurados.

        O fallback acontece somente para erros de rate limit (429).
        """

        last_error = None

        models_to_try = []

        for candidate in [preferred_model, self.default_model, *self.fallback_models]:
            if candidate and candidate not in models_to_try:
                models_to_try.append(candidate)

        for model in models_to_try:

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

                return interaction, model

            except Exception as error:

                last_error = error

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
    
    # --------------------------------------------------------------------------- #
    # Contagem de tokens (no caso do Gemini, gratuita)
    # --------------------------------------------------------------------------- #
    def count_tokens(self, prompt: str, model: Optional[str] = None) -> int:
        """Conta o número de tokens que seriam usados para gerar uma resposta."""
        model = model or self.default_model
        result = self.client.models.count_tokens(model=model, contents=prompt)
        return result.total_tokens

    # --------------------------------------------------------------------------- #
    # Geração de texto
    # --------------------------------------------------------------------------- #
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
        """
        Faz uma chamada de geração com retry automático em erros transitórios
        (5xx / instabilidade de rede). Erros de cliente (prompt inválido, chave
        errada, etc.) não são retentados — falham na hora.

        Para conversas com histórico, passe `previous_interaction_id` (vindo de
        uma GeminiResponse anterior) em vez de remontar o histórico na mão — é
        o padrão suportado pela Interactions API e evita reenviar tudo a cada
        chamada. Veja a classe ChatSession, que já faz esse controle.

        `use_cache`: None segue o default do cliente (definido em use_cache
        no __init__); True/False força ligar ou ignorar o cache só nesta
        chamada — útil quando você quer forçar uma resposta nova mesmo tendo
        cache (ex: temperature alta, respostas variadas de propósito).
        """
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
                    raw=None,
                )
                self._log_usage(response, cached=True)
                return response

        generation_config = {}
        if max_output_tokens is not None:
            generation_config["max_output_tokens"] = max_output_tokens
        if temperature is not None:
            generation_config["temperature"] = temperature

        attempt = 0
        while True:
            attempt += 1
            try:
                interaction, current_model = self._create_with_fallback(
                    input=prompt,
                    tools=TOOL_DEFINITIONS,
                    previous_interaction_id=previous_interaction_id,
                    preferred_model=model,
                    system_instruction=system,
                    generation_config=generation_config or None,
                )

                while True:
                    function_calls = self._get_function_calls(interaction)

                    if not function_calls:
                        break

                    logger.info(
                        "Gemini solicitou %d ferramenta(s).",
                        len(function_calls),
                    )

                    function_results = []

                    for step in function_calls:

                        result = self._execute_tool_call(step)

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

                    interaction, current_model = self._create_with_fallback(
                        input=function_results,
                        tools=TOOL_DEFINITIONS,
                        previous_interaction_id=interaction.id,
                        preferred_model=current_model,
                        system_instruction=system,
                    )

                response = self._to_response(
                    interaction,
                    current_model,
                    process_name,
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

            except _RETRYABLE_ERRORS as e:
                if attempt > self.max_retries:
                    logger.error(
                        "Excedeu %d tentativas. Desistindo. Último erro: %s",
                        self.max_retries, e,
                    )
                    raise
                wait = 2 ** attempt
                logger.warning(
                    "Erro transitório (tentativa %d/%d): %s. Aguardando %ds...",
                    attempt, self.max_retries, e, wait,
                )
                time.sleep(wait)

            # Qualquer outro erro (bug de programação, argumento inválido, etc.)
            # sobe na hora — não faz sentido "tentar de novo" um TypeError.

    def _to_response(
        self,
        interaction,
        model: str,
        process_name: Optional[str],
    ) -> GeminiResponse:

        usage = interaction.usage

        return GeminiResponse(
            text=interaction.output_text,
            input_tokens=getattr(
                usage,
                "total_input_tokens",
                0,
            ),
            output_tokens=getattr(
                usage,
                "total_output_tokens",
                0,
            ),
            total_tokens=getattr(
                usage,
                "total_tokens",
                0,
            ),
            model=model,
            interaction_id=getattr(
                interaction,
                "id",
                None,
            ),
            process_name=process_name,
            raw=interaction,
        )

    # --------------------------------------------------------------------------- #
    # Log de uso
    # --------------------------------------------------------------------------- #
    def _log_usage(self, response: GeminiResponse, cached: bool = False) -> None:
        self._session_input_tokens += response.input_tokens
        self._session_output_tokens += response.output_tokens
        self._session_calls += 1

        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "process": response.process_name,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "cached": cached,
        }
        try:
            with open(self.usage_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            # Não deixar uma falha de disco (ex: pasta sem permissão, disco cheio)
            # derrubar a chamada inteira — a resposta já foi obtida com sucesso.
            logger.warning("Não consegui gravar o log de uso em %s: %s", self.usage_log_path, e)

    def session_summary(self) -> dict:
        """Resumo do uso acumulado desde que este cliente foi criado (em memória)."""
        return {
            "calls": self._session_calls,
            "cache_hits": self._session_cache_hits,
            "input_tokens": self._session_input_tokens,
            "output_tokens": self._session_output_tokens,
            "total_tokens": self._session_input_tokens + self._session_output_tokens,
        }


# --------------------------------------------------------------------------- #
# Sessão de conversa
# --------------------------------------------------------------------------- #
class ChatSession:
    """
    Representa uma conversa com histórico. O histórico de verdade é mantido
    pelo servidor via `previous_interaction_id` — este objeto guarda uma
    cópia local (self.messages) só para você exibir/inspecionar.

    Se `session_id` for informado, o `interaction_id` mais recente (e o
    histórico local) é salvo em disco a cada mensagem, num arquivo
    compartilhado por session_id (`sessions_path`). Isso permite retomar a
    MESMA conversa em uma execução futura do script — o vínculo de
    continuidade é o interaction_id, que vive no servidor do Gemini, não
    no processo Python. Sem session_id, a sessão só existe em memória e se
    perde quando o script termina (comportamento anterior).
    """

    def __init__(
        self,
        client: GeminiClient,
        system_instruction: Optional[str] = None,
        session_id: Optional[str] = None,
        sessions_path: Path | str = DEFAULT_SESSIONS_PATH,
    ):
        self.client = client
        self.system = system_instruction
        self.session_id = session_id
        self.sessions_path = Path(sessions_path)
        self.messages: list[Message] = []
        self._last_interaction_id: Optional[str] = None

        if self.session_id:
            self._load()

    def send(self, user_message: str, **kwargs) -> GeminiResponse:
        """Envia uma mensagem e recebe a resposta, mantendo o histórico."""
        response = self.client.generate(
            prompt=user_message,
            previous_interaction_id=self._last_interaction_id,
            system=self.system,
            **kwargs,
        )

        # Só grava no histórico se a chamada teve sucesso — assim, se der
        # erro (mesmo após os retries), a conversa não fica com uma
        # mensagem "órfã" do usuário sem resposta correspondente.
        self.messages.append(Message(role="user", text=user_message))
        self.messages.append(Message(role="model", text=response.text))
        self._last_interaction_id = response.interaction_id

        if self.session_id:
            self._save()

        return response

    def get_history(self) -> list[Message]:
        """Retorna o histórico local (cópia, para não permitir mutação externa)."""
        return self.messages.copy()

    def clear_history(self) -> None:
        """Limpa o histórico local, desvincula da conversa anterior e apaga do disco."""
        self.messages.clear()
        self._last_interaction_id = None
        if self.session_id:
            self._save()

    # ------------------------------------------------------------------- #
    # Persistência em disco (entre execuções diferentes do script)
    # ------------------------------------------------------------------- #

    def _load(self) -> None:
        if not self.sessions_path.exists():
            return
        try:
            with open(self.sessions_path, encoding="utf-8") as f:
                all_sessions = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Não consegui ler %s (%s). Começando sessão nova.", self.sessions_path, e)
            return

        saved = all_sessions.get(self.session_id)
        if saved is None:
            return  # session_id novo, ainda não existe em disco

        self._last_interaction_id = saved.get("last_interaction_id")
        self.messages = [Message(**m) for m in saved.get("messages", [])]
        logger.info(
            "Sessão '%s' retomada (%d mensagem(ns) no histórico local).",
            self.session_id, len(self.messages),
        )

    def _save(self) -> None:
        all_sessions = {}
        if self.sessions_path.exists():
            try:
                with open(self.sessions_path, encoding="utf-8") as f:
                    all_sessions = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # arquivo corrompido: sobrescreve do zero em vez de travar

        all_sessions[self.session_id] = {
            "last_interaction_id": self._last_interaction_id,
            "messages": [{"role": m.role, "text": m.text} for m in self.messages],
        }

        try:
            with open(self.sessions_path, "w", encoding="utf-8") as f:
                json.dump(all_sessions, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("Não consegui salvar a sessão '%s' em disco: %s", self.session_id, e)


def read_usage_log(path: Path | str = DEFAULT_USAGE_LOG_PATH) -> list[dict]:
    """Lê o log persistido em disco (histórico entre execuções, não só da sessão atual)."""
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# --------------------------------------------------------------------------- #
# Registro de "processos": prompts/system reutilizáveis por nome
# --------------------------------------------------------------------------- #
_PROCESS_REGISTRY: dict[str, dict] = {}


def register_process(name: str, system: str, model: Optional[str] = None) -> None:
    """
    Registra um "processo" nomeado, que encapsula um prompt de sistema e modelo.
    Pode ser usado em múltiplos scripts diferentes, desde que o registro seja
    feito antes do uso.
    """
    _PROCESS_REGISTRY[name] = {"system": system, "model": model}
    logger.info(f"Processo '{name}' registrado com sucesso.")


def run_process(client: GeminiClient, name: str, prompt: str, **kwargs) -> GeminiResponse:
    """Executa um processo previamente registrado com register_process."""
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
    """
    Carrega processos de um arquivo YAML ou JSON e registra todos no
    catálogo (equivalente a chamar register_process() para cada um).
    Retorna quantos processos foram carregados.

    Formato esperado (chave = nome do processo):

        log_triage:
          system: >
            Você é um assistente de triagem de logs de pipelines de dados...
          model: null   # opcional; null usa o default do cliente

        resumo_pt:
          system: "Resuma o texto fornecido em até 3 frases, em português claro."

    Separar processos em arquivo (em vez de code) permite adicionar um
    processo novo sem tocar no módulo, e reusar o mesmo arquivo entre
    scripts diferentes.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de processos não encontrado: {path}")

    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as e:
            raise ImportError(
                "Para carregar processos de YAML, instale: pip install pyyaml"
            ) from e
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


# --------------------------------------------------------------------------- #
# Exemplo de uso
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # Processos carregados de arquivo (veja processes.yaml de exemplo).
    # Se preferir sem arquivo, register_process() continua funcionando normalmente.
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