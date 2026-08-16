"""Compatibilidade com imports antigos do cliente Gemini."""

from gemini import (
    ChatSession,
    GeminiClient,
    GeminiResponse,
    Message,
    load_processes,
    register_process,
    run_process,
)

__all__ = [
    "GeminiClient",
    "ChatSession",
    "GeminiResponse",
    "Message",
    "register_process",
    "run_process",
    "load_processes",
]