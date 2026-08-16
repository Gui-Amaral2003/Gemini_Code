from .filesystem import read_file
from .spreadsheet import (
    list_sheets,
    preview_sheet,
    read_sheet,
    search_in_sheet,
)
from .database import query_table

# Funções que o Python realmente pode executar.
TOOLS = {
    "read_file": read_file,
    'query_table': query_table,
    'list_sheets': list_sheets,
    'preview_sheet': preview_sheet,
    'read_sheet': read_sheet,
    'search_in_sheet': search_in_sheet
}
