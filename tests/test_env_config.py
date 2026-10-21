from dotenv import dotenv_values

from gemini import env_config


def test_load_env_status_returns_empty_for_missing_file(tmp_path):
    assert env_config.load_env_status(tmp_path / ".env") == {}


def test_save_default_env_creates_parent_and_reads_latest_values(monkeypatch, tmp_path):
    path = tmp_path / "new" / "app" / ".env"
    monkeypatch.setattr(env_config, "ENV_PATH", path)
    monkeypatch.setattr(env_config, "SYSTEM_ENV", {})

    env_config.update_env_value("GEMINI_API_KEY", "first")
    assert env_config.load_env_status()["GEMINI_API_KEY"] == "first"
    env_config.update_env_value("GEMINI_API_KEY", "second")
    assert env_config.load_env_status()["GEMINI_API_KEY"] == "second"
    assert path.is_file()


def test_diagnostics_use_system_values_without_exposing_or_replacing_file(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    env_config.update_env_value("GEMINI_API_KEY", "file-value", path)
    monkeypatch.setattr(env_config, "ENV_PATH", path)
    monkeypatch.setattr(env_config, "SYSTEM_ENV", {"GEMINI_API_KEY": "system-value"})

    assert env_config.load_env_status()["GEMINI_API_KEY"] == "system-value"
    assert env_config.load_env_status(path)["GEMINI_API_KEY"] == "file-value"
    env_config.update_env_value("GEMINI_API_KEY", "edited-file-value")
    assert env_config.load_env_status()["GEMINI_API_KEY"] == "system-value"
    assert env_config.load_env_status(path)["GEMINI_API_KEY"] == "edited-file-value"


def test_delete_default_env_keeps_other_quoted_settings(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    monkeypatch.setattr(env_config, "ENV_PATH", path)
    env_config.update_env_value("GEMINI_API_KEY", "secret")
    env_config.update_env_value("HIVE_PASSWORD", 'quoted "password"')

    env_config.delete_env_value("GEMINI_API_KEY")

    assert dotenv_values(path) == {"HIVE_PASSWORD": 'quoted "password"'}


def test_update_env_value_creates_file_and_preserves_existing_content(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("# comentário\nEXISTING=value\n", encoding="utf-8")

    env_config.update_env_value("GEMINI_API_KEY", "secret-key", env_path)

    values = dotenv_values(env_path)
    assert values == {
        "EXISTING": "value",
        "GEMINI_API_KEY": "secret-key",
    }
    assert "# comentário" in env_path.read_text(encoding="utf-8")


def test_update_env_value_replaces_only_requested_key(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        'GEMINI_API_KEY="old"\nHIVE_HOST="server"\n',
        encoding="utf-8",
    )

    env_config.update_env_value("GEMINI_API_KEY", "new", env_path)

    assert dotenv_values(env_path) == {
        "GEMINI_API_KEY": "new",
        "HIVE_HOST": "server",
    }


def test_is_configured_rejects_missing_and_empty_values():
    status = {
        "EMPTY": "",
        "CONFIGURED": "value",
    }

    assert env_config.is_configured("CONFIGURED", status) is True
    assert env_config.is_configured("EMPTY", status) is False
    assert env_config.is_configured("MISSING", status) is False


def test_missing_required_reports_gemini_key(tmp_path):
    env_path = tmp_path / ".env"

    assert [item.key for item in env_config.missing_required(env_path)] == [
        "GEMINI_API_KEY"
    ]

    env_config.update_env_value("GEMINI_API_KEY", "configured", env_path)
    assert env_config.missing_required(env_path) == []


def test_port_validator_accepts_integer_and_rejects_other_values():
    assert env_config._validate_port("10000") is None
    assert env_config._validate_port("abc") == "Porta deve ser um número inteiro."


def test_secret_settings_are_marked_as_secret():
    secret_keys = {
        key for key, setting in env_config.ENV_SETTINGS.items()
        if setting.secret
    }

    assert secret_keys == {
        "GEMINI_API_KEY",
        "DB_CONN_STRING",
        "HIVE_PASSWORD",
        "AIRFLOW_PASSWORD",
    }
