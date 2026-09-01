import os
from typing import Optional
import pandas as pd
from .validation import (
    QueryValidationError,
    _validate_identifier,
    validate_conditions
)
from .db_connections import DB_CONNECTIONS, get_dialect_config

TABELAS_PERMITIDAS = {
    "TEST_DOA_DEALS": {
        'connection': 'sqlserver_main',
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
    },
    # Exemplo de tabela Hive — ajuste para as tabelas reais do seu ambiente.
    # Sem "colunas_editaveis": Hive fica somente leitura por decisão de
    # design (a maioria das tabelas Hive não é ACID transacional; ver
    # write_operations.py, que segue assumindo dialeto mssql).
    # "ALGUMA_TABELA_HIVE": {
    #     "connection": "hive_lake",
    #     "schema": "algum_schema",
    #     "colunas_filtro": {"id": "int", "nome": "str"},
    #     "colunas_retorno": ["id", "nome"],
    # },
}

MAX_ROWS = 10000
#QUERY_TIMEOUT_SECONDS = 10

# Cache do singleton lazy da engine — ver get_engine()/reset_engine_cache().
_ENGINE_CACHE: Optional['object'] = {}

def _build_engine_url(connection_name: str) -> str:
    """
    Monta a URL de conexão (str ou sqlalchemy.engine.URL) e os connect_args
    apropriados para uma conexão pré-cadastrada em DB_CONNECTIONS.
 
    - build="conn_string": connection string pronta numa única env var
      (padrão atual do SQL Server via pyodbc). connect_args aplica o
      timeout, que o pyodbc suporta nativamente.
    - build="url_components": monta a URL a partir de host/porta/usuário/
      senha/database separados via sqlalchemy.engine.URL.create(), que
      cuida do encoding de caracteres especiais na senha automaticamente
      (evita o problema de montar a URL na mão com senha LDAP contendo
      '@', ':', etc). Sem connect_args aqui — não existe timeout de query
      nativo equivalente no PyHive (ver nota em db_connections.py).
    """
    import sqlalchemy

    config = DB_CONNECTIONS[connection_name]

    if config['build'] == 'conn_string':
        url = os.environ.get(config['conn_string_env'])
        connect_args = {"timeout": config.get("query_timeout_seconds")}

        return url, connect_args

    if config['build'] == 'url_components':
        port_raw = os.environ.get(config['port_env'])
        url = sqlalchemy.engine.URL.create(
            drivername="hive",
            username=os.environ.get(config["user_env"]),
            password=os.environ.get(config["password_env"]),
            host=os.environ.get(config["host_env"]),
            port=int(port_raw) if port_raw else None,
            database=os.environ.get(config["database_env"]),
            query={"auth": config.get("auth", "NONE")},
        )
        return url, {}

    raise ValueError(f"build desconhecido para a conexão '{connection_name}': {config['build']!r}")

def get_engine(connection_name: str = "sqlserver_main"):
    """
    Retorna a engine do SQLAlchemy para uma conexão pré-cadastrada em
    DB_CONNECTIONS, criando-a na primeira chamada e reaproveitando nas
    seguintes (cache por connection_name — múltiplas conexões coexistem
    na mesma sessão, ex: SQL Server e Hive ao mesmo tempo).
 
    connection_name tem default "sqlserver_main" só para manter chamadas
    antigas (sem argumento) funcionando; todo código novo que já sabe a
    tabela/conexão de destino deve passar o nome explicitamente.
    """
    global _ENGINE_CACHE
 
    if connection_name not in DB_CONNECTIONS:
        raise ValueError(
            f"Conexão não cadastrada: {connection_name}. "
            f"Disponíveis: {list(DB_CONNECTIONS)}"
        )
 
    if connection_name not in _ENGINE_CACHE:
        import sqlalchemy
 
        url, connect_args = _build_engine_url(connection_name)
        _ENGINE_CACHE[connection_name] = sqlalchemy.create_engine(url, connect_args=connect_args)
 
    return _ENGINE_CACHE[connection_name]

def reset_engine_cache(connection_name: Optional[str] = None) -> None:
    """
    Descarta a(s) engine(s) cacheada(s). Uso exclusivo de testes — permite
    simular outra connection string (ou uma engine mockada) entre casos de
    teste sem que o cache de um teste anterior vaze para o próximo.
 
    connection_name=None (padrão) reseta todas as conexões cacheadas;
    informe um nome específico para resetar só aquela.
    """
    global _ENGINE_CACHE
    if connection_name is None:
        _ENGINE_CACHE = {}
    else:
        _ENGINE_CACHE.pop(connection_name, None)

def _quote_identifier(name: str, dialect_config: dict) -> str:
    open_quote, close_quote = dialect_config['quote']

    return f"{open_quote}{name}{close_quote}"

def _build_query(table: str, conditions: list[dict]):
    """
    Valida table + conditions contra o catálogo e monta uma query
    parametrizada, respeitando o dialeto da conexão cadastrada para essa
    tabela (quoting de identificador + posição do LIMIT/TOP).
 
    Retorna (sql, params, connection_name)
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
    connection_name = config["connection"]
 
    _validate_identifier(schema, 'schema')
    _validate_identifier(table, 'tabela')
    for col in colunas_retorno:
        _validate_identifier(col, 'coluna de retorno')
 
    dialect_config = get_dialect_config(connection_name)
 
    where_clauses = []
    params = []
 
    for coluna, operador, valor_validado in validate_conditions(conditions, colunas_filtro):
        param_name = f"param_{len(params)}"
        where_clauses.append(f"{_quote_identifier(coluna, dialect_config)} {operador} :{param_name}")
        params.append(valor_validado)
 
    colunas_sql = ', '.join(_quote_identifier(c, dialect_config) for c in colunas_retorno)
    tabela_sql = f"{_quote_identifier(schema, dialect_config)}.{_quote_identifier(table, dialect_config)}"
 
    limit_style = dialect_config["limit_style"]
 
    if limit_style == "top":
        sql = f'SELECT TOP {MAX_ROWS} {colunas_sql} FROM {tabela_sql}'
    else:
        sql = f'SELECT {colunas_sql} FROM {tabela_sql}'
 
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
 
    if limit_style == "limit":
        sql += f" LIMIT {MAX_ROWS}"
 
    return sql, params, connection_name

def _execute_query(sql: str, params: list, connection_name: str, engine = None) -> tuple[Optional[pd.DataFrame], Optional[str]]:
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
        resolved_engine = engine or get_engine(connection_name)

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
        sql, params, connection_name = _build_query(table, conditions or [])
    except QueryValidationError as e:
        return None, f"Requisição rejeitada: {e}"

    return _execute_query(sql, params, connection_name, engine=engine)

def query_table(table: str, conditions: list[dict] | None = None, engine = None) -> str:
    """
    Executa uma consulta SELECT em uma tabela pré-cadastrada, filtrando apenas por colunas e operadores permitidos no catálogo TABELAS_PERMITIDAS
    """
    df, error = fetch_table_dataframe(table, conditions, engine)
    if error:
        return error

    result_list =  df.to_dict(orient='records')
    return str(result_list)