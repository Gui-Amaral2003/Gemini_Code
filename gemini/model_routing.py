"""
Classificação de tools por "posição provável" numa cadeia de function calls,
usada pelo roteamento multi-modelo em GeminiClient.

A classificação em si (ToolRouting.TERMINAL/EXPLORATORY/UNCLASSIFIED) vive
em tools/registry.py, como parte da política de cada tool
(ToolPolicy.routing) — este módulo só consome essa informação e decide se
uma rodada inteira de function calls pode rodar no modelo barato.
"""
from tools import TOOL_POLICIES, ToolRouting

def all_terminal(tool_names: list[str]) -> bool:
    """
    True apenas se todas as tools na lista forem terminais.
    Uma lista vazia, uma tool exploratoria, ou uma tool não catalogada
    em nenhum grupo fazem retornar False (mantém modelo forte)
    """
    if not tool_names:
        return False
    return all(
        (policy := TOOL_POLICIES.get(name)) is not None
        and policy.routing == ToolRouting.TERMINAL
        for name in tool_names
    )