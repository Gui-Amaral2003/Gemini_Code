# Configuração

## Instalação do comando

Para uso normal, instale a aplicação isoladamente com `pipx`:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
py -m pipx install "gemini-code-terminal[all] @ git+https://github.com/Gui-Amaral2003/Gemini_Code.git"
```

Depois de `ensurepath`, feche e reabra o terminal para que o Windows reconheça a alteração no `PATH`. Se o projeto tiver sido instalado com `pip`, `python -m gemini_terminal` pode ser usado como alternativa ao executável global.

O extra `all` instala todas as integrações. Para uma instalação menor, omita-o ou escolha entre `data`, `charts`, `pdf`, `sqlserver`, `hive` e `airflow`. O diagnóstico `/config` informa quais recursos estão disponíveis sem tentar conexões externas.

## Assistente

```bash
gemini-terminal --config
```

Dentro do terminal:

- `/config` executa diagnósticos locais sem revelar valores secretos;
- `/config edit` reabre o assistente.
- `/config resources` cadastra, edita e remove repositórios Git e DAGs do Airflow.

## Catálogo local de recursos

As allowlists de tabelas, repositórios e DAGs ficam em `catalogs.toml`, no diretório de dados do aplicativo. Use `/config` para consultar o caminho, a validade e a quantidade de recursos. A variável opcional `GEMINI_CATALOG_PATH` seleciona outro arquivo; não há descoberta automática na pasta atual.

O catálogo começa vazio. Os recursos anteriormente fixos no código precisam ser cadastrados novamente. Credenciais continuam no `.env`. Um arquivo inválido bloqueia o carregamento de todas as allowlists até ser corrigido e o terminal reiniciado.

Execute `/config resources`, escolha `1` para Git ou `2` para Airflow e depois `adicionar`, `editar` ou `remover`. Use `0` para sair do menu de grupos. Para cancelar durante um formulário, pressione Ctrl+C. Cada alteração exige confirmação antes de salvar; habilitar escrita em Git exige digitar `PERMITIR ESCRITA`. O padrão é somente leitura. A gravação é atômica e preserva os outros grupos.

Reinicie o terminal depois de salvar: schemas e tools usam o mesmo catálogo carregado na inicialização.

Tabelas são configuradas manualmente nesta V1; consulte [catalogs.example.toml](../examples/catalogs.example.toml). As conexões disponíveis são `sqlserver_main` e `hive_lake`; tipos de coluna aceitos: `int`, `float`, `str` e `date`. Sem `editable_columns`, a tabela permanece somente leitura. Escrita está disponível somente para SQL Server.

O editor reescreve o TOML ao salvar, preservando dados, mas não comentários e formatação. Arquivos locais chamados `catalogs.toml` são ignorados pelo Git.

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

## Diretório de dados

Sessões, cache, quota, histórico do prompt, traces e logs de auditoria ficam no diretório de dados da aplicação definido pelo sistema operacional. Para escolher outro local:

```env
GEMINI_DATA_DIR=C:\caminho\para\gemini-data
```

Essa separação permite executar `gemini-terminal` de qualquer diretório sem gravar estado dentro do pacote instalado. A pasta `output/` continua relativa ao diretório atual, pois contém resultados solicitados pelo usuário.

Para reutilizar sessões criadas por versões anteriores, aponte temporariamente `GEMINI_DATA_DIR` para a antiga pasta `gemini/` do clone ou copie os arquivos locais para o novo diretório.

## Bancos de dados

As conexões lógicas ficam em `tools/db_connections.py`. Cada tabela cadastrada em `database.tables` no catálogo local aponta para uma conexão e declara:

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

A API v2 do Airflow 3.x usa autenticação por token. O token fica apenas em memória e é renovado quando necessário. Cadastre os DAGs consultáveis em `/config resources` ou na seção `airflow.dags` do catálogo local.
