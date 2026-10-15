
import os
import ssl
from pathlib import Path

from google.genai import errors as genai_errors
from dotenv import load_dotenv
from platformdirs import user_data_dir

load_dotenv()

PACKAGE_DIR = Path(__file__).resolve().parent
APP_NAME = "GeminiTerminal"
APP_AUTHOR = "GuiAmaral"


def _resolve_data_dir() -> Path:
    configured = os.environ.get("GEMINI_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


DATA_DIR = _resolve_data_dir()

RETRYABLE_ERRORS = (
    genai_errors.ServerError,
    ConnectionError,
    TimeoutError,
    ssl.SSLError
)

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_USAGE_LOG_PATH = DATA_DIR / "gemini_usage_log.jsonl"
DEFAULT_CACHE_PATH = DATA_DIR / "gemini_cache.json"
# A persistência de sessões não pode depender do diretório de onde o
# terminal foi iniciado. Sem uma base absoluta, executar o mesmo script fora
# da raiz do projeto cria/lê outro arquivo e faz sessões parecerem ausentes.
DEFAULT_SESSIONS_PATH = DATA_DIR / "chat_sessions.json"
DEFAULT_TRACE_LOG_PATH = DATA_DIR / "gemini_trace_log.jsonl"
DEFAULT_QUOTA_PATH = DATA_DIR / "quota_tracker.json"
DEFAULT_PROMPT_HISTORY_PATH = DATA_DIR / "prompt_history.txt"
DEFAULT_DB_AUDIT_LOG_PATH = DATA_DIR / "db_write_audit_log.jsonl"
DEFAULT_GIT_AUDIT_LOG_PATH = DATA_DIR / "git_write_audit_log.jsonl"

# --------------------------------------------------------------------------- #
# Timeouts — defesa em camadas contra travamentos.
#
#   1. DEFAULT_API_CALL_TIMEOUT_SECONDS — timeout de uma chamada HTTP
#      individual ao Gemini. Aplicado tanto no client inteiro (HttpOptions,
#      em MILISSEGUNDOS) quanto por chamada (interactions.create(timeout=...),
#      em SEGUNDOS — atenção à diferença de unidade). NÃO é garantia: há
#      issues abertas no SDK (googleapis/python-genai #911, #1330, #4031)
#      onde esse timeout não é respeitado em certos paths internos.
#   2. MAX_TOOL_ROUNDS — limite de rodadas de tool-calling numa mesma
#      chamada a generate(). Cobre o modelo pedindo ferramentas indefinidamente
#      sem cronometrar nem interromper a execução de uma tool. Cada ferramenta
#      deve controlar seu próprio timeout conforme a operação e suas garantias
#      de consistência (transação, rollback, idempotência etc.).
#
# O limite de rodadas pode ser estendido via confirmação explícita do usuário
# (ver GeminiClient._check_tool_round_budget) — mesmo padrão já usado para cota
# diária esgotada.
#
# Valores abaixo são placeholder — mesmo status do RATE_LIMITS_RPD em
# quota_tracker.py: ajustar com uso real antes de confiar cegamente.
DEFAULT_API_CALL_TIMEOUT_SECONDS = 200
MAX_TOOL_ROUNDS = 10
MAX_TOOL_EXEC_SECONDS = 90
