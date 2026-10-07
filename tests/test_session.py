import json

import pytest

from gemini.session import ChatSession


class FakeClient:
    pass


def test_persist_cria_sessao_vazia_e_listagem(tmp_path):
    path = tmp_path / "state" / "sessions.json"
    session = ChatSession(FakeClient(), session_id="trabalho", sessions_path=path)

    session.persist()

    assert path.exists()
    assert ChatSession.session_exists("trabalho", path)
    assert ChatSession.list_sessions(path) == [
        {
            "session_id": "trabalho",
            "messages": 0,
            "updated_at": ChatSession.list_sessions(path)[0]["updated_at"],
        }
    ]


def test_list_sessions_le_formato_antigo_sem_updated_at(tmp_path):
    path = tmp_path / "sessions.json"
    path.write_text(
        json.dumps(
            {
                "antiga": {
                    "last_interaction_id": "interaction-1",
                    "messages": [{"role": "user", "text": "oi"}],
                }
            }
        ),
        encoding="utf-8",
    )

    assert ChatSession.list_sessions(path) == [
        {"session_id": "antiga", "messages": 1, "updated_at": None}
    ]


def test_list_sessions_ignora_messages_em_formato_invalido(tmp_path):
    path = tmp_path / "sessions.json"
    path.write_text(
        json.dumps({"invalida": {"messages": None}}),
        encoding="utf-8",
    )

    assert ChatSession.list_sessions(path)[0]["messages"] == 0


class FakeClientError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@pytest.mark.parametrize(
    "message",
    [
        "previous_interaction_id not found",
        "Interaction expired",
        "Previous interaction does not exist",
    ],
)
def test_reconhece_interacao_expirada(message):
    error = FakeClientError(404, message)

    assert ChatSession._looks_like_expired_interaction(error)


@pytest.mark.parametrize(
    ("code", "message"),
    [
        (401, "Interaction not found"),
        (400, "Invalid API key"),
        (400, "Interaction request malformed"),
    ],
)
def test_nao_confunde_outros_erros_com_interacao_expirada(code, message):
    error = FakeClientError(code, message)

    assert not ChatSession._looks_like_expired_interaction(error)


@pytest.mark.parametrize("session_id", ["", "   ", "nome\nquebrado", "x" * 81])
def test_rejeita_nome_de_sessao_invalido(session_id, tmp_path):
    with pytest.raises(ValueError):
        ChatSession(FakeClient(), session_id=session_id, sessions_path=tmp_path / "sessions.json")


def test_nome_da_sessao_e_normalizado(tmp_path):
    session = ChatSession(
        FakeClient(), session_id="  trabalho  ", sessions_path=tmp_path / "sessions.json"
    )

    assert session.session_id == "trabalho"
