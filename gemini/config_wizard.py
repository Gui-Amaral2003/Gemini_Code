"""
Camada de apresentação (Rich) sobre env_config.py e config_checks.py.
Acessível via /config no terminal ou --config na CLI, antes de existir
GeminiClient — por isso este módulo não importa gemini.client.
"""
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich import box

from .env_config import (
    ENV_PATH,
    groups,
    load_env_status,
    update_env_value,
)
from .config_checks import CheckStatus, ConfigCheck, run_local_checks

STYLE_ACCENT = "bright_yellow"
STYLE_OK = "bold green"
STYLE_MISSING = "bold red"
STYLE_WARNING = "bold yellow"
STYLE_SKIPPED = "dim"
STYLE_SYSTEM = "dim"


_STATUS_PRESENTATION = {
    CheckStatus.OK: ("[OK]", STYLE_OK),
    CheckStatus.WARNING: ("[!]", STYLE_WARNING),
    CheckStatus.ERROR: ("[X]", STYLE_MISSING),
    CheckStatus.SKIPPED: ("[-]", STYLE_SKIPPED),
}


def _status_table(console: Console, checks: Optional[list[ConfigCheck]] = None) -> None:
    checks = checks if checks is not None else run_local_checks()

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2), expand=True)
    table.add_column(style="bold", ratio=1)
    table.add_column(ratio=3)

    first = True
    group_names = list(dict.fromkeys(check.group for check in checks))
    for group_name in group_names:
        if not first:
            table.add_row("", "")
        first = False

        table.add_row(Text(group_name.upper(), style="bold underline"), "")
        for check in (item for item in checks if item.group == group_name):
            marker, style = _STATUS_PRESENTATION[check.status]
            message = Text(f"{marker} {check.message}", style=style)
            if check.remediation:
                message.append(f"\nComo corrigir: {check.remediation}", style=STYLE_SYSTEM)
            table.add_row(f"  {check.name}", message)

    errors = sum(check.status is CheckStatus.ERROR for check in checks)
    warnings = sum(check.status is CheckStatus.WARNING for check in checks)
    summary = f"{errors} erro(s) · {warnings} aviso(s) · diagnóstico local (sem rede)"

    console.print(
        Panel(
            table,
            title="Configuração",
            subtitle=f"[dim]{ENV_PATH} · {summary}[/dim]",
            border_style=STYLE_ACCENT,
            box=box.ROUNDED,
        )
    )


def show_status(console: Optional[Console] = None) -> None:
    show = console or Console()
    _status_table(show)


def _edit_setting(console: Console, setting, status: dict[str, str]) -> None:
    current_value = status.get(setting.key, "")
    hint = " [dim](Enter para manter o valor atual)[/dim]" if current_value else ""

    prompt_label = setting.label
    if setting.example:
        prompt_label += f" [dim](ex: {setting.example})[/dim]"

    while True:
        new_value = Prompt.ask(
            f"{prompt_label}{hint}",
            password=setting.secret,
            default="",
            show_default=False,
        )

        if not new_value:
            if current_value:
                return  # manteve o valor existente
            if setting.required:
                console.print(Panel(f"{setting.label} é obrigatório.", style=STYLE_MISSING, box=box.ROUNDED))
                continue
            return  # opcional, deixou vazio

        if setting.validator:
            error = setting.validator(new_value)
            if error:
                console.print(Panel(error, style=STYLE_MISSING, box=box.ROUNDED))
                continue

        update_env_value(setting.key, new_value)
        console.print(Panel(f"{setting.label} salvo.", style=STYLE_OK, box=box.ROUNDED))
        return


def _edit_group(console: Console, group_name: str, settings: list) -> None:
    status = load_env_status()
    console.print(Panel(f"Grupo: {group_name}", style=STYLE_ACCENT, box=box.ROUNDED))
    for setting in settings:
        _edit_setting(console, setting, status)
        status = load_env_status()  # recarrega para refletir o que acabou de ser salvo


def run_wizard(console: Optional[Console] = None, only_groups: Optional[list[str]] = None) -> None:
    """
    Assistente interativo por grupo. only_groups restringe os grupos
    exibidos — usado no arranque sem GEMINI_API_KEY, para não empurrar
    configuração de SQL Server/Hive/Airflow em cima de quem só quer
    começar a usar o terminal.
    """
    run = console or Console()
    available = {
        name: settings for name, settings in groups().items()
        if not only_groups or name in only_groups
    }

    if not available:
        run.print(Panel("Nenhum grupo disponível para configurar.", style=STYLE_SYSTEM, box=box.ROUNDED))
        return

    while True:
        show_status(run)

        options = list(available.keys())
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column()
        for i, name in enumerate(options, start=1):
            table.add_row(f"[{STYLE_ACCENT}][{i}][/{STYLE_ACCENT}] {name}")
        table.add_row(f"[{STYLE_ACCENT}][0][/{STYLE_ACCENT}] Sair")
        run.print(table)

        choice = Prompt.ask("Grupo para configurar", default="0")
        if choice == "0" or not choice.strip():
            break

        try:
            index = int(choice) - 1
            if not (0 <= index < len(options)):
                raise ValueError
        except ValueError:
            run.print(Panel("Opção inválida.", style=STYLE_MISSING, box=box.ROUNDED))
            continue

        _edit_group(run, options[index], available[options[index]])

    run.print(
        Panel(
            f"Configuração salva em {ENV_PATH}.\n\n"
            "Reinicie o terminal para que todas as alterações tenham efeito.",
            style=STYLE_ACCENT,
            box=box.ROUNDED,
        )
    )
