##TODO: 1. Testar tools de excel para planilhas grandes, verificar se o modelo vai chamar a read_sheet e não a preview_sheet 
##TODO: 2. Usar para um caso generico, com o objetivo de testar a search_in_sheet
##TODO: 3. Solicitar dados que não existe, para garantir que o modelo não vai invertar dados
##TODO: 4. Adicionar uma busca por arqruivos mais robusta
##TODO: 5. Testar o analyze_table_data
##TODO: 6. Refinar a instrução sobre quando chamar plot_sheet_data/plot_table_data (evitar que o modelo gere gráfico quando o usuário só queria um número)
##TODO: 7. Adicionar os tests para filesystem, database, pdf_reader e GeminiClient
##TODO: 8. Limpeza de arquivos
##TODO: 9. Prosseguir com a criação dos tests
##TODO 10. Testar economia gerada pelo model_routing
##TODO 11. Permitir escrita no modulo git, não apenas leitura
from pathlib import Path
import logging
from gemini import GeminiClient, ChatSession
from tools.definitions import TOOL_DEFINITIONS
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.status import Status
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
from rich import box

SESSION_ID = 'teste'
PLOTS_DIR = Path("output") / "plots"

# Gradiente clássico do ícone do Gemini (azul -> roxo -> rosa)
GEMINI_BLUE = (66, 133, 244)     # #4285F4
GEMINI_PURPLE = (145, 104, 192)  # #9168C0
GEMINI_PINK = (217, 101, 112)    # #D96570


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _gemini_gradient(t: float) -> str:
    """t entre 0 e 1 -> hex interpolado ao longo do gradiente azul -> roxo -> rosa."""
    if t < 0.5:
        rgb = _lerp_color(GEMINI_BLUE, GEMINI_PURPLE, t / 0.5)
    else:
        rgb = _lerp_color(GEMINI_PURPLE, GEMINI_PINK, (t - 0.5) / 0.5)
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def build_sparkle(size: int = 13) -> Text:
    """
    Desenha o 'sparkle' do Gemini em blocos, com gradiente diagonal
    (azul no canto superior esquerdo -> rosa no canto inferior direito)
    e um rostinho simples (olhos + boca) recortado no meio.
    """
    center = size // 2
    eyes = {(center - 2, center - 2), (center - 2, center + 2)}
    mouth = {(center + 2, c) for c in range(center - 1, center + 2)}

    art = Text()
    for r in range(size):
        for c in range(size):
            d = abs(r - center) + abs(c - center)
            filled = d <= center

            if not filled or (r, c) in eyes or (r, c) in mouth:
                art.append("  ")
                continue

            t = (r + c) / (2 * (size - 1))
            art.append("██", style=_gemini_gradient(t))
        art.append("\n")
    return art
STYLE_USER = "bold cyan"
STYLE_GEMINI = "bold magenta"
STYLE_SYSTEM = "dim"
STYLE_ERROR = "bold red"
STYLE_ACCENT = "bright_yellow"

console = Console()

# Agrupamento só para exibição no /tools — não tem relação com o roteamento multi-modelo (ver gemini/model_routing.py), que classifica por posição provável na cadeia de tool-calling, não por domínio.
TOOL_CATEGORIES = {
    "Arquivos e scripts": ["read_file", "create_file", "run_script"],
    "Banco de dados": ["query_table"],
    "Planilhas": ["list_sheets", "preview_sheet", "read_sheet", "search_in_sheet"],
    "Análise de dados": ["analyze_sheet_data", "analyze_table_data", 'describe_sheet_column', 'describe_table_column'],
    "Gráficos": ["plot_sheet_data", "plot_table_data"],
    "PDF": ["preview_pdf", "read_pdf", "search_in_pdf"],
    "Git": ["git_status", "git_diff_unstaged", "git_diff_staged", "git_log", "git_show", "git_blame"],
}

##Config de log, utilizar a *_VISIBLE para debug e *_HIDDEN para produção, assim conseguimos ver os erros/avisos mesmo com log oculto
##NÃO MUDE NA CONFIG DO LOG, UTILIZE O /logs
GEMINI_LOGGER_NAME = "gemini_client"
LOG_LEVEL_VISIBLE = logging.INFO
LOG_LEVEL_HIDDEN = logging.WARNING  # erros/avisos continuam aparecendo mesmo "oculto"

