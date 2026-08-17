import os

from .validation import (
    QueryValidationError,
    _validate_identifier,
    validate_conditions
)

TABELAS_PERMITIDAS = {
    "TEST_DOA_DEALS": {
        "schema": "rsk",
        # coluna -> tipo esperado (usado pra validar operador e valor)
        "colunas_filtro": {
            "ID": "int",
            "WBC_TERM": "str",
            "CTG_SUBMITTER": 'str',
            "Counterpart_CNPJ": 'str',
            'Contract_Type': 'str',
            'Supply_Start': 'date',
            'Supply_End': 'date',
            'Company': 'str'
        },
        "colunas_retorno": ["ID", "WBC_TERM", "CTG_SUBMITTER", "Counterpart_CNPJ", "Contract_Type", "Supply_Start", "Supply_End", "Company"],
    }
}

MAX_ROWS = 5000
QUERY_TIMEOUT_SECONDS = 10


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

    for coluna, operador, valor_validado in validate_conditions(conditions, colunas_filtro):
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

