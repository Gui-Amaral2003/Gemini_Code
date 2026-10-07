from types import SimpleNamespace

import gemini_terminal


class FakePromptSession:
    def __init__(self, answers):
        self.answers = iter(answers)

    def prompt(self, _message):
        return next(self.answers)


def _sessions():
    return [
        {"session_id": "default", "messages": 2, "updated_at": None},
        {"session_id": "trabalho", "messages": 4, "updated_at": None},
    ]


def test_submenu_consume_n_e_nome_da_nova_sessao(monkeypatch):
    monkeypatch.setattr(gemini_terminal, "print_sessions", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        gemini_terminal.ChatSession, "list_sessions", lambda _path: _sessions()
    )
    chat = SimpleNamespace(sessions_path="sessions.json", session_id="default")

    result = gemini_terminal.pick_session_in_prompt(
        chat, FakePromptSession(["n", "projeto"])
    )

    assert result == ("new", "projeto")


def test_submenu_abre_sessao_pelo_numero(monkeypatch):
    monkeypatch.setattr(gemini_terminal, "print_sessions", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        gemini_terminal.ChatSession, "list_sessions", lambda _path: _sessions()
    )
    chat = SimpleNamespace(sessions_path="sessions.json", session_id="default")

    result = gemini_terminal.pick_session_in_prompt(
        chat, FakePromptSession(["2"])
    )

    assert result == ("open", "trabalho")


def test_submenu_volta_sem_enviar_entrada_ao_modelo(monkeypatch):
    monkeypatch.setattr(gemini_terminal, "print_sessions", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        gemini_terminal.ChatSession, "list_sessions", lambda _path: _sessions()
    )
    chat = SimpleNamespace(sessions_path="sessions.json", session_id="default")

    result = gemini_terminal.pick_session_in_prompt(chat, FakePromptSession(["q"]))

    assert result == ("back", None)