def main():
    logging.getLogger(GEMINI_LOGGER_NAME).setLevel(LOG_LEVEL_VISIBLE)
    client = GeminiClient(cheap_model = 'gemini-3.5-flash-lite')

    chat = ChatSession(
        client = client,
        session_id = SESSION_ID,
        system_instruction = """
        Você é meu assistente técnico de programação.
        Responda de forma ojetiva e técnica. 
        Mantenha o contexto da conversa

        REGRA SOBRE MÚLTIPLOS ARQUIVOS:
        Se o usuário pedir para processar mais de um arquivo (planilha, PDF ou tabela)
        na mesma solicitação, chame a ferramenta correspondente uma vez para cada
        arquivo, todas na mesma resposta — não processe um arquivo, escreva um
        resumo parcial e espere confirmação para continuar com o próximo.

        REGRA OBRIGATÓRIA sobre cálculos em dados de planilha ou banco:
        Se a pergunta pedir soma, média, contagem, mínimo, máximo, ou total agrupado por
        categoria/região/vendedor/etc., você DEVE chamar a ferramenta analyze_sheet_data
        (planilhas) ou analyze_table_data (banco) e responder com o RESULTADO que ela retornar.

        Isso significa que, para esse tipo de pergunta:
        - É proibido calcular o resultado você mesmo a partir de dados lidos via read_sheet,
        preview_sheet ou query_table.
        - read_sheet/preview_sheet/query_table só servem para exibir linhas/registros ao usuário
        ou para descobrir nomes de colunas — nunca como substituto de analyze_sheet_data/
        analyze_table_data para produzir um resultado agregado.

        REGRA SOBRE GRÁFICOS:
        Só chame plot_sheet_data ou plot_table_data quando o usuário pedir explicitamente
        para ver, gerar ou visualizar um gráfico/plot. Se o usuário só pediu um número, uma
        soma, uma média ou uma tabela, use analyze_sheet_data/analyze_table_data — NUNCA
        chame as ferramentas de plot nesse caso.
        """
    )

    print_banner()

    while True:
        try:
            user_input = Prompt.ask(f"\n[{STYLE_USER}]Você[/{STYLE_USER}]").strip()

            if not user_input:
                continue

            if user_input == "/exit":
                console.print(Panel("See You Space Cowboy...", style=STYLE_SYSTEM, box=box.ROUNDED))
                break

            if user_input == "/help":
                print_help()
                continue

            if user_input == "/history":
                print_history(chat)
                continue

            if user_input == "/clear":
                chat.clear_history()
                console.print(Panel("Contexto limpo.", style=STYLE_SYSTEM, box=box.ROUNDED))
                continue

            if user_input == "/tools" or user_input.startswith("/tools "):
                arg = user_input[len("/tools"):].strip()
                print_tools(arg or None)
                continue

            if user_input == "/tokens":
                print_tokens(client)
                continue

            if user_input == '/logs':
                toggle_logs()
                continue

            with Status("[dim]Gemini está pensando...[/dim]", console=console, spinner="dots"):
                response = chat.send(user_input)

            print_response(response.text)

            if response.generated_files:
                handle_generated_files(response.generated_files)

        except KeyboardInterrupt:
            console.print(Panel("Encerrando...", style=STYLE_SYSTEM, box=box.ROUNDED))
            break

        except Exception as e:
            print_error(str(e))


# --------------------------------------------------------------------------- #
# Renderização
# --------------------------------------------------------------------------- #

def print_banner() -> None:
    console.print(Align.center(build_sparkle()))

    title = Text("Gemini Terminal", style=f"{STYLE_ACCENT} bold")
    body = Text.from_markup(
        f"Sessão ativa: [{STYLE_ACCENT}]{SESSION_ID}[/{STYLE_ACCENT}]\n\n"
        "[bold]Comandos[/bold]\n"
        "  [cyan]/help[/cyan]     mostra os comandos\n"
        "  [cyan]/history[/cyan]  mostra o histórico\n"
        "  [cyan]/clear[/cyan]    limpa o contexto\n"
        "  [cyan]/tools[/cyan]    mostra as ferramentas, /tools <nome> para detalhes\n"
        "  [cyan]/logs[/cyan]     alterna visibilidade dos logs\n"
        "  [cyan]/tokens[/cyan]   mostra consumo\n"
        "  [cyan]/exit[/cyan]     sair"
    )
    console.print(
        Align.center(
            Panel(body, title=title, border_style=STYLE_ACCENT, box=box.ROUNDED, padding=(1, 2))
        )
    )

