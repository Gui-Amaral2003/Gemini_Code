from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ActivityEvent:
    """Evento observavel produzido durante uma chamada ao Gemini."""
    type: str
    message: str
    timestamp: float
    model: Optional[str] = None
    tool: Optional[str] = None
    stage: Optional[str] = None
    duration: Optional[float] = None
    details: dict = field(default_factory=dict)

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
    # Arquivos gerados por tools durante essa chamada (ex: PNGs de plot_sheet_data/plot_table_data), ainda em staging — cabe a quem consome (ex: gemini_terminal.py) decidir se mantém ou descarta.
    generated_files: list[Path] = field(default_factory=list)
    # Pensamentos do modelo durante a geração da resposta.
    thoughts: list[str] = field(default_factory = list)
    activities: list[ActivityEvent] = field(default_factory=list)
    duration: float = 0.0
    cached: bool = False
    raw: object = field(default=None, repr=False)

@dataclass
class Message:
    """Registro local de uma mensagem de uma conversa (só para exibição/histórico)."""
    role: str
    text: str
