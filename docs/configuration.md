# Configuração

## Assistente

```bash
python gemini_terminal.py --config
```

Dentro do terminal:

- `/config` executa diagnósticos locais sem revelar valores secretos;
- `/config edit` reabre o assistente.

## Variáveis

```env
GEMINI_API_KEY=sua_chave

# SQL Server opcional
DB_CONN_STRING=sua_connection_string

# Hive opcional
HIVE_HOST=seu_host
HIVE_PORT=10000
HIVE_DATABASE=seu_database
HIVE_USER=seu_usuario
HIVE_PASSWORD=sua_senha

# Airflow opcional
AIRFLOW_API_URL=http://seu-airflow:8080
AIRFLOW_USERNAME=seu_usuario
AIRFLOW_PASSWORD=sua_senha
```

O `.env` não deve ser versionado.

## Bancos de dados

As conexões lógicas ficam em `tools/db_connections.py`. Cada tabela cadastrada em `TABELAS_PERMITIDAS`, em `tools/database.py`, aponta para uma conexão e declara:

- schema;
- colunas retornáveis;
- colunas filtráveis e seus tipos;
- colunas editáveis, quando escrita for permitida.

Sem banco configurado, as ferramentas de arquivos, planilhas, PDF, Git e Airflow continuam disponíveis.

### SQL Server

Usa uma connection string fornecida por `DB_CONN_STRING`. Escritas continuam limitadas por allowlist, filtro obrigatório e confirmação.

### Hive

A URL é montada por componentes para preservar caracteres especiais de credenciais LDAP. O projeto usa `pure-sasl`, evitando a dependência nativa de Cyrus SASL. A integração deve ser tratada como somente-leitura.

## Airflow

A API v2 do Airflow 3.x usa autenticação por token. O token fica apenas em memória e é renovado quando necessário. Os DAGs consultáveis precisam ser cadastrados em `AIRFLOW_ALLOWED_DAGS`.
