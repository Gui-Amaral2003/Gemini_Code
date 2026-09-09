
from pathlib import Path
from google.genai import errors as genai_errors
import ssl

RETRYABLE_ERRORS = (
    genai_errors.ServerError,
    ConnectionError,
    TimeoutError,
    ssl.SSLError
)

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_USAGE_LOG_PATH = Path('gemini/gemini_usage_log.jsonl')
DEFAULT_CACHE_PATH = Path('gemini/gemini_cache.json')
DEFAULT_SESSIONS_PATH = Path('gemini/chat_sessions.json')
DEFAULT_TRACE_LOG_PATH = Path('gemini/gemini_trace_log.jsonl')
DEFAULT_QUOTA_PATH = Path('gemini/quota_tracker.json')

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