"""Regressões do onboarding: configurar e reiniciar fora do repositório."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("custom_env", [False, True])
@pytest.mark.parametrize("system_key", [False, True])
def test_configure_and_restart_from_another_directory(tmp_path, custom_env, system_key):
    app_home = tmp_path / "app"
    working_a = tmp_path / "project-a"
    working_b = tmp_path / "project-b"
    working_a.mkdir()
    working_b.mkdir()
    (working_b / ".env").write_text("GEMINI_API_KEY=wrong-local-key\n", encoding="utf-8")
    data_dir = tmp_path / "custom-data"
    env_path = tmp_path / "explicit" / ".env" if custom_env else app_home / ".env"
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("GEMINI_", "HIVE_", "AIRFLOW_"))
        and key != "DB_CONN_STRING"
    }
    environment.update({
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        "TEST_APP_HOME": str(app_home),
        "TEST_DATA_HOME": str(data_dir),
        "TEST_ENV_PATH": str(env_path),
        "TEST_SYSTEM_KEY": "yes" if system_key else "no",
    })
    if custom_env:
        environment["GEMINI_ENV_PATH"] = str(env_path)
    if system_key:
        environment["GEMINI_API_KEY"] = "system-key"
    bootstrap = """
import os
from pathlib import Path
import platformdirs
platformdirs.user_data_dir = lambda *args, **kwargs: os.environ["TEST_APP_HOME"]
"""
    save = bootstrap + """
from gemini.env_config import ENV_PATH, update_env_value
assert ENV_PATH == Path(os.environ["TEST_ENV_PATH"])
update_env_value("GEMINI_API_KEY", "file-key")
update_env_value("GEMINI_DATA_DIR", os.environ["TEST_DATA_HOME"])
"""
    restart = bootstrap + """
from gemini import config, env_config
from tools.catalogs import catalog_path
from app_environment import ENV_PATH
expected = "system-key" if os.environ["TEST_SYSTEM_KEY"] == "yes" else "file-key"
assert os.environ["GEMINI_API_KEY"] == expected
assert env_config.load_env_status()["GEMINI_API_KEY"] == expected
assert ENV_PATH == Path(os.environ["TEST_ENV_PATH"])
assert config.DATA_DIR == Path(os.environ["TEST_DATA_HOME"])
assert catalog_path() == config.DATA_DIR / "catalogs.toml"
"""
    for script, cwd in ((save, working_a), (restart, working_b)):
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=cwd, env=environment,
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
    assert env_path.is_file()
    assert not (working_a / ".env").exists()
    assert (working_b / ".env").read_text(encoding="utf-8") == "GEMINI_API_KEY=wrong-local-key\n"

