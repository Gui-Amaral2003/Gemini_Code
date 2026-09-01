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

# Funções que o Python realmente pode executar.
TOOLS = {
    "read_file": read_file,
    "create_file": create_file,
    "run_script": run_script,
    'query_table': query_table,
    'update_table': update_table,
    'delete_table_rows': delete_table_rows,
    'list_sheets': list_sheets,
    'preview_sheet': preview_sheet,
    'read_sheet': read_sheet,
    'search_in_sheet': search_in_sheet,
    'analyze_sheet_data': analyze_sheet_data,
    'analyze_table_data': analyze_table_data,
    'plot_sheet_data': plot_sheet_data,
    'plot_table_data': plot_table_data,
    'describe_sheet_column': describe_sheet_column,
    'describe_table_column': describe_table_column,
    'preview_pdf': preview_pdf,
    'read_pdf': read_pdf,
    'search_in_pdf': search_in_pdf,
    'git_status': git_status,
    'git_diff_unstaged': git_diff_unstaged,
    'git_diff_staged': git_diff_staged,
    'git_log': git_log,
    'git_show': git_show,
    'git_blame': git_blame,
    'edit_repo_file': edit_repo_file,
    'list_dags': list_dags,
    'get_dag_runs': get_dag_runs,
    'get_task_instances': get_task_instances,
    'get_task_log': get_task_log,
}