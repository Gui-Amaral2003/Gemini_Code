from copy import deepcopy
from io import StringIO
import os
import subprocess
import sys

import pytest
from rich.console import Console

from tools import catalogs
from gemini import resource_wizard


def test_missing_catalog_has_no_permissions(tmp_path):
    assert catalogs.load_catalog(tmp_path / "missing.toml") == {}


def test_malformed_toml_is_reported_without_overwriting(tmp_path):
    path = tmp_path / "catalogs.toml"
    path.write_text("[broken", encoding="utf-8")
    with pytest.raises(catalogs.CatalogError, match="Não foi possível ler"):
        catalogs.load_catalog(path)
    assert path.read_text(encoding="utf-8") == "[broken"


def test_catalog_path_uses_explicit_override(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_CATALOG_PATH", str(tmp_path / "custom.toml"))
    assert catalogs.catalog_path() == tmp_path / "custom.toml"


def test_roundtrip_preserves_git_airflow_and_table_configuration(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    data = {
        "git": {"repositories": {"repo": {"path": str(repo), "writable": False}}},
        "airflow": {"dags": {"daily.v1": {"description": 'Ingestão "diária"'}}},
        "database": {"tables": {"deals": {
            "connection": "sqlserver_main",
            "schema": "sales",
            "return_columns": ["id"],
            "filter_columns": {"id": "int"},
        }}},
    }
    path = tmp_path / "catalogs.toml"
    catalogs.save_catalog(data, path)
    assert catalogs.load_catalog(path) == data


@pytest.mark.parametrize("config", [
    {"git": {"repositories": {"repo": {"path": "relative/path"}}}},
    {"git": {"repository": {}}},
    {"airflow": {"dags": {"../daily": {"description": "Invalid"}}}},
    {"database": {"tables": {"deals": {
        "connection": "hive_lake", "schema": "sales",
        "return_columns": ["id"], "editable_columns": {"id": "int"},
    }}}},
])
def test_invalid_catalog_cannot_replace_existing_file(tmp_path, config):
    path = tmp_path / "catalogs.toml"
    catalogs.save_catalog({}, path)
    original = path.read_bytes()
    with pytest.raises(catalogs.CatalogError):
        catalogs.save_catalog(config, path)
    assert path.read_bytes() == original


def test_failed_atomic_replace_preserves_original(monkeypatch, tmp_path):
    path = tmp_path / "catalogs.toml"
    catalogs.save_catalog({}, path)
    original = path.read_bytes()

    def fail(*args):
        raise OSError("write failed")

    monkeypatch.setattr(catalogs.os, "replace", fail)
    with pytest.raises(OSError):
        catalogs.save_catalog({"airflow": {"dags": {}}}, path)
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


def test_wizard_cancel_does_not_save(monkeypatch, tmp_path):
    path = tmp_path / "catalogs.toml"
    answers = iter(["2", "adicionar", "daily", "Daily job", "0"])
    monkeypatch.setattr(resource_wizard.Prompt, "ask", lambda *a, **kw: next(answers))
    monkeypatch.setattr(resource_wizard.Confirm, "ask", lambda *a, **kw: False)
    resource_wizard.run_resources(Console(file=StringIO()), path)
    assert not path.exists()


def test_wizard_save_preserves_other_groups(monkeypatch, tmp_path):
    path = tmp_path / "catalogs.toml"
    original = {"database": {"tables": {"deals": {
        "connection": "sqlserver_main", "schema": "sales", "return_columns": ["id"],
    }}}}
    catalogs.save_catalog(original, path)
    answers = iter(["2", "adicionar", "daily", "Daily job", "0"])
    monkeypatch.setattr(resource_wizard.Prompt, "ask", lambda *a, **kw: next(answers))
    monkeypatch.setattr(resource_wizard.Confirm, "ask", lambda *a, **kw: True)
    resource_wizard.run_resources(Console(file=StringIO()), path)
    result = catalogs.load_catalog(path)
    assert result["database"] == original["database"]
    assert result["airflow"]["dags"]["daily"]["description"] == "Daily job"


def test_wizard_requires_explicit_write_phrase(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    data = {}
    answers = iter(["adicionar", "project", str(repo), "wrong"])
    monkeypatch.setattr(resource_wizard.Prompt, "ask", lambda *a, **kw: next(answers))
    monkeypatch.setattr(resource_wizard.Confirm, "ask", lambda *a, **kw: True)
    candidate = deepcopy(data)
    assert not resource_wizard._edit_resource(
        Console(file=StringIO()), candidate, "git", "repositories"
    )
    assert not candidate["git"]["repositories"]


@pytest.mark.parametrize("invalid", [False, True])
def test_startup_schemas_share_catalog_and_fail_closed(tmp_path, invalid):
    path = tmp_path / "catalogs.toml"
    if invalid:
        path.write_text("[invalid", encoding="utf-8")
    else:
        catalogs.save_catalog({
            "airflow": {"dags": {"daily_test": {"description": "Test"}}},
        }, path)
    script = """
import os
from tools.catalogs import AIRFLOW_ALLOWED_DAGS, TABLES_ALLOWED, GIT_ALLOWED_REPOS, CATALOG_ERROR
from tools.definitions import TOOL_DEFINITIONS
definition = next(d for d in TOOL_DEFINITIONS if d["name"] == "get_dag_runs")
dag_schema = definition["parameters"]["properties"]["dag_id"]
assert not TABLES_ALLOWED and not GIT_ALLOWED_REPOS
if os.environ["TEST_INVALID"] == "yes":
    assert not AIRFLOW_ALLOWED_DAGS and CATALOG_ERROR
    assert "enum" not in dag_schema
else:
    assert set(AIRFLOW_ALLOWED_DAGS) == {"daily_test"}
    assert dag_schema["enum"] == ["daily_test"]
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "GEMINI_CATALOG_PATH": str(path), "TEST_INVALID": "yes" if invalid else "no"},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
