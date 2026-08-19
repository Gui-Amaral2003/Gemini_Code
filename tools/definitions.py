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
                    "description": (
                        "Nome do arquivo a ser lido ou caminho completo. Se apenas "
                        "o nome for informado, o arquivo é localizado automaticamente."
                    ),
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
    {
        "type": "function",
        "name": "analyze_sheet_data",
        "description": (
            "Executa uma análise agregada (soma, média, contagem, min, max, etc.) sobre os "
            "dados de uma planilha (.xlsx ou .csv), com filtro e agrupamento opcionais. "
            "Use esta ferramenta em vez de calcular manualmente a partir de dados já vistos "
            "no contexto — ela garante exatidão e evita ler a planilha inteira."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": (
                        "Nome do arquivo de planilha (.xlsx ou .csv) ou caminho completo. "
                        "Se apenas o nome for informado, o arquivo é localizado automaticamente."
                    ),
                },
                "sheet_name": {
                    "type": "string",
                    "description": "Nome da aba, se aplicável (apenas para .xlsx). Se omitido, usa a primeira aba.",
                },
                "operation": {
                    "type": "string",
                    "enum": ["sum", "mean", "count", "min", "max", "nunique", "median", "std"],
                    "description": "Operação de agregação a ser aplicada.",
                },
                "target_column": {
                    "type": "string",
                    "description": (
                        "Coluna a ser agregada. Obrigatória para todas as operações, exceto "
                        "'count' sem agrupamento (nesse caso, conta o total de linhas)."
                    ),
                },
                "group_by": {
                    "type": "string",
                    "description": (
                        "Coluna única para agrupar o resultado. Se omitido, retorna um único "
                        "valor agregado sobre toda a planilha."
                    ),
                },
                "conditions": {
                    "type": "array",
                    "description": "Lista de condições de filtro aplicadas antes da agregação.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {"type": "string", "description": "Nome da coluna a filtrar."},
                            "operator": {
                                "type": "string",
                                "enum": ["=", "!=", ">", "<", ">=", "<=", "LIKE"],
                                "description": "Operador de comparação. LIKE apenas para colunas de texto.",
                            },
                            "value": {
                                "type": "string",
                                "description": "Valor de comparação (convertido para o tipo real da coluna).",
                            },
                        },
                        "required": ["column", "operator", "value"],
                    },
                },
                "top_n": {
                    "type": "integer",
                    "description": "Limita o número de grupos retornados quando group_by é usado.",
                },
                "sort_ascending": {
                    "type": "boolean",
                    "description": "Se True, ordena o resultado agrupado em ordem crescente. Padrão: decrescente.",
                },
            },
            "required": ["file_path", "operation"],
        },
    },
    {
        "type": "function",
        "name": "analyze_table_data",
        "description": (
            "Executa uma análise agregada (soma, média, contagem, min, max, etc.) sobre os "
            "dados de uma tabela pré-cadastrada do banco SQL Server, com filtro e agrupamento "
            "opcionais. Use esta ferramenta em vez de calcular manualmente a partir de dados já "
            "vistos no contexto — ela garante exatidão e evita ler a tabela inteira."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Nome da tabela pré-cadastrada (ver TABELAS_PERMITIDAS).",
                },
                "operation": {
                    "type": "string",
                    "enum": ["sum", "mean", "count", "min", "max", "nunique", "median", "std"],
                    "description": "Operação de agregação a ser aplicada.",
                },
                "target_column": {
                    "type": "string",
                    "description": (
                        "Coluna a ser agregada. Obrigatória para todas as operações, exceto "
                        "'count' sem agrupamento (nesse caso, conta o total de linhas)."
                    ),
                },
                "group_by": {
                    "type": "string",
                    "description": (
                        "Coluna única para agrupar o resultado. Se omitido, retorna um único "
                        "valor agregado sobre toda a tabela."
                    ),
                },
                "conditions": {
                    "type": "array",
                    "description": "Lista de condições de filtro aplicadas antes da agregação.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {"type": "string", "description": "Nome da coluna a filtrar."},
                            "operator": {
                                "type": "string",
                                "enum": ["=", "!=", ">", "<", ">=", "<=", "LIKE"],
                                "description": "Operador de comparação. LIKE apenas para colunas de texto.",
                            },
                            "value": {
                                "type": "string",
                                "description": "Valor de comparação (convertido para o tipo real da coluna).",
                            },
                        },
                        "required": ["column", "operator", "value"],
                    },
                },
                "top_n": {
                    "type": "integer",
                    "description": "Limita o número de grupos retornados quando group_by é usado.",
                },
                "sort_ascending": {
                    "type": "boolean",
                    "description": "Se True, ordena o resultado agrupado em ordem crescente. Padrão: decrescente.",
                },
            },
            "required": ["table", "operation"],
        },
    },
    {
        "type": "function",
        "name": "preview_pdf",
        "description": (
            "Mostra o número de páginas, metadados básicos (título/autor) e um preview "
            "do texto da primeira página de um PDF. Use antes de ler ou buscar dados "
            "para entender a estrutura do documento e detectar se ele tem texto "
            "extraível (PDFs escaneados/imagem não têm)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Nome do arquivo PDF a ser lido ou caminho completo. Se apenas "
                        "o nome for informado, o arquivo é localizado automaticamente."
                    ),
                }
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "read_pdf",
        "description": (
            "Lê o texto de um PDF de forma paginada. Use start_page e max_pages para "
            "percorrer documentos grandes aos poucos, evitando estourar o contexto."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho do arquivo PDF.",
                },
                "start_page": {
                    "type": "integer",
                    "description": "Página inicial (0-indexado). Padrão: 0.",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "Máximo de páginas a retornar nesta chamada. Padrão: 10.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "search_in_pdf",
        "description": (
            "Busca um texto (substring, sem diferenciar maiúsculas/minúsculas) em todas "
            "as páginas de um PDF. Retorna o número da página e um trecho de contexto ao "
            "redor de cada ocorrência. Útil para localizar um trecho específico sem "
            "precisar ler o documento inteiro."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho do arquivo PDF.",
                },
                "query": {
                    "type": "string",
                    "description": "Texto a buscar.",
                },
                "max_matches": {
                    "type": "integer",
                    "description": "Máximo de ocorrências a retornar. Padrão: 20.",
                },
            },
            "required": ["path", "query"],
        },
    },
]
 
 