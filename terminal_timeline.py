"""
Timeline de atividade em tempo real para o terminal interativo — substitui
o Status de linha única ("Gemini está pensando...") por uma lista de
linhas que cresce conforme os ActivityEvent chegam (seleção de modelo,
ferramentas executando/concluídas).

Reaproveita a mesma decisão de "quais eventos importam" que já existe em
gemini_terminal.py::print_trace(compact=True) — não duplica critério novo.

Isolado num módulo próprio pelo mesmo motivo de terminal_completer.py:
mantém a lógica de UI fora de gemini/client.py, sem acoplar o client a
nenhuma biblioteca de terminal.
"""
from typing import Optional
from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

from gemini import ActivityEvent

_RELEVANT_TYPES = {
    "model_selected",
    "fallback_selected",
    "synthesis_started",
    "tool_started",
    "tool_completed",
    "tool_failed",
}


class ToolTimeline:
    """
    Uso:
        timeline = ToolTimeline(console)
        timeline.start()
        client.set_activity_callback(timeline.handle_event)
        ...
        timeline.stop()

    stop()/start() têm a mesma assinatura que Status.stop()/start(), então
    os callbacks de confirmação (make_confirm_callback/make_confirm_typed_callback)
    funcionam sem alteração — só passar o timeline no lugar do status.
    """

    def __init__(self, console: Console):
        self._console = console
        self._lines: list[Text] = []
        # tool_name -> índice em self._lines, para reescrever "Executando X..." como "✓ X concluída"
        self._tool_line_index: dict[str, int] = {}
        self._live: Optional[Live] = None

    def start(self) -> None:
        self._lines = []
        self._tool_line_index = {}
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=12,
            transient=True,  # some ao parar
        )
        self._live.start()

    def stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    def handle_event(self, event: ActivityEvent) -> None:
        if event.type not in _RELEVANT_TYPES:
            return

        if event.type == "tool_started" and event.tool:
            line = Text("⠋ ", style="dim")
            line.append(f"Executando {event.tool}...")
            self._tool_line_index[event.tool] = len(self._lines)
            self._lines.append(line)

        elif event.type in {"tool_completed", "tool_failed"} and event.tool:
            ok = event.type == "tool_completed"
            icon, style = ("✓", "bold green") if ok else ("x", "bold red")
            duration = f" ({event.duration:.2f}s)" if event.duration is not None else ""

            line = Text(f"{icon} ", style=style)
            line.append(f"{event.tool}{duration}")

            index = self._tool_line_index.get(event.tool)
            if index is not None:
                self._lines[index] = line
            else:
                self._lines.append(line)

        else:
            # Eventos informativos sem par início/fim: seleção de modelo, fallback, início da síntese com o modelo barato.
            line = Text("• ", style="dim")
            line.append(event.message)
            self._lines.append(line)

        if self._live is not None:
            self._live.update(self._render())

    def _render(self):
        if not self._lines:
            return Text("Gemini está pensando...", style="dim")
        return Group(*self._lines)