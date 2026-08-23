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
)
from .pdf_reader import preview_pdf, read_pdf, search_in_pdf
from .git_tool import (
    git_status,
    git_diff_unstaged,
    git_diff_staged,
    git_log,
    git_show,
    git_blame,
)

# Funções que o Python realmente pode executar.
TOOLS = {
    "read_file": read_file,
    "create_file": create_file,
    "run_script": run_script,
    'query_table': query_table,
    'list_sheets': list_sheets,
    'preview_sheet': preview_sheet,
    'read_sheet': read_sheet,
    'search_in_sheet': search_in_sheet,
    'analyze_sheet_data': analyze_sheet_data,
    'analyze_table_data': analyze_table_data,
    'plot_sheet_data': plot_sheet_data,
    'plot_table_data': plot_table_data,
    'preview_pdf': preview_pdf,
    'read_pdf': read_pdf,
    'search_in_pdf': search_in_pdf,
    'git_status': git_status,
    'git_diff_unstaged': git_diff_unstaged,
    'git_diff_staged': git_diff_staged,
    'git_log': git_log,
    'git_show': git_show,
    'git_blame': git_blame,
}