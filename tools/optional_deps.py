import importlib
from importlib.util import find_spec
from typing import Callable

PACKAGE = "gemini-code-terminal"
REPO = "git+https://github.com/Gui-Amaral2003/Gemini_Code.git"

# extra -> [(módulo importável, nome no pip)]
EXTRAS = {
    "data": [("pandas", "pandas"), ("openpyxl", "openpyxl")],
    "sqlserver": [("sqlalchemy", "sqlalchemy"), ("pyodbc", "pyodbc")],
    "hive": [("sqlalchemy", "sqlalchemy"), ("pyhive", "pyhive"), ("thrift", "thrift"),
             ("thrift_sasl", "thrift-sasl"), ("pure_sasl", "pure-sasl")],
    "charts": [("matplotlib", "matplotlib"), ("plotext", "plotext")],
    "pdf": [("pypdf", "pypdf")],
    "airflow": [("requests", "requests")],
}


ModuleFinder = Callable[[str], object]


def install_command(extra: str) -> str:
    _get_dependencies(extra)
    return f'pipx install --force "{PACKAGE}[{extra}] @ {REPO}"'


class MissingDependencyError(ImportError):
    def __init__(self, extra: str, missing: list[str]):
        super().__init__(
            f"A integração '{extra}' não está instalada (faltando: {', '.join(missing)}). "
            f"Reinstale incluindo o extra: {install_command(extra)}"
        )


def _get_dependencies(extra: str) -> list[tuple[str, str]]:
    try:
        return EXTRAS[extra]
    except KeyError as error:
        raise ValueError(f"Extra desconhecido: {extra}") from error


def missing_dependencies(
    extra: str,
    finder: ModuleFinder = find_spec,
) -> list[str]:
    """Retorna os nomes de distribuição ausentes sem importar os pacotes."""
    missing = []
    for module, pip_name in _get_dependencies(extra):
        try:
            available = finder(module) is not None
        except (ImportError, AttributeError, ValueError):
            available = False
        if not available:
            missing.append(pip_name)
    return missing


def is_available(extra: str, finder: ModuleFinder = find_spec) -> bool:
    return not missing_dependencies(extra, finder)


def require(extra: str) -> None:
    """Verifica se todas as dependências de um extra estão instaladas."""
    missing = []
    for module, pip_name in _get_dependencies(extra):
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(pip_name)

    if missing:
        raise MissingDependencyError(extra, missing)
