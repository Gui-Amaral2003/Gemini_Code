from dotenv import dotenv_values

from gemini import env_config


def test_load_env_status_returns_empty_for_missing_file(tmp_path):
    assert env_config.load_env_status(tmp_path / ".env") == {}


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
