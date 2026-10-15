"""Gera a imagem determinística usada na página inicial do projeto."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.data_analysis import analyze_sheet_data  # noqa: E402

DATASET = PROJECT_ROOT / "examples" / "SampleSuperstore.csv"
OUTPUT = PROJECT_ROOT / "docs" / "assets" / "terminal-demo.svg"


def build_demo(console: Console) -> None:
    result = analyze_sheet_data(
        file_path=str(DATASET),
        operation="sum",
        target_column="Profit",
        group_by="Region",
        sort_ascending=False,
    )

    console.print(
        Panel(
            "[bold bright_yellow]Gemini Terminal[/bold bright_yellow]\n"
            "[dim]Sessão ativa: portfolio-demo[/dim]",
            border_style="bright_yellow",
            box=box.ROUNDED,
        )
    )
    console.print(
        Text.from_markup(
            "[bold cyan]Você:[/bold cyan] No arquivo "
            "[bold]examples/SampleSuperstore.csv[/bold], calcule o Profit total "
            "por Region. Use analyze_sheet_data e ordene do maior para o menor."
        )
    )
    console.print()
    console.print(
        Panel(
            Group(
                Text("• Modelo selecionado: gemini-flash", style="dim"),
                Text("✓ analyze_sheet_data (0.08s)", style="bold green"),
                Text("• Sintetizando resposta", style="dim"),
            ),
            title="Execução",
            border_style="bright_black",
            box=box.ROUNDED,
        )
    )
    console.print(Text("Gemini", style="bold magenta"))
    console.print(Markdown("**Profit total por região:**\n\n" + result))
    console.print(
        Text(
            "gemini-flash · 2 chamadas · tool executada com dados fictícios · cache miss",
            style="dim",
        )
    )


def main() -> None:
    console = Console(
        file=StringIO(),
        record=True,
        width=110,
        color_system="truecolor",
        force_terminal=True,
    )
    build_demo(console)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    console.save_svg(str(OUTPUT), title="Gemini Terminal — demo")
    print(f"Demo gerada em {OUTPUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