def print_response(text: str) -> None:
    console.print(
        Panel(
            Markdown(text),
            title=Text("Gemini", style=STYLE_GEMINI),
            title_align="left",
            border_style=STYLE_GEMINI,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def print_error(message: str) -> None:
    console.print(
        Panel(
            message,
            title=Text("Erro", style=STYLE_ERROR),
            title_align="left",
            border_style=STYLE_ERROR,
            box=box.ROUNDED,
        )
    )

def print_help() -> None:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style=f"{STYLE_ACCENT} bold")
    table.add_column()
    table.add_row("/help", "Mostra esta ajuda")
    table.add_row("/history", "Mostra o histórico local")
    table.add_row("/clear", "Limpa a conversa")
    table.add_row("/tokens", "Mostra consumo de tokens")
    table.add_row("/tools", "Lista as ferramentas disponíveis, por categoria")
    table.add_row("/logs", "Alterna visibilidade dos logs (visível por padrão)")
    table.add_row("/tools <nome>", "Mostra a descrição completa de uma ferramenta")
    table.add_row("/exit", "Encerra o programa")

    conteudo = Columns([build_sparkle(), table], padding=(0, 4), equal=False, expand=False)

    console.print(Panel(conteudo, title="Comandos", border_style=STYLE_ACCENT, box=box.ROUNDED))

def print_tokens(client: GeminiClient) -> None:
    summary = client.session_summary()

    table = Table(box=box.SIMPLE_HEAVY, show_header=False)
    table.add_column(style="bold")
    table.add_column(justify="right", style=STYLE_ACCENT)

    labels = {
        "calls": "Chamadas de API",
        "cache_hits": "Cache hits",
        "input_tokens": "Tokens de entrada",
        "output_tokens": "Tokens de saída",
        "total_tokens": "Total de tokens",
    }
    for key, label in labels.items():
        table.add_row(label, str(summary.get(key, 0)))

    console.print(Panel(table, title="Consumo da sessão", border_style=STYLE_ACCENT, box=box.ROUNDED))

def _short_description(full_description: str, max_chars: int = 80) -> str:
    """Primeira frase da descrição (a mesma usada no TOOL_DEFINITIONS enviado
    ao Gemini), cortada em max_chars. Evita duplicar texto — só resume."""
    first_line = " ".join(full_description.split())  # colapsa espaços/quebras
    first_sentence = first_line.split(". ")[0].rstrip(".")
 
    if len(first_sentence) > max_chars:
        return first_sentence[:max_chars].rstrip() + "..."
    return first_sentence + "."

def print_tools(tool_name: str | None = None) -> None:
    definitions_by_name = {d["name"]: d for d in TOOL_DEFINITIONS}
 
    # /tools <nome> — mostra a descrição completa de uma ferramenta específica
    if tool_name:
        definition = definitions_by_name.get(tool_name)
        if not definition:
            print_error(
                f"Ferramenta '{tool_name}' não encontrada. "
                f"Use /tools para ver a lista completa."
            )
            return
 
        console.print(
            Panel(
                definition["description"].strip(),
                title=Text(tool_name, style=f"{STYLE_ACCENT} bold"),
                title_align="left",
                border_style=STYLE_ACCENT,
                box=box.ROUNDED,
            )
        )
        return
 
    # /tools — visão geral compacta, agrupada por categoria
    categorized = {name for names in TOOL_CATEGORIES.values() for name in names}
    uncategorized = [name for name in definitions_by_name if name not in categorized]
 
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2), expand=True)
    table.add_column(style=f"{STYLE_ACCENT} bold", no_wrap=True, ratio=1)
    table.add_column(ratio=3)
 
    groups = dict(TOOL_CATEGORIES)
    if uncategorized:
        groups["Outras"] = uncategorized
 
    first_group = True
    for category, names in groups.items():
        if not first_group:
            table.add_row("", "")
        first_group = False
 
        table.add_row(Text(category.upper(), style="bold underline"), "")
 
        for name in names:
            definition = definitions_by_name.get(name)
            if not definition:
                continue
            table.add_row(f"  {name}", _short_description(definition["description"]))
 
    console.print(
        Panel(
            table,
            title="Ferramentas disponíveis",
            subtitle="[dim]/tools <nome> para detalhes[/dim]",
            border_style=STYLE_ACCENT,
            box=box.ROUNDED,
        )
    )

def toggle_logs() -> None:
    gemini_logger = logging.getLogger(GEMINI_LOGGER_NAME)
    currently_visible = gemini_logger.level <= LOG_LEVEL_VISIBLE
 
    if currently_visible:
        gemini_logger.setLevel(LOG_LEVEL_HIDDEN)
        console.print(Panel("Logs ocultos. (Erros e avisos continuam aparecendo.)", style=STYLE_SYSTEM, box=box.ROUNDED))
    else:
        gemini_logger.setLevel(LOG_LEVEL_VISIBLE)
        console.print(Panel("Logs visíveis.", style=STYLE_SYSTEM, box=box.ROUNDED))

def print_history(chat: ChatSession) -> None:
    history = chat.get_history()

    if not history:
        console.print(Panel("Histórico vazio.", style=STYLE_SYSTEM, box=box.ROUNDED))
        return

    for message in history:
        if message.role == "user":
            console.print(
                Panel(
                    message.text,
                    title=Text("Você", style=STYLE_USER),
                    title_align="left",
                    border_style=STYLE_USER,
                    box=box.ROUNDED,
                )
            )
        else:
            print_response(message.text)


def handle_generated_files(files: list[Path]) -> None:
    """Pergunta ao usuário, para cada arquivo gerado nesta resposta (ex: gráficos),
    se ele quer manter (move para PLOTS_DIR) ou descartar (deleta do staging)."""
    for file_path in files:
        if not file_path.exists():
            continue

        manter = Confirm.ask(
            f"Salvar o gráfico gerado ([{STYLE_ACCENT}]{file_path.name}[/{STYLE_ACCENT}])?",
            default=False,
        )

        if manter:
            PLOTS_DIR.mkdir(parents=True, exist_ok=True)
            destino = PLOTS_DIR / file_path.name
            file_path.replace(destino)
            console.print(f"[green]Salvo em:[/green] {destino}")
        else:
            try:
                file_path.unlink()
            except OSError as e:
                print_error(f"Não consegui remover o arquivo temporário {file_path}: {e}")
            else:
                console.print("[dim]Descartado.[/dim]")


if __name__ == "__main__":
    main()