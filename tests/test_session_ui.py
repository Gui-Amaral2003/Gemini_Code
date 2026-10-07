from datetime import datetime

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import gemini.session_ui as session_ui
from gemini.session_ui import (
    SESSIONS_COMMAND,
    format_relative,
    is_inactive,
    session_key_bindings,
    truncate,
)


def test_formata_tempo_relativo():
    now = datetime(2026, 10, 6, 12, 0, 0)

    assert format_relative("2026-10-06 11:59:30", now) == "há 30s"
    assert format_relative("2026-10-06 11:55:00", now) == "há 5min"
    assert format_relative("2026-10-06 09:00:00", now) == "há 3h"
    assert format_relative(None, now) == "desconhecido"


def test_identifica_sessao_inativa():
    now = datetime(2026, 10, 6, 12, 0, 0)

    assert is_inactive("2026-09-29 11:59:59", now)
    assert not is_inactive("2026-10-01 12:00:00", now)


def test_truncate_adiciona_reticencias():
    assert truncate("abcdefgh", 5) == "abcde…"
    assert truncate("abc", 5) == "abc"


def test_atalho_de_sessao_usa_seta_direita():
    bindings = session_key_bindings().bindings

    assert SESSIONS_COMMAND == "/sessions"
    assert any(binding.keys == ("right",) for binding in bindings)


def test_tela_reutiliza_input_e_output_informados(monkeypatch):
    sentinel_input = object()
    sentinel_output = object()
    captured = {}

    class FakeApplication:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return ("back", None)

    monkeypatch.setattr(session_ui, "Application", FakeApplication)

    assert session_ui.pick_session(
        [], input=sentinel_input, output=sentinel_output
    ) == ("back", None)
    assert captured["input"] is sentinel_input
    assert captured["output"] is sentinel_output


def test_tela_processa_atalho_de_nova_sessao(monkeypatch):
    real_application = session_ui.Application

    with create_pipe_input() as pipe_input:
        class TestApplication:
            def __init__(self, **kwargs):
                self.app = real_application(
                    **kwargs, input=pipe_input, output=DummyOutput()
                )

            def run(self):
                return self.app.run(pre_run=lambda: pipe_input.send_text("n"))

        monkeypatch.setattr(session_ui, "Application", TestApplication)

        assert session_ui.pick_session([], None) == ("new", None)


def test_tela_processa_navegacao_e_abertura(monkeypatch):
    real_application = session_ui.Application
    sessions = [
        {"session_id": "primeira", "messages": 0, "updated_at": None},
        {"session_id": "segunda", "messages": 0, "updated_at": None},
    ]

    with create_pipe_input() as pipe_input:
        class TestApplication:
            def __init__(self, **kwargs):
                self.app = real_application(
                    **kwargs, input=pipe_input, output=DummyOutput()
                )

            def run(self):
                return self.app.run(pre_run=lambda: pipe_input.send_text("j\r"))

        monkeypatch.setattr(session_ui, "Application", TestApplication)

        assert session_ui.pick_session(sessions, None) == ("open", "segunda")


def test_tela_processa_escape(monkeypatch):
    real_application = session_ui.Application

    with create_pipe_input() as pipe_input:
        class TestApplication:
            def __init__(self, **kwargs):
                self.app = real_application(
                    **kwargs, input=pipe_input, output=DummyOutput()
                )

            def run(self):
                return self.app.run(pre_run=lambda: pipe_input.send_bytes(b"\x1b"))

        monkeypatch.setattr(session_ui, "Application", TestApplication)

        assert session_ui.pick_session([], None) == ("back", None)
