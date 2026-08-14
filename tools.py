from pathlib import Path
import re
import os


# --------------------------------------------------------------------------- #
# Ler arquivos do próprio sistema
# --------------------------------------------------------------------------- #

def read_file(path: str) -> str:
    """Lê um arquivo de texto."""

    file_path = Path(path)

    if not file_path.exists():
        return f"Arquivo não encontrado: {path}"

    if not file_path.is_file():
        return f"O caminho não é um arquivo: {path}"

    try:
        return file_path.read_text(encoding="utf-8")

    except UnicodeDecodeError:
        return f"Erro ao decodificar o arquivo: {path}. Certifique-se de que está em UTF-8."

    except OSError as e:
        return f"Erro ao ler o arquivo: {path}. Detalhes: {e}"

# --------------------------------------------------------------------------- #
# Funções para acesso ao banco de dados
# --------------------------------------------------------------------------- #
TABELAS_PERMITIDAS = {
    "pedidos": {
        "schema": "vendas",
        "colunas_filtro": {"cliente_id": "int", "status": "str", "data_pedido": "date"},
        "colunas_retorno": ["id", "cliente_id", "status", "data_pedido", "valor"],
    },
    "clientes": {
        "schema": "vendas",
        "colunas_filtro": {"cliente_id": "int", "cidade": "str"},
        "colunas_retorno": ["id", "nome", "cidade"],  # note: sem CPF, mesmo que exista na tabela
    },
}

_OPERADORES_POR_TIPO = {
    "int": {"=", "!=", ">", "<", ">=", "<="},
    "float": {"=", "!=", ">", "<", ">=", "<="},
    "date": {"=", "!=", ">", "<", ">=", "<="},
    "str": {"=", "!=", "LIKE"}
}

# Validação extra de indentificadores válidos
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

MAX_ROWS = 10_000
QUERY_TIMEOUT_SECONDS = 10

class QueryValidationError(ValueError):
    """Erro de validação de query."""

def _validate_identifier(name: str, label: str) -> None:
    if not _IDENTIFIER_RE.match(name):
        raise QueryValidationError(f"{label} inválido: {name!r}")

def _coerce_value(value, tipo: str, coluna: str):
    """Converte o valor para o tipo esperado"""
    try:
        if tipo == 'int':
            return int(value)
        if tipo == 'float':
            return float(value)
        if tipo == 'date':
            # Aceita YYYY-MM-DD, deixa o driver validar o formato final
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
                raise ValueError
            return str(value)
        if tipo == 'str':
            return str(value)

    except (ValueError, TypeError) as e:
        raise QueryValidationError(f"Erro ao converter valor para coluna {coluna}: {value}. Detalhes: {e}")

def _build_query(table: str, conditions: list[dict]):
    """
    Valida table + conditions contra o catálogo e monta uma query parametrizada.

    Retorna (sql, params)
    """
    if table not in TABELAS_PERMITIDAS:
        raise QueryValidationError(
            f"Tabela não permitida: {table}"
            f"Disponíveis: {list(TABELAS_PERMITIDAS)}"
        )

    config = TABELAS_PERMITIDAS[table]
    schema = config["schema"]
    colunas_filtro = config["colunas_filtro"]
    colunas_retorno = config['colunas_retorno']

    _validate_identifier(schema, 'schema')
    _validate_identifier(table, 'tabela')
    for col in colunas_retorno:
        _validate_identifier(col, 'coluna de retorno')

    where_clauses = []
    params = []

    for cond in conditions or []:
        coluna = cond.get('column')
        operador = cond.get('operator')
        valor = cond.get('value')

        if coluna not in colunas_filtro:
            raise QueryValidationError(
                f"Coluna não permitida para filtro: {coluna}. "
                f"Disponíveis: {list(colunas_filtro)}"
            )

        _validate_identifier(coluna, 'coluna de filtro')

        tipo = colunas_filtro[coluna]
        operadores_validos = _OPERADORES_POR_TIPO[tipo]

        if operador not in operadores_validos:
            raise QueryValidationError(
                f"Operador '{operador}' não é permitido para a coluna '{coluna}' "
                f"(tipo {tipo}). Permitidos: {sorted(operadores_validos)}"
            )

        valor_validado = _coerce_value(valor, tipo, coluna)

        if operador == "LIKE":
            # o próprio valor pode ter % embutido; se não tiver, envolve automaticamente
            if "%" not in valor_validado:
                valor_validado = f"%{valor_validado}%"

        where_clauses.append(f"[{coluna}] {operador} :param_{len(params)}")
        params.append(valor_validado)

    colunas_sql = ', '.join(f"[{c}]" for c in colunas_retorno)
    sql = f'SELECT TOP {MAX_ROWS} {colunas_sql} FROM [{schema}].[{table}]'

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    return sql, params

def query_table(table: str, conditions: list[dict] | None = None) -> str:
    """
    Executa uma consulta SELECT em uma tabela pré-cadastrada, filtrando apenas por colunas e operadores permitidos no catálogo TABELAS_PERMITIDAS
    """

    try:
        sql, params = _build_query(table, conditions or [])
    except QueryValidationError as e:
        return f"Requisição rejeitada: {e}"

    try:
        import sqlalchemy
        conn_string = os.environ.get("DB_CONN_STRING")

        engine = sqlalchemy.create_engine(conn_string, connect_args={"timeout": QUERY_TIMEOUT_SECONDS})

        with engine.connect() as conn:

            params_dict = {
                f"param_{i}": value
                for i, value in enumerate(params)
            }

            result = conn.execute(sqlalchemy.text(sql), params_dict)
            rows = result.fetchall()

            if not rows:
                return "Nenhum resultado encontrado."

            # Converte para lista de dicionários
            result_list = [dict(row._mapping) for row in rows]
            return str(result_list)
    except Exception as e:
        return f"Erro ao executar a query: {e}"


# Funções que o Python realmente pode executar.
TOOLS = {
    "read_file": read_file,
    'query_table': query_table
}


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
]
 