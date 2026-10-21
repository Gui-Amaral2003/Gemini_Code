"""Catálogo local validado, compartilhado pelos schemas e pelas tools."""

import json
import os
import re
import tempfile
import tomllib
from pathlib import Path

from app_environment import resolve_data_dir

from .db_connections import DB_CONNECTIONS


class CatalogError(ValueError):
    """Catálogo inválido: nenhuma permissão é carregada."""


def catalog_path() -> Path:
    configured = os.environ.get("GEMINI_CATALOG_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return resolve_data_dir() / "catalogs.toml"


def _mapping(value, location):
    if not isinstance(value, dict):
        raise CatalogError(f"{location}: esperado um grupo TOML.")
    return value


def _keys(value, allowed, location):
    unknown = set(value) - set(allowed)
    if unknown:
        raise CatalogError(f"{location}: campos desconhecidos: {', '.join(sorted(unknown))}.")


def _text(value, location):
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{location}: informe um texto não vazio.")
    return value


def validate_sql_identifier(value, location):
    _text(value, location)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise CatalogError(f"{location}: identificador SQL inválido.")


def validate_catalog(data: dict) -> None:
    _mapping(data, "catálogo")
    _keys(data, ("git", "airflow", "database"), "catálogo")
    groups = {}
    for group, section in (("git", "repositories"), ("airflow", "dags"), ("database", "tables")):
        config = _mapping(data.get(group, {}), group)
        _keys(config, (section,), group)
        groups[group] = _mapping(config.get(section, {}), f"{group}.{section}")
    for name, repo in groups["git"].items():
        where = f"git.repositories.{name}"
        _text(name, where)
        _mapping(repo, where)
        _keys(repo, ("path", "writable"), where)
        path = Path(_text(repo.get("path"), where + ".path")).expanduser()
        if not path.is_absolute() or not path.is_dir() or not (path / ".git").exists():
            raise CatalogError(f"{where}.path: informe um caminho absoluto de um repositório Git existente.")
        if type(repo.get("writable", False)) is not bool:
            raise CatalogError(f"{where}.writable: esperado true ou false.")
    for name, dag in groups["airflow"].items():
        where = f"airflow.dags.{name}"
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise CatalogError(f"{where}: ID de DAG inválido.")
        _mapping(dag, where)
        _keys(dag, ("description",), where)
        _text(dag.get("description"), where + ".description")
    for name, table in groups["database"].items():
        where = f"database.tables.{name}"
        validate_sql_identifier(name, where)
        _mapping(table, where)
        _keys(table, ("connection", "schema", "return_columns", "filter_columns", "editable_columns", "column_types"), where)
        if not isinstance(table.get("connection"), str) or table["connection"] not in DB_CONNECTIONS:
            raise CatalogError(f"{where}.connection: conexão não cadastrada.")
        validate_sql_identifier(table.get("schema"), where + ".schema")
        columns = table.get("return_columns")
        if not isinstance(columns, list) or not columns or any(not isinstance(c, str) for c in columns):
            raise CatalogError(f"{where}.return_columns: informe uma lista não vazia de colunas.")
        for column in columns:
            validate_sql_identifier(column, where + ".return_columns")
        if len(columns) != len(set(columns)):
            raise CatalogError(f"{where}.return_columns: colunas duplicadas.")
        for field in ("filter_columns", "editable_columns", "column_types"):
            for column, kind in _mapping(table.get(field, {}), where + "." + field).items():
                validate_sql_identifier(column, where + "." + field)
                if kind not in ("int", "float", "str", "date"):
                    raise CatalogError(f"{where}.{field}.{column}: tipo inválido.")
        for column, kind in table.get("column_types", {}).items():
            for field in ("filter_columns", "editable_columns"):
                declared = table.get(field, {}).get(column)
                if declared is not None and declared != kind:
                    raise CatalogError(f"{where}.{field}.{column}: tipo diverge de column_types.")
        if table.get("editable_columns") and DB_CONNECTIONS[table["connection"]]["dialect"] != "mssql":
            raise CatalogError(f"{where}: escrita disponível apenas para SQL Server.")


def load_catalog(path: Path | None = None) -> dict:
    target = path if path is not None else catalog_path()
    try:
        with target.open("rb") as stream:
            data = tomllib.load(stream)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise CatalogError(f"Não foi possível ler {target}: {error}") from error
    validate_catalog(data)
    return data


def _serialize(data: dict) -> str:
    lines = ["# Recursos locais do Gemini Terminal. Não inclua credenciais."]

    def visit(group, parts):
        if parts:
            lines.append("\n[" + ".".join(json.dumps(p, ensure_ascii=False) for p in parts) + "]")
        for key, value in group.items():
            if not isinstance(value, dict):
                lines.append(f"{json.dumps(key, ensure_ascii=False)} = {json.dumps(value, ensure_ascii=False)}")
        for key, value in group.items():
            if isinstance(value, dict):
                visit(value, [*parts, key])

    visit(data, [])
    return "\n".join(lines) + "\n"


def save_catalog(data: dict, path: Path | None = None) -> None:
    """Valida tudo antes da substituição atômica do arquivo."""
    validate_catalog(data)
    target = path if path is not None else catalog_path()
    content = _serialize(data)
    tomllib.loads(content)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


# Snapshot de inicialização. Erros fecham todas as allowlists.
# TODO: recarregamento explícito e atômico de schemas/tools sem reiniciar.
CATALOG_ERROR = None
try:
    CATALOG = load_catalog()
except CatalogError as error:
    CATALOG = {}
    CATALOG_ERROR = str(error)

TABLES_ALLOWED = {
    name: {
        "connection": table["connection"],
        "schema": table["schema"],
        "colunas_retorno": table["return_columns"],
        "colunas_filtro": table.get("filter_columns", {}),
        "colunas_editaveis": table.get("editable_columns", {}),
    }
    for name, table in CATALOG.get("database", {}).get("tables", {}).items()
}
CHART_TYPES = {"bar", "line"}
GIT_ALLOWED_REPOS = {
    name: {"path": Path(repo["path"]).expanduser().resolve(), "writable": repo.get("writable", False)}
    for name, repo in CATALOG.get("git", {}).get("repositories", {}).items()
}
AIRFLOW_ALLOWED_DAGS = CATALOG.get("airflow", {}).get("dags", {})
