"""
Catálogo central de variáveis de ambiente configuráveis via /config (e
--config, usado antes de o GeminiClient existir). Fonte única de verdade
sobre quais variáveis existem, a que grupo pertencem, se são secretas e
como são persistidas no .env.

Deliberadamente sem dependência de terminal (Rich/prompt_toolkit) — só
lida com o catálogo e leitura/escrita do .env. A camada de interação
(wizard) fica em gemini/config_wizard.py, mesma separação de
tools/confirmation.py (callback de pergunta) vs tools/*.py (regra).
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from dotenv import dotenv_values, set_key, unset_key
from app_environment import ENV_PATH, SYSTEM_ENV


@dataclass(frozen=True)
class EnvSetting:
    key: str
    label: str
    group: str
    secret: bool = False
    required: bool = False
    description: str = ""
    example: str = ""
    validator: Optional[Callable[[str], Optional[str]]] = None


def _validate_port(value: str) -> Optional[str]:
    if not value.isdigit():
        return "Porta deve ser um número inteiro."
    return None


ENV_SETTINGS: dict[str, EnvSetting] = {
    "GEMINI_CATALOG_PATH": EnvSetting(
        key="GEMINI_CATALOG_PATH",
        label="Arquivo de recursos (catalogs.toml)",
        group="Aplicativo",
        description="Caminho opcional do catálogo local de tabelas, Git e Airflow.",
    ),
    "GEMINI_DATA_DIR": EnvSetting(
        key="GEMINI_DATA_DIR",
        label="Diretório de dados",
        group="Aplicativo",
        description="Local opcional para sessões, cache, quota e logs.",
        example="C:\\Users\\usuario\\GeminiTerminal",
    ),
    "GEMINI_API_KEY": EnvSetting(
        key="GEMINI_API_KEY",
        label="Gemini API key",
        group="Gemini",
        secret=True,
        required=True,
        description="Chave usada para autenticar na API do Gemini.",
        example="AIza...",
    ),
    "DB_CONN_STRING": EnvSetting(
        key="DB_CONN_STRING",
        label="Connection string",
        group="SQL Server",
        secret=True,
        description="Connection string completa usada pelo pyodbc/SQLAlchemy.",
    ),
    "HIVE_HOST": EnvSetting(key="HIVE_HOST", label="Host", group="Hive"),
    "HIVE_PORT": EnvSetting(key="HIVE_PORT", label="Porta", group="Hive", example="10000", validator=_validate_port),
    "HIVE_DATABASE": EnvSetting(key="HIVE_DATABASE", label="Database", group="Hive"),
    "HIVE_USER": EnvSetting(key="HIVE_USER", label="Usuário", group="Hive"),
    "HIVE_PASSWORD": EnvSetting(key="HIVE_PASSWORD", label="Senha", group="Hive", secret=True),
    "AIRFLOW_API_URL": EnvSetting(key="AIRFLOW_API_URL", label="URL da API", group="Airflow", example="http://sua-vm:8080"),
    "AIRFLOW_USERNAME": EnvSetting(key="AIRFLOW_USERNAME", label="Usuário", group="Airflow"),
    "AIRFLOW_PASSWORD": EnvSetting(key="AIRFLOW_PASSWORD", label="Senha", group="Airflow", secret=True),
}

GROUP_ORDER = ["Aplicativo", "Gemini", "SQL Server", "Hive", "Airflow"]


def groups() -> dict[str, list[EnvSetting]]:
    """Agrupa ENV_SETTINGS por grupo, respeitando GROUP_ORDER."""
    grouped: dict[str, list[EnvSetting]] = {name: [] for name in GROUP_ORDER}
    for setting in ENV_SETTINGS.values():
        grouped.setdefault(setting.group, []).append(setting)
    return {name: settings for name, settings in grouped.items() if settings}


def load_env_status(path: Optional[Path] = None) -> dict[str, str]:
    """
    Sem path explícito, lê o arquivo global com os overrides do ambiente.
    Um path explícito consulta só o arquivo, útil para edição/migração.
    Arquivo inexistente é aceito no primeiro --config.
    """
    target = path if path is not None else ENV_PATH
    values = {
        key: (value or "") for key, value in dotenv_values(target).items()
    } if target.exists() else {}
    if path is None:
        values.update({key: SYSTEM_ENV[key] for key in ENV_SETTINGS if key in SYSTEM_ENV})
    return values


def is_configured(key: str, status: Optional[dict[str, str]] = None, path: Optional[Path] = None) -> bool:
    status = status if status is not None else load_env_status(path)
    return bool(status.get(key))


def update_env_value(key: str, value: str, path: Optional[Path] = None) -> None:
    """Grava/atualiza uma variável no .env, preservando o restante do arquivo."""
    target = path if path is not None else ENV_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch(exist_ok=True)
    set_key(dotenv_path=str(target), key_to_set=key, value_to_set=value, quote_mode="always")


def delete_env_value(key: str, path: Optional[Path] = None) -> None:
    """
    Remove uma variável do arquivo preservando outras entradas e comentários.
    Não altera variáveis herdadas do ambiente do processo.
    """
    target = path if path is not None else ENV_PATH
    if not target.exists():
        return
    unset_key(str(target), key)


def missing_required(path: Optional[Path] = None) -> list[EnvSetting]:
    status = load_env_status(path)
    return [s for s in ENV_SETTINGS.values() if s.required and not is_configured(s.key, status)]
