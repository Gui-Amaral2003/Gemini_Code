
from pathlib import Path
from google.genai import errors as genai_errors
import ssl

RETRYABLE_ERRORS = (
    genai_errors.ServerError,
    ConnectionError,
    TimeoutError,
    ssl.SSLError
)

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_USAGE_LOG_PATH = Path('gemini/gemini_usage_log.jsonl')
DEFAULT_CACHE_PATH = Path('gemini/gemini_cache.json')
DEFAULT_SESSIONS_PATH = Path('gemini/chat_sessions.json')
DEFAULT_TRACE_LOG_PATH = Path('gemini/gemini_trace_log.jsonl')
DEFAULT_QUOTA_PATH = Path('gemini/quota_tracker.json')