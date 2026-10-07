"""
Tela full-screen para gerenciar sessões.
 
Camada de apresentação pura sobre ChatSession.list_sessions(): não conhece
GeminiClient nem faz I/O em disco. Quem chama (gemini_terminal.py) decide o
que fazer com a ação retornada — abrir uma sessão existente reaproveita
exatamente a mesma lógica do /switch.
 
Abre com a seta para a direita quando o prompt está vazio (ver
session_key_bindings) ou digitando /sessions.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, HSplit, VSplit, Window, Layout
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style

SESSIONS_COMMAND = "/sessions"

INACTIVE_AFTER_DAYS = 7

NAME_WIDTH = 28
FIRST_MESSAGE_CHARS = 200
LAST_MESSAGE_CHARS = 600

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, _TIMESTAMP_FORMAT)
    except ValueError:
        return None

def format_relative(updated_at: Optional[str], now: Optional[datetime] = None) -> str:
    """'2026-10-05 10:00:00' -> 'há 42s' / 'há 5min' / 'há 3h' / 'há 30d'."""

    parsed = _parse_timestamp(updated_at)
    if parsed is None:
        return "desconhecido"

    seconds = max(0, int(((now or datetime.now()) - parsed).total_seconds()))
    if seconds < 60:
        return f"há {seconds}s"
    if seconds < 3600:
        return f"há {seconds // 60}min"
    if seconds < 86400:
        return f"há {seconds // 3600}h"
    return f"há {seconds // 86400}d"

def is_inactive(updated_at: Optional[str], now: Optional[datetime] = None) -> bool:
    parsed = _parse_timestamp(updated_at)
    if parsed is None:
        return False
    return ((now or datetime.now()) - parsed).days >= INACTIVE_AFTER_DAYS

def truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"

def _inline(text: str, limit: int) -> str:
    """Versão de uma linha só (para a lista): colapsa espaços/quebras e corta."""
    return truncate(" ".join((text or "").split()), limit)

def session_key_bindings() -> KeyBindings:
    """
    Seta para a direita abre a tela de sessões, mas SÓ com o buffer vazio —
    assim não briga com a edição normal nem com o autosuggest (que também usa
    a seta direita quando há texto digitado).
 
    O prompt devolve SESSIONS_COMMAND como se o usuário tivesse digitado
    '/sessions'; o loop principal trata como mais um comando.
    """
    kb = KeyBindings()
 
    @kb.add("right", filter=Condition(lambda: not get_app().current_buffer.text))
    def _(event):
        event.app.exit(result=SESSIONS_COMMAND)
 
    return kb

def pick_session(
    sessions: list[dict],
    active_id: Optional[str] = None,
    *,
    input=None,
    output=None,
) -> tuple[str, Optional[str]]:
    """
    Mostra a lista de sessões (esquerda) e os detalhes da selecionada (direita).
 
    sessions: saída de ChatSession.list_sessions() — cada item com
        session_id, messages, updated_at, first_user, last_model.
    Retorna ("open", session_id) | ("new", None) | ("back", None).
    """
    state = {'index': 0}
    for i, item in enumerate(sessions):
        if item['session_id'] == active_id:
            state['index'] = i
            break

    def move(delta: int):
        if sessions:
            state['index'] = max(0, min(len(sessions) - 1, state['index'] + delta))

    def header_fragments():
        total = len(sessions)
        inactive = sum(is_inactive(s['updated_at']) for s in sessions)
        return [
            ("bold", "Sessões\n"),
            ("ansibrightblack", f"Todas {total}  ·  Recentes {total - inactive}  ·  Inativas {inactive}"),
        ]

    def list_fragments():
        if not sessions:
            return [("ansibrightblack", "  Nenhuma sessão persistida. Pressione n para criar uma.\n")]

        fragments = []
        for i, item in enumerate(sessions):
            selected = i == state['index']
            inactive = is_inactive(item['updated_at'])
            style = 'reverse' if selected else ('inactive' if inactive else "")
            marker = "›" if selected else " "
            dot = "●" if item["session_id"] == active_id else "○"
            name = _inline(item["session_id"], NAME_WIDTH)
            when = format_relative(item.get("updated_at"))

            line = f" {marker} {dot} {name:<{NAME_WIDTH}} {item.get('messages', 0):>4} msg {when:>10}"
            fragments.append((style, line + "\n"))

        return fragments

    def detail_fragments():
        if not sessions:
            return [('ansibrightblack', 'Sem detalhes.')]

        item = sessions[state['index']]
        updated_at = item.get('updated_at')
        fragments = [
            ("bold", "Detalhes da sessão\n\n"),
            ("ansicyan", f"{item['session_id']}\n"),
        ]
        if item['session_id'] == active_id:
            fragments.append(("ansigreen", "Sessão ativa\n\n"))

        fragments += [
            ("ansibrightblack", f"{item.get('messages', 0)} mensagens · atualizada {format_relative(updated_at)}"),
            ("ansibrightblack", f" ({updated_at or 'sem data'})\n\n"),
            ("ansibrightblack", "Primeira pergunta\n"),
            ("", truncate(item.get("first_user", ""), FIRST_MESSAGE_CHARS) or "(vazia)"),
            ("", "\n\n"),
            ("ansibrightblack", "Última resposta\n"),
            ("", truncate(item.get("last_model", ""), LAST_MESSAGE_CHARS) or "(sem resposta ainda)"),
            ("", "\n"),
        ]

        if is_inactive(updated_at):
            fragments += [
                ("", "\n"),
                (
                    "ansiyellow",
                    "Sessão antiga: o servidor pode ter descartado o contexto. "
                    "Se isso acontecer, você poderá reconstruí-lo a partir do histórico local.\n",
                ),
            ]

        return fragments

    def footer_fragments():
        return [("ansibrightblack", " ↑/↓ mover   enter abrir   n nova   esc voltar")]

    kb = KeyBindings()
 
    @kb.add("up")
    @kb.add("k")
    def _(event):
        move(-1)
 
    @kb.add("down")
    @kb.add("j")
    def _(event):
        move(1)
 
    @kb.add("pageup")
    def _(event):
        move(-10)
 
    @kb.add("pagedown")
    def _(event):
        move(10)
 
    @kb.add("home")
    def _(event):
        state["index"] = 0
 
    @kb.add("end")
    def _(event):
        move(len(sessions))
 
    @kb.add("enter")
    def _(event):
        if sessions:
            event.app.exit(result=("open", sessions[state["index"]]["session_id"]))
 
    @kb.add("n")
    def _(event):
        event.app.exit(result=("new", None))

    # eager: sem isso o Escape espera um instante para saber se é início de
    # uma sequência (ex: setas), e a tela parece travada ao voltar.
    @kb.add("escape", eager=True)
    @kb.add("left")
    @kb.add("q")
    @kb.add("c-c")
    def _(event):
        event.app.exit(result=("back", None))

    list_window = Window(
        FormattedTextControl(
            list_fragments,
            get_cursor_position=lambda: Point(x=0, y=state["index"]),
            focusable=True,
        ),
        width=Dimension(weight=3),
        always_hide_cursor=True,
        wrap_lines=False,
    )
    detail_window = Window(
        FormattedTextControl(detail_fragments),
        width=Dimension(weight=2),
        wrap_lines=True,
    )
 
    layout = Layout(
        HSplit([
            Window(FormattedTextControl(header_fragments), height=2),
            Window(height=1, char="─"),
            VSplit([list_window, Window(width=1, char="│"), detail_window]),
            Window(FormattedTextControl(footer_fragments), height=1),
        ]),
        focused_element=list_window,
    )
 
    style = Style.from_dict({"inactive": "fg:#666666"})
    application_options = {}
    if input is not None:
        application_options["input"] = input
    if output is not None:
        application_options["output"] = output

    return Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=True,
        **application_options,
    ).run()

