# TODO: adicionar /config test com confirmação explícita para validar Gemini, SQL Server, Hive e Airflow sem misturar chamadas externas ao diagnostico local.
# TODO: permitir exportar um relatório sanitizado, sem segredos, hosts internos, headers HTTP, connection strings, prompts ou caminhos pessoais.
# TODO: avaliar reparos assistidos apenas para ações locais e reversíveis; nunca corrigir credenciais, conexões ou permissões automaticamente.

"""Diagnósticos locais e sem efeitos colaterais para o comando /config."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from .env_config import load_env_status


class CheckStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ConfigCheck:
    group: str
    name: str
    status: CheckStatus
    message: str
    remediation: Optional[str] = None


DependencyFinder = Callable[[str], object]


def _configured(status: dict[str, str], key: str) -> bool:
    return bool(status.get(key, "").strip())


def _dependency_check(
    group: str,
    display_name: str,
    module_name: str,
    finder: DependencyFinder,
) -> ConfigCheck:
    try:
        available = finder(module_name) is not None
    except (ImportError, AttributeError, ValueError):
        available = False
    return ConfigCheck(
        group=group,
        name=display_name,
        status=CheckStatus.OK if available else CheckStatus.ERROR,
        message="Dependência disponível." if available else "Dependência não instalada.",
        remediation=None if available else f"Instale a dependência '{display_name}'.",
    )


def _check_gemini(status: dict[str, str], finder: DependencyFinder) -> list[ConfigCheck]:
    value = status.get("GEMINI_API_KEY", "").strip()
    checks = [_dependency_check("Gemini", "google-genai", "google.genai", finder)]
    if not value:
        checks.insert(0, ConfigCheck(
            "Gemini", "API key", CheckStatus.ERROR,
            "GEMINI_API_KEY não configurada.",
            "Use /config edit para informar a chave.",
        ))
    elif value.casefold() in {"sua_chave", "sua_chave_aqui", "your_key", "changeme"}:
        checks.insert(0, ConfigCheck(
            "Gemini", "API key", CheckStatus.ERROR,
            "GEMINI_API_KEY ainda contém um valor de exemplo.",
            "Use /config edit para informar uma chave real.",
        ))
    else:
        checks.insert(0, ConfigCheck(
            "Gemini", "API key", CheckStatus.OK,
            "Configurada; validade externa não testada.",
        ))
    return checks


def _check_sql_server(status: dict[str, str], finder: DependencyFinder) -> list[ConfigCheck]:
    if not _configured(status, "DB_CONN_STRING"):
        return [ConfigCheck(
            "SQL Server", "Integração", CheckStatus.SKIPPED,
            "Opcional e não configurada.",
        )]
    return [
        ConfigCheck(
            "SQL Server", "Connection string", CheckStatus.OK,
            "Configurada; conexão externa não testada.",
        ),
        _dependency_check("SQL Server", "pyodbc", "pyodbc", finder),
        _dependency_check("SQL Server", "SQLAlchemy", "sqlalchemy", finder),
    ]


def _check_hive(status: dict[str, str], finder: DependencyFinder) -> list[ConfigCheck]:
    keys = ("HIVE_HOST", "HIVE_PORT", "HIVE_DATABASE", "HIVE_USER", "HIVE_PASSWORD")
    # A porta pode existir como default no .env.example sem ativar a integracao.
    activating_keys = ("HIVE_HOST", "HIVE_DATABASE", "HIVE_USER", "HIVE_PASSWORD")
    if not any(_configured(status, key) for key in activating_keys):
        return [ConfigCheck("Hive", "Integração", CheckStatus.SKIPPED, "Opcional e não configurada.")]

    missing = [key for key in keys if not _configured(status, key)]
    checks: list[ConfigCheck] = []
    if missing:
        checks.append(ConfigCheck(
            "Hive", "Variáveis", CheckStatus.ERROR,
            "Configuração incompleta: " + ", ".join(missing) + ".",
            "Use /config edit para preencher as variáveis ausentes.",
        ))
    else:
        checks.append(ConfigCheck(
            "Hive", "Variáveis", CheckStatus.OK,
            "Configuração completa; conexão externa não testada.",
        ))

    port = status.get("HIVE_PORT", "").strip()
    if port and (not port.isdigit() or not 1 <= int(port) <= 65535):
        checks.append(ConfigCheck(
            "Hive", "Porta", CheckStatus.ERROR,
            "HIVE_PORT deve ser um número entre 1 e 65535.",
        ))
    elif port:
        checks.append(ConfigCheck("Hive", "Porta", CheckStatus.OK, "Porta válida localmente."))

    checks.extend([
        _dependency_check("Hive", "PyHive", "pyhive", finder),
        _dependency_check("Hive", "thrift", "thrift", finder),
    ])
    return checks


def _check_airflow(status: dict[str, str], finder: DependencyFinder) -> list[ConfigCheck]:
    keys = ("AIRFLOW_API_URL", "AIRFLOW_USERNAME", "AIRFLOW_PASSWORD")
    if not any(_configured(status, key) for key in keys):
        return [ConfigCheck("Airflow", "Integração", CheckStatus.SKIPPED, "Opcional e não configurada.")]

    missing = [key for key in keys if not _configured(status, key)]
    checks: list[ConfigCheck] = []
    if missing:
        checks.append(ConfigCheck(
            "Airflow", "Variáveis", CheckStatus.ERROR,
            "Configuração incompleta: " + ", ".join(missing) + ".",
            "Use /config edit para preencher as variáveis ausentes.",
        ))
    else:
        checks.append(ConfigCheck(
            "Airflow", "Variáveis", CheckStatus.OK,
            "Configuração completa; autenticação externa não testada.",
        ))

    raw_url = status.get("AIRFLOW_API_URL", "").strip()
    if raw_url:
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            checks.append(ConfigCheck(
                "Airflow", "URL", CheckStatus.ERROR,
                "AIRFLOW_API_URL deve ser uma URL HTTP ou HTTPS válida.",
            ))
        elif parsed.scheme == "http":
            checks.append(ConfigCheck(
                "Airflow", "URL", CheckStatus.WARNING,
                "URL válida, mas usa HTTP sem criptografia.",
                "Prefira HTTPS quando o servidor oferecer suporte.",
            ))
        else:
            checks.append(ConfigCheck("Airflow", "URL", CheckStatus.OK, "URL válida localmente."))
    checks.append(_dependency_check("Airflow", "requests", "requests", finder))
    return checks


def _check_tools() -> list[ConfigCheck]:
    try:
        from tools import TOOL_DEFINITIONS, TOOL_POLICIES

        definition_names = {definition["name"] for definition in TOOL_DEFINITIONS}
        policy_names = set(TOOL_POLICIES)
        if definition_names != policy_names:
            return [ConfigCheck(
                "Sistema local", "Tools", CheckStatus.ERROR,
                "Definições e políticas de tools estão divergentes.",
            )]
        return [ConfigCheck(
            "Sistema local", "Tools", CheckStatus.OK,
            f"{len(policy_names)} tools registradas e consistentes.",
        )]
    except Exception as error:
        return [ConfigCheck(
            "Sistema local", "Tools", CheckStatus.ERROR,
            f"Falha ao validar o catálogo: {type(error).__name__}.",
            "Consulte os logs da inicialização para ver o erro completo.",
        )]


def _check_output_directory(output_dir: Path = Path("output")) -> ConfigCheck:
    target = output_dir if output_dir.exists() else output_dir.parent
    if target.exists() and os.access(target, os.W_OK):
        message = "Diretório de saída gravável." if output_dir.exists() else "Diretório de saída pode ser criado."
        return ConfigCheck("Sistema local", "Output", CheckStatus.OK, message)
    return ConfigCheck(
        "Sistema local", "Output", CheckStatus.ERROR,
        "Diretório de saída não está acessível para escrita.",
    )


def run_local_checks(
    status: Optional[dict[str, str]] = None,
    dependency_finder: DependencyFinder = importlib.util.find_spec,
    output_dir: Path = Path("output"),
) -> list[ConfigCheck]:
    """Executa apenas verificações locais; não abre conexões nem altera arquivos."""
    current = status if status is not None else load_env_status()
    checks = [
        *_check_gemini(current, dependency_finder),
        *_check_sql_server(current, dependency_finder),
        *_check_hive(current, dependency_finder),
        *_check_airflow(current, dependency_finder),
        *_check_tools(),
        _check_output_directory(output_dir),
    ]
    return checks


