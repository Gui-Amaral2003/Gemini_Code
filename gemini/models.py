from dataclasses import dataclass, field
from typing import Optional

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
    api_calls: int = 1
    raw: object = field(default=None, repr=False)

@dataclass
class Message:
    """Registro local de uma mensagem de uma conversa (só para exibição/histórico)."""
    role: str
    text: str
