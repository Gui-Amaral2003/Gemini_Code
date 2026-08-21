"""
Classificação de tools por "posição provável" numa cadeia de function calls,
usada pelo roteamento multi-modelo em GeminiClient.
 
TERMINAL_TOOLS: tools que tipicamente encerram uma cadeia de tool-calling —
    já devolvem um resultado processado/filtrado (agregação, gráfico, busca
    pontual), então o próximo passo natural é sintetizar a resposta final.
    Candidatas a rodar com o modelo mais barato.
 
EXPLORATORY_TOOLS: tools que tipicamente precedem outra chamada de tool —
    exploram estrutura ou trazem dados brutos (preview, listagem, leitura
    paginada). Mantêm o modelo mais forte, porque a próxima decisão ainda
    pode ser "qual tool chamar em seguida".
 
Se uma rodada de function_calls misturar tools dos dois grupos, ou incluir
qualquer tool não catalogada aqui, o roteamento é conservador por padrão
(mantém o modelo forte) — ver all_terminal().
"""

TERMINAL_TOOLS = {
    "analyze_sheet_data",
    "analyze_table_data",
    "plot_sheet_data",
    "plot_table_data",
    "search_in_pdf",
    "search_in_sheet",
}
 
EXPLORATORY_TOOLS = {
    "read_file",
    "query_table",
    "list_sheets",
    "preview_sheet",
    "read_sheet",
    "preview_pdf",
    "read_pdf",
}

def all_terminal(tool_names: list[str]) -> bool:
    """
    True apenas se todas as tools na lista forem terminais.
    Uma lista vazia, uma tool exploratoria, ou uma tool não catalogada
    em nenhum grupo fazem retornar False (mantém modelo forte)
    """
    if not tool_names:
        return False
    return all(tool_name in TERMINAL_TOOLS for tool_name in tool_names)