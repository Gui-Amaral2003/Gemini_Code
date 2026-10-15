from gemini.config import (
    DATA_DIR,
    DEFAULT_CACHE_PATH,
    DEFAULT_PROMPT_HISTORY_PATH,
    DEFAULT_QUOTA_PATH,
    DEFAULT_SESSIONS_PATH,
    DEFAULT_TRACE_LOG_PATH,
    DEFAULT_USAGE_LOG_PATH,
    PACKAGE_DIR,
    _resolve_data_dir,
)


def test_caminho_de_sessoes_nao_depende_do_diretorio_atual():
    assert DEFAULT_SESSIONS_PATH.is_absolute()
    assert DEFAULT_SESSIONS_PATH.name == "chat_sessions.json"
    assert DEFAULT_SESSIONS_PATH.parent == DATA_DIR
    assert DATA_DIR != PACKAGE_DIR


def test_arquivos_de_estado_compartilham_diretorio_de_dados():
    paths = {
        DEFAULT_CACHE_PATH,
        DEFAULT_PROMPT_HISTORY_PATH,
        DEFAULT_QUOTA_PATH,
        DEFAULT_SESSIONS_PATH,
        DEFAULT_TRACE_LOG_PATH,
        DEFAULT_USAGE_LOG_PATH,
    }

    assert {path.parent for path in paths} == {DATA_DIR}


def test_diretorio_de_dados_pode_ser_sobrescrito_por_env(monkeypatch, tmp_path):
    custom_dir = tmp_path / "runtime"
    monkeypatch.setenv("GEMINI_DATA_DIR", str(custom_dir))

    assert _resolve_data_dir() == custom_dir.resolve()
