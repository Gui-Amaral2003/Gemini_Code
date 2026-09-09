"""
Catálogo central de tools: registra, para cada ferramenta exposta ao Gemini,
a função Python que a executa e as políticas de execução (confirmação,
timeout, se gera arquivo, roteamento de modelo).

Esta é a ÚNICA fonte de verdade sobre comportamento de execução de tools —
antes desse arquivo, essa informação estava espalhada em quatro lugares
(TOOLS, TERMINAL_TOOLS/EXPLORATORY_TOOLS em gemini/model_routing.py,
PLOT_TOOL_NAMES e TOOLS_REQUIRING_CONFIRMATION em gemini/client.py), com
risco de divergência ao adicionar/mudar uma tool.

tools/definitions.py continua separado de propósito: é sobre o SCHEMA
(formato JSON enviado ao Gemini), natureza diferente de política de
execução. A consistência entre os dois é garantida por _assert_consistency,
que falha no import se os nomes de tool divergirem entre TOOL_DEFINITIONS
e TOOL_POLICIES.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from .filesystem import read_file, create_file
from .script_runner import run_script
from .spreadsheet import (
    list_sheets,
    preview_sheet,
    read_sheet,
    search_in_sheet,
)
from .database import query_table
from .data_analysis import (
    analyze_sheet_data,
    analyze_table_data,
    plot_sheet_data,
    plot_table_data,
    describe_sheet_column,
    describe_table_column
)
from .pdf_reader import preview_pdf, read_pdf, search_in_pdf
from .git_tool import (
    git_status,
    git_diff_unstaged,
    git_diff_staged,
    git_log,
    git_show,
    git_blame,
    edit_repo_file
)
from .write_operations import update_table, delete_table_rows
from .airflow_tool import (
    list_dags,
    get_dag_runs,
    get_task_instances,
    get_task_log,
)

from .definitions import TOOL_DEFINITIONS

class ToolRouting(Enum):
    """Ver gemini/model_routing.py para o racional completo do roteamento multi-modelo"""
    TERMINAL = 'terminal' # candidata a modelo barato após a rodada
    EXPLORATORY = 'exploratory' # mantém modelo forte — próxima decisão pode ser outra tool
    UNCLASSIFIED = 'unclassified' # default — conservador, mantém modelo forte

@dataclass(frozen = True)
class ToolPolicy:
    name: str
    function: Callable
    requires_confirmation: bool = False
    generate_file: bool = False
    routing: ToolRouting = ToolRouting.UNCLASSIFIED
    # Override do timeout genérico de execução (MAX_TOOL_EXEC_SECONDS, em
    # gemini/config.py). None usa o default global. Este campo deve permanecer
    # None quando requires_confirmation=True: essas tools não entram no wrapper
    # de timeout porque aguardam interação humana dentro da própria função.
    timeout_seconds: Optional[float] = None

TOOL_POLICIES: dict[str, ToolPolicy] = {
    "read_file": ToolPolicy("read_file", read_file, routing=ToolRouting.EXPLORATORY),
    "create_file": ToolPolicy("create_file", create_file, requires_confirmation=True, routing=ToolRouting.EXPLORATORY),
    "run_script": ToolPolicy("run_script", run_script, requires_confirmation=True, routing=ToolRouting.EXPLORATORY),
    "query_table": ToolPolicy("query_table", query_table, routing=ToolRouting.EXPLORATORY),
    "update_table": ToolPolicy("update_table", update_table, requires_confirmation=True, routing=ToolRouting.TERMINAL),
    "delete_table_rows": ToolPolicy("delete_table_rows", delete_table_rows, requires_confirmation=True, routing=ToolRouting.TERMINAL),
    "list_sheets": ToolPolicy("list_sheets", list_sheets, routing=ToolRouting.EXPLORATORY),
    "preview_sheet": ToolPolicy("preview_sheet", preview_sheet, routing=ToolRouting.EXPLORATORY),
    "read_sheet": ToolPolicy("read_sheet", read_sheet, routing=ToolRouting.EXPLORATORY),
    "search_in_sheet": ToolPolicy("search_in_sheet", search_in_sheet, routing=ToolRouting.TERMINAL),
    "analyze_sheet_data": ToolPolicy("analyze_sheet_data", analyze_sheet_data, routing=ToolRouting.TERMINAL),
    "analyze_table_data": ToolPolicy("analyze_table_data", analyze_table_data, routing=ToolRouting.TERMINAL),
    "plot_sheet_data": ToolPolicy("plot_sheet_data", plot_sheet_data, generate_file=True, routing=ToolRouting.TERMINAL),
    "plot_table_data": ToolPolicy("plot_table_data", plot_table_data, generate_file=True, routing=ToolRouting.TERMINAL),
    "describe_sheet_column": ToolPolicy("describe_sheet_column", describe_sheet_column, routing=ToolRouting.EXPLORATORY),
    "describe_table_column": ToolPolicy("describe_table_column", describe_table_column, routing=ToolRouting.EXPLORATORY),
    "preview_pdf": ToolPolicy("preview_pdf", preview_pdf, routing=ToolRouting.EXPLORATORY),
    "read_pdf": ToolPolicy("read_pdf", read_pdf, routing=ToolRouting.EXPLORATORY),
    "search_in_pdf": ToolPolicy("search_in_pdf", search_in_pdf, routing=ToolRouting.TERMINAL),
    "git_status": ToolPolicy("git_status", git_status, routing=ToolRouting.EXPLORATORY),
    "git_diff_unstaged": ToolPolicy("git_diff_unstaged", git_diff_unstaged, routing=ToolRouting.TERMINAL),
    "git_diff_staged": ToolPolicy("git_diff_staged", git_diff_staged, routing=ToolRouting.TERMINAL),
    "git_log": ToolPolicy("git_log", git_log, routing=ToolRouting.EXPLORATORY),
    "git_show": ToolPolicy("git_show", git_show, routing=ToolRouting.TERMINAL),
    "git_blame": ToolPolicy("git_blame", git_blame, routing=ToolRouting.TERMINAL),
    "edit_repo_file": ToolPolicy("edit_repo_file", edit_repo_file, requires_confirmation=True, routing=ToolRouting.TERMINAL),
    "list_dags": ToolPolicy("list_dags", list_dags, routing=ToolRouting.EXPLORATORY),
    "get_dag_runs": ToolPolicy("get_dag_runs", get_dag_runs, routing=ToolRouting.EXPLORATORY),
    "get_task_instances": ToolPolicy("get_task_instances", get_task_instances, routing=ToolRouting.TERMINAL),
    "get_task_log": ToolPolicy("get_task_log", get_task_log, routing=ToolRouting.TERMINAL),
}

TOOLS = {name: policy.function for name, policy in TOOL_POLICIES.items()}

def _assert_consistency() -> None:
    """
    Falha no import (cedo, alto, ruidoso) se TOOL_DEFINITIONS (schema enviado
    ao Gemini) e TOOL_POLICIES (comportamento de execução) divergirem — o
    tipo de bug que motivou esta consolidação (esquecer de registrar uma tool
    nova em um dos dois lugares) vira um erro imediato em vez de um
    comportamento errado silencioso descoberto em produção.
    """
    definition_names = {d['name'] for d in TOOL_DEFINITIONS}
    policy_names = set(TOOL_POLICIES)
    mismatched_names = {
        key: policy.name
        for key, policy in TOOL_POLICIES.items()
        if key != policy.name
    }
    invalid_functions = {
        key for key, policy in TOOL_POLICIES.items()
        if not callable(policy.function)
    }
    invalid_timeouts = {
        key: policy.timeout_seconds
        for key, policy in TOOL_POLICIES.items()
        if policy.timeout_seconds is not None and policy.timeout_seconds <= 0
    }
    confirmation_timeouts = {
        key: policy.timeout_seconds
        for key, policy in TOOL_POLICIES.items()
        if policy.requires_confirmation and policy.timeout_seconds is not None
    }

    if (
        definition_names != policy_names
        or mismatched_names
        or invalid_functions
        or invalid_timeouts
        or confirmation_timeouts
    ):
        faltando_policy = definition_names - policy_names
        faltando_definition = policy_names - definition_names
        raise RuntimeError(
            "Catálogo de tools inválido: "
            f"faltando em TOOL_POLICIES: {faltando_policy}, "
            f"faltando em TOOL_DEFINITIONS: {faltando_definition}, "
            f"nomes divergentes: {mismatched_names}, "
            f"funções inválidas: {invalid_functions}, "
            f"timeouts inválidos: {invalid_timeouts}, "
            f"tools de confirmação com timeout: {confirmation_timeouts}"
        )

_assert_consistency()
