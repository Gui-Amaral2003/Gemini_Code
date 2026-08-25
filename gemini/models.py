from dataclasses import dataclass, field
from pathlib import Path
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
    # Arquivos gerados por tools durante essa chamada (ex: PNGs de plot_sheet_data/plot_table_data), ainda em staging — cabe a quem consome (ex: gemini_terminal.py) decidir se mantém ou descarta.
    generated_files: list[Path] = field(default_factory=list)
    # Pensamentos do modelo durante a geração da resposta.
    thoughts: list[str] = field(default_factory = list)
    raw: object = field(default=None, repr=False)

@dataclass
class Message:
    """Registro local de uma mensagem de uma conversa (só para exibição/histórico)."""
    role: str
    text: str