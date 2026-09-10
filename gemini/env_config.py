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
from dotenv import dotenv_values, set_key

ENV_PATH = Path(".env")

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

GROUP_ORDER = ["Gemini", "SQL Server", "Hive", "Airflow"]


def groups() -> dict[str, list[EnvSetting]]:
    """Agrupa ENV_SETTINGS por grupo, respeitando GROUP_ORDER."""
    grouped: dict[str, list[EnvSetting]] = {name: [] for name in GROUP_ORDER}
    for setting in ENV_SETTINGS.values():
        grouped.setdefault(setting.group, []).append(setting)
    return {name: settings for name, settings in grouped.items() if settings}


def load_env_status(path: Path = ENV_PATH) -> dict[str, str]:
    """
    Lê o .env em disco. Nunca lança se o arquivo não existir — este
    módulo também é usado antes de o .env existir (primeiro --config).
    """
    if not path.exists():
        return {}
    return {key: (value or "") for key, value in dotenv_values(path).items()}


def is_configured(key: str, status: Optional[dict[str, str]] = None, path: Path = ENV_PATH) -> bool:
    status = status if status is not None else load_env_status(path)
    return bool(status.get(key))


def update_env_value(key: str, value: str, path: Path = ENV_PATH) -> None:
    """Grava/atualiza uma variável no .env, preservando o restante do arquivo."""
    path.touch(exist_ok=True)
    set_key(dotenv_path=str(path), key_to_set=key, value_to_set=value, quote_mode="always")


def delete_env_value(key: str, path: Path = ENV_PATH) -> None:
    """
    Remove uma variável do .env. Reescreve o arquivo (mantendo as demais
    entradas na mesma ordem) em vez de confiar em um "unset" da lib —
    setar valor vazio deixaria a chave presente, comportamento diferente
    de "não configurado".
    """
    if not path.exists():
        return

    current = dotenv_values(path)
    if key not in current:
        return

    lines = [f'{k}="{v or ""}"' for k, v in current.items() if k != key]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def missing_required(path: Path = ENV_PATH) -> list[EnvSetting]:
    status = load_env_status(path)
    return [s for s in ENV_SETTINGS.values() if s.required and not is_configured(s.key, status)]