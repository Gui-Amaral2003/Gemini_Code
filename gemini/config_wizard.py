"""
Camada de apresentação (Rich) sobre gemini/env_config.py. Acessível via
/config no terminal ou --config na CLI, antes de existir GeminiClient —
por isso este módulo não importa gemini.client.
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
    is_configured,
    update_env_value,
)

STYLE_ACCENT = "bright_yellow"
STYLE_OK = "bold green"
STYLE_MISSING = "bold red"
STYLE_SYSTEM = "dim"


def _status_table(console: Console) -> None:
    status = load_env_status()

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2), expand=True)
    table.add_column(style="bold", ratio=1)
    table.add_column(ratio=1)

    first = True
    for group_name, settings in groups().items():
        if not first:
            table.add_row("", "")
        first = False

        table.add_row(Text(group_name.upper(), style="bold underline"), "")
        for setting in settings:
            configured = is_configured(setting.key, status)
            marker = (
                Text("✓ Configurado", style=STYLE_OK)
                if configured else
                Text("✗ Não configurado", style=STYLE_MISSING)
            )
            table.add_row(f"  {setting.label}", marker)

    console.print(
        Panel(
            table,
            title="Configuração",
            subtitle=f"[dim]{ENV_PATH}[/dim]",
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