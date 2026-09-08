
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
#      onde esse timeout não é respeitado em certos paths internos. Por isso
#      as camadas 2 e 3 não são "extra", são a proteção real.
#   2. MAX_TOOL_ROUNDS — limite de rodadas de tool-calling numa mesma
#      chamada a generate(). Cobre o modelo pedindo ferramentas indefinidamente.
#   3. MAX_GENERATE_SECONDS — orçamento de tempo total de um generate(),
#      checado de forma COOPERATIVA (só entre rodadas de tool-calling, nunca
#      no meio da execução de uma tool) — matar a execução à força no meio
#      de um update_table/edit_repo_file quebraria a invariante de reversão
#      segura dessas ferramentas.
#
# Ambos os limites (2 e 3) podem ser contornados via confirmação explícita
# do usuário (ver GeminiClient._check_generation_budget) — mesmo padrão já
# usado para cota diária esgotada.
#
# Valores abaixo são placeholder — mesmo status do RATE_LIMITS_RPD em
# quota_tracker.py: ajustar com uso real antes de confiar cegamente.
DEFAULT_API_CALL_TIMEOUT_SECONDS = 200
MAX_TOOL_ROUNDS = 10
MAX_GENERATE_SECONDS = 300
