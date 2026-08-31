"""
Catálogo de conexões e dialetos de banco de dados.
 
Mesmo padrão de catálogo pré-cadastrado usado por TABELAS_PERMITIDAS
(database.py) e GIT_ALLOWED_REPOS (git_tool.py): o modelo nunca escolhe uma
connection string livre, apenas o nome de uma conexão pré-validada aqui.
 
DB_DIALECTS descreve só as diferenças sintáticas entre bancos que afetam a
geração de SQL (quoting de identificador, posição do LIMIT/TOP). Um banco
novo que caia no mesmo grupo sintático de um já existente (ex: MySQL usa
crase + LIMIT, igual ao Hive) não precisa de uma entrada de dialeto nova —
só uma entrada em DB_CONNECTIONS apontando pro dialeto já existente.
 
DB_CONNECTIONS mapeia um nome lógico de conexão -> como montar a engine
(connection string pronta via env var, ou componentes separados quando
building via URL evita problema de encoding — ver Hive/LDAP abaixo) +
qual dialeto usar. Múltiplas conexões coexistem na mesma sessão: nada aqui
impede ter SQL Server e Hive ativos ao mesmo tempo.
"""

DB_DIALECTS = {
    'mssql': {
        'quote': ("[", "]"),
        'limit_style': 'top' # TOP N logo após o SELECT
    },
    'hive': {
        'quote': ("`", "`"),
        'limit_style': 'limit' # LIMIT N no final da query
    },
    ## "mysqll" entra aqui reaproveitando o mesmo dialeto do Hive, que também usa crase + LIMIT
}

DB_CONNECTIONS = {
    "sqlserver_main": {
        "dialect": "mssql",
        "build": "conn_string",       # connection string pronta numa única env var
        "conn_string_env": "DB_CONN_STRING",
        "query_timeout_seconds": 10,  # aplicado via connect_args (pyodbc suporta)
    },
    "hive_lake": {
        "dialect": "hive",
        "build": "url_components",    # monta a URL via componentes (evita problema de encoding de senha LDAP)
        "host_env": "HIVE_HOST",
        "port_env": "HIVE_PORT",
        "database_env": "HIVE_DATABASE",
        "user_env": "HIVE_USER",
        "password_env": "HIVE_PASSWORD",
        "auth": "LDAP",
        # Documentado, mas SEM enforcement real — PyHive não expõe um
        # timeout de query via connect_args do SQLAlchemy como o pyodbc
        # expõe para mssql. Decisão consciente (opção mais simples): por
        # ora isso é só metadado/intenção. Se uma query Hive mal filtrada
        # travar a sessão por muito tempo na prática, revisitar com um
        # wrapper de timeout (ex: concurrent.futures) antes de generalizar
        # esse catálogo para mais conexões.
        "query_timeout_seconds": 60,
    },
}

def get_dialect_config(connection_name: str) -> dict:
    """Retorna a config de dialeto (quote, limit_style) para uma conexão pré-cadastrada."""

    connection = DB_CONNECTIONS.get(connection_name)
    if not connection:
        raise ValueError(f"Conexão '{connection_name}' não encontrada no catálogo.")

    return DB_DIALECTS[connection["dialect"]]