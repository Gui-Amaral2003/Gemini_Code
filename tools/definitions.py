from .database import TABELAS_PERMITIDAS

# Descrição das ferramentas que será enviada ao Gemini.
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "read_file",
        "description": "Lê o conteúdo de um arquivo de texto.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho do arquivo que deve ser lido.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "query_table",
        "description": (
            "Consulta dados em uma tabela pré-cadastrada do banco de dados. "
            "Somente tabelas e colunas explicitamente permitidas podem ser "
            "usadas. Os filtros são combinados sempre com AND."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Nome da tabela a consultar.",
                    "enum": list(TABELAS_PERMITIDAS.keys()),
                },
                "conditions": {
                    "type": "array",
                    "description": "Lista de condições de filtro, combinadas com AND.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {
                                "type": "string",
                                "description": "Nome da coluna a filtrar.",
                            },
                            "operator": {
                                "type": "string",
                                "description": "Operador de comparação.",
                                "enum": ["=", "!=", ">", "<", ">=", "<=", "LIKE"],
                            },
                            "value": {
                                "description": "Valor a comparar.",
                            },
                        },
                        "required": ["column", "operator", "value"],
                    },
                },
            },
            "required": ["table"],
        },
    },
    {
        "type": "function",
        "name": "list_sheets",
        "description": (
            "Lista as abas de um arquivo Excel (.xlsx/.xls) com suas dimensões, "
            "ou as dimensões da tabela caso seja um CSV. Use antes de ler ou "
            "buscar dados para descobrir os nomes das abas disponíveis."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho do arquivo (.xlsx, .xls ou .csv).",
                }
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "preview_sheet",
        "description": (
            "Mostra as colunas, o total de linhas e uma amostra das primeiras "
            "linhas de uma aba (ou de um CSV). Use para entender a estrutura "
            "da planilha antes de ler tudo ou fazer uma busca."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho do arquivo (.xlsx, .xls ou .csv).",
                },
                "sheet_name": {
                    "type": "string",
                    "description": (
                        "Nome da aba a ler. Se omitido, usa a primeira aba "
                        "(ignorado para CSV)."
                    ),
                },
                "n_rows": {
                    "type": "integer",
                    "description": "Quantas linhas mostrar na amostra (padrão: 10).",
                },
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "read_sheet",
        "description": (
            "Lê os dados de uma aba (ou CSV) de forma paginada. Use start_row "
            "e max_rows para percorrer planilhas grandes aos poucos, e columns "
            "para trazer só as colunas relevantes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho do arquivo (.xlsx, .xls ou .csv).",
                },
                "sheet_name": {
                    "type": "string",
                    "description": (
                        "Nome da aba a ler. Se omitido, usa a primeira aba "
                        "(ignorado para CSV)."
                    ),
                },
                "start_row": {
                    "type": "integer",
                    "description": "Linha inicial (0-indexado). Padrão: 0.",
                },
                "max_rows": {
                    "type": "integer",
                    "description": "Máximo de linhas a retornar nesta chamada. Padrão: 200.",
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de colunas a retornar. Se omitido, retorna todas.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "search_in_sheet",
        "description": (
            "Busca um valor (texto ou número) dentro de uma aba/CSV, em uma "
            "coluna específica ou em todas. Útil para achar uma linha "
            "específica sem precisar ler a planilha inteira."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho do arquivo (.xlsx, .xls ou .csv).",
                },
                "query": {
                    "type": "string",
                    "description": "Valor a buscar (substring, sem diferenciar maiúsculas/minúsculas).",
                },
                "sheet_name": {
                    "type": "string",
                    "description": (
                        "Nome da aba onde buscar. Se omitido, usa a primeira aba "
                        "(ignorado para CSV)."
                    ),
                },
                "column": {
                    "type": "string",
                    "description": "Coluna onde buscar. Se omitido, busca em todas as colunas.",
                },
                "max_matches": {
                    "type": "integer",
                    "description": "Máximo de linhas encontradas a retornar. Padrão: 50.",
                },
            },
            "required": ["path", "query"],
        },
    },
]
 