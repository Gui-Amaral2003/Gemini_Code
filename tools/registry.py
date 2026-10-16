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
from importlib import import_module
from typing import Callable, Optional

from .definitions import TOOL_DEFINITIONS


@dataclass(frozen=True)
class LazyTool:
    """Callable que importa a implementação somente na primeira execução."""

    target: str

    def load(self) -> Callable:
        module_name, separator, function_name = self.target.partition(":")
        if not separator or not module_name or not function_name:
            raise ValueError(f"Referência de tool inválida: {self.target!r}")
        function = getattr(import_module(module_name), function_name)
        if not callable(function):
            raise TypeError(f"Implementação de tool não é chamável: {self.target}")
        return function

    def __call__(self, *args, **kwargs):
        return self.load()(*args, **kwargs)


def lazy(target: str) -> LazyTool:
    return LazyTool(target)

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
    # Nome do argumento que deve apontar para um arquivo criado nesta sessão.
    requires_session_created_file: Optional[str] = None
    # Nome do campo do resultado que contém um arquivo criado nesta sessão.
    registers_session_created_file: Optional[str] = None

TOOL_POLICIES: dict[str, ToolPolicy] = {
    "read_file": ToolPolicy("read_file", lazy("tools.filesystem:read_file"), routing=ToolRouting.EXPLORATORY),
    "create_file": ToolPolicy("create_file", lazy("tools.filesystem:create_file"), requires_confirmation=True, routing=ToolRouting.EXPLORATORY, registers_session_created_file="file_path"),
    "run_script": ToolPolicy("run_script", lazy("tools.script_runner:run_script"), requires_confirmation=True, routing=ToolRouting.EXPLORATORY, requires_session_created_file="path"),
    "query_table": ToolPolicy("query_table", lazy("tools.database:query_table"), routing=ToolRouting.EXPLORATORY),
    "update_table": ToolPolicy("update_table", lazy("tools.write_operations:update_table"), requires_confirmation=True, routing=ToolRouting.TERMINAL),
    "delete_table_rows": ToolPolicy("delete_table_rows", lazy("tools.write_operations:delete_table_rows"), requires_confirmation=True, routing=ToolRouting.TERMINAL),
    "list_sheets": ToolPolicy("list_sheets", lazy("tools.spreadsheet:list_sheets"), routing=ToolRouting.EXPLORATORY),
    "preview_sheet": ToolPolicy("preview_sheet", lazy("tools.spreadsheet:preview_sheet"), routing=ToolRouting.EXPLORATORY),
    "read_sheet": ToolPolicy("read_sheet", lazy("tools.spreadsheet:read_sheet"), routing=ToolRouting.EXPLORATORY),
    "search_in_sheet": ToolPolicy("search_in_sheet", lazy("tools.spreadsheet:search_in_sheet"), routing=ToolRouting.TERMINAL),
    "analyze_sheet_data": ToolPolicy("analyze_sheet_data", lazy("tools.data_analysis:analyze_sheet_data"), routing=ToolRouting.TERMINAL),
    "analyze_table_data": ToolPolicy("analyze_table_data", lazy("tools.data_analysis:analyze_table_data"), routing=ToolRouting.TERMINAL),
    "plot_sheet_data": ToolPolicy("plot_sheet_data", lazy("tools.data_analysis:plot_sheet_data"), generate_file=True, routing=ToolRouting.TERMINAL),
    "plot_table_data": ToolPolicy("plot_table_data", lazy("tools.data_analysis:plot_table_data"), generate_file=True, routing=ToolRouting.TERMINAL),
    "describe_sheet_column": ToolPolicy("describe_sheet_column", lazy("tools.data_analysis:describe_sheet_column"), routing=ToolRouting.EXPLORATORY),
    "describe_table_column": ToolPolicy("describe_table_column", lazy("tools.data_analysis:describe_table_column"), routing=ToolRouting.EXPLORATORY),
    "preview_pdf": ToolPolicy("preview_pdf", lazy("tools.pdf_reader:preview_pdf"), routing=ToolRouting.EXPLORATORY),
    "read_pdf": ToolPolicy("read_pdf", lazy("tools.pdf_reader:read_pdf"), routing=ToolRouting.EXPLORATORY),
    "search_in_pdf": ToolPolicy("search_in_pdf", lazy("tools.pdf_reader:search_in_pdf"), routing=ToolRouting.TERMINAL),
    "git_status": ToolPolicy("git_status", lazy("tools.git_tool:git_status"), routing=ToolRouting.EXPLORATORY),
    "git_diff_unstaged": ToolPolicy("git_diff_unstaged", lazy("tools.git_tool:git_diff_unstaged"), routing=ToolRouting.TERMINAL),
    "git_diff_staged": ToolPolicy("git_diff_staged", lazy("tools.git_tool:git_diff_staged"), routing=ToolRouting.TERMINAL),
    "git_log": ToolPolicy("git_log", lazy("tools.git_tool:git_log"), routing=ToolRouting.EXPLORATORY),
    "git_show": ToolPolicy("git_show", lazy("tools.git_tool:git_show"), routing=ToolRouting.TERMINAL),
    "git_blame": ToolPolicy("git_blame", lazy("tools.git_tool:git_blame"), routing=ToolRouting.TERMINAL),
    "edit_repo_file": ToolPolicy("edit_repo_file", lazy("tools.git_tool:edit_repo_file"), requires_confirmation=True, routing=ToolRouting.TERMINAL),
    "list_dags": ToolPolicy("list_dags", lazy("tools.airflow_tool:list_dags"), routing=ToolRouting.EXPLORATORY),
    "get_dag_runs": ToolPolicy("get_dag_runs", lazy("tools.airflow_tool:get_dag_runs"), routing=ToolRouting.EXPLORATORY),
    "get_task_instances": ToolPolicy("get_task_instances", lazy("tools.airflow_tool:get_task_instances"), routing=ToolRouting.TERMINAL),
    "get_task_log": ToolPolicy("get_task_log", lazy("tools.airflow_tool:get_task_log"), routing=ToolRouting.TERMINAL),
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
    invalid_session_file_fields = {
        key: {
            "requires": policy.requires_session_created_file,
            "registers": policy.registers_session_created_file,
        }
        for key, policy in TOOL_POLICIES.items()
        if any(
            value is not None and (not isinstance(value, str) or not value.strip())
            for value in (
                policy.requires_session_created_file,
                policy.registers_session_created_file,
            )
        )
    }

    if (
        definition_names != policy_names
        or mismatched_names
        or invalid_functions
        or invalid_timeouts
        or confirmation_timeouts
        or invalid_session_file_fields
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
            f"tools de confirmação com timeout: {confirmation_timeouts}, "
            f"campos de arquivo da sessão inválidos: {invalid_session_file_fields}"
        )

_assert_consistency()
