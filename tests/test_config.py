from pathlib import Path

from gemini.config import DEFAULT_SESSIONS_PATH


def test_caminho_de_sessoes_nao_depende_do_diretorio_atual():
    assert DEFAULT_SESSIONS_PATH.is_absolute()
    assert DEFAULT_SESSIONS_PATH.name == "chat_sessions.json"
    assert DEFAULT_SESSIONS_PATH.parent == Path(__file__).resolve().parents[1] / "gemini"
