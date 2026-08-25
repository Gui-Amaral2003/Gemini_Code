import os
from typing import Optional
import pandas as pd
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
            'Company': 'str',
            'Deal_Date': 'date'
        },
        "colunas_retorno": ["ID", "WBC_TERM", "CTG_SUBMITTER", "Counterpart_CNPJ", "Contract_Type", "Supply_Start", "Supply_End", "Company", 'Deal_Date'],
        "colunas_editaveis": {'WBC_TERM': 'str', 'Flag': 'str', 'Status': 'str'}
    }
}

MAX_ROWS = 5000
QUERY_TIMEOUT_SECONDS = 10

# Cache do singleton lazy da engine — ver get_engine()/reset_engine_cache().
_ENGINE_CACHE: Optional['object'] = None

def get_engine():
    """
    Retorna a engine do SQLAlchemy, criando-a na primeira chamada e
    reaproveitando nas seguintes (singleton lazy).
 
    Em produção, ninguém precisa chamar isso diretamente nem passar engine
    para as funções abaixo — o default (engine=None) já resolve sozinho.
    Existe como função pública principalmente para permitir override em
    testes (via reset_engine_cache() + monkeypatch, ou passando uma engine
    de teste explicitamente para query_table/fetch_table_dataframe).
    """
    global _ENGINE_CACHE

    if _ENGINE_CACHE is None:
        import sqlalchemy

        conn_string = os.environ.get("DB_CONN_STRING")
        _ENGINE_CACHE = sqlalchemy.create_engine(conn_string, connect_args={"timeout": QUERY_TIMEOUT_SECONDS})

    return _ENGINE_CACHE

def reset_engine_cache() -> None:
    """
    Descarta a engine cacheada. Uso exclusivo de testes — permite simular
    outra DB_CONN_STRING (ou uma engine mockada) entre casos de teste sem
    que o cache de um teste anterior vaze para o próximo.
    """
    global _ENGINE_CACHE
    _ENGINE_CACHE = None

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

def _execute_query(sql: str, params: list, engine = None) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Executa uma query já validada/parametrizada (via _build_query) e
    retorna o resultado como DataFrame.
 
    engine=None usa get_engine() (produção); testes podem injetar uma
    engine/mock diretamente aqui (ou nas funções públicas abaixo, que
    repassam o parâmetro).
 
    Nunca levanta exceção — erro de execução vira mensagem de string,
    no mesmo padrão dos outros _load_*/_validate_* deste projeto, para
    que o modelo consiga se autocorrigir ou o usuário entenda o problema
    sem stacktrace.
    """
    import sqlalchemy

    try:
        resolved_engine = engine or get_engine()

        params_dict = {
            f"param_{i}": value
            for i, value in enumerate(params)
        }

        with resolved_engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(sql), conn, params=params_dict)

    except Exception as e:
        return None, f"Erro ao executar a query: {e}"

    if df.empty:
        return None, "Nenhum resultado encontrado para os filtros aplicados."

    return df, None

def fetch_table_dataframe(table: str, conditions: Optional[list[dict]] = None, engine=None) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Valida e executa uma consulta em uma tabela pré-cadastrada, aplicando
    os filtros diretamente no SQL (via _build_query), e retorna o
    resultado como DataFrame — para ser consumido por analyze_table_data/
    plot_table_data (tools/data_analysis.py).
 
    Retorna (df, error) — error já formatado para o modelo/usuário.
    """
    try:
        sql, params = _build_query(table, conditions or [])
    except QueryValidationError as e:
        return None, f"Requisição rejeitada: {e}"

    return _execute_query(sql, params, engine=engine)

def query_table(table: str, conditions: list[dict] | None = None, engine = None) -> str:
    """
    Executa uma consulta SELECT em uma tabela pré-cadastrada, filtrando apenas por colunas e operadores permitidos no catálogo TABELAS_PERMITIDAS
    """
    df, error = fetch_table_dataframe(table, conditions, engine)
    if error:
        return error

    result_list =  df.to_dict(orient='records')
    return str(result_list)