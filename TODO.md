## TODO:

# ============================================================
# ROADMAP — GEMINI DATA AGENT
# ============================================================

# ------------------------------------------------------------
# FASE 1 — ORGANIZAÇÃO E QUALIDADE DO PROJETO
# ------------------------------------------------------------

## TODO: Reorganizar o projeto em uma estrutura modular
# Separar:
# - client
# - sessions
# - tools
# - database
# - spreadsheets
# - analysis
# - models
# - tests
# Objetivo: reduzir a responsabilidade de gemini_client.py e tools.py.

## TODO: Separar as ferramentas em módulos específicos
# Exemplo:
# tools/
# ├── files.py
# ├── database.py
# ├── spreadsheet.py
# ├── analysis.py
# └── visualization.py

## TODO: Criar um sistema central de registro de ferramentas
# Substituir o dicionário TOOLS por um mecanismo de registro.
# Exemplo conceitual:
# register_tool(name, function, description)

## TODO: Criar modelos estruturados para resultados das ferramentas
# Criar ToolResult com:
# - success
# - data
# - error_type
# - message
# - metadata

## TODO: Remover arquivos temporários/testes do diretório principal
# Avaliar:
# - teste.py
# - teste.txt
# - arquivos gerados em runtime
# Mover testes para tests/ e exemplos para examples/.

## TODO: Garantir que arquivos gerados em runtime não sejam versionados
# Avaliar:
# - gemini_cache.json
# - gemini_usage_log.jsonl
# - chat_sessions.json
# Adicionar ao .gitignore quando apropriado.

## TODO: Criar .env.example
# Documentar todas as variáveis necessárias sem expor credenciais.
# Nunca versionar .env.

# ------------------------------------------------------------
# FASE 2 — TESTES
# ------------------------------------------------------------

## TODO: Migrar os testes atuais para pytest

## TODO: Criar tests/test_tools.py

## TODO: Criar testes para read_file()
# Testar:
# - arquivo inexistente
# - diretório no lugar de arquivo
# - encoding inválido
# - arquivo válido

## TODO: Criar testes para query_table()
# Testar:
# - tabela não permitida
# - coluna não permitida
# - operador inválido
# - tipo inválido
# - limite de registros
# - parâmetros SQL
# - ausência de resultados

## TODO: Criar testes para Excel/CSV
# Testar:
# - arquivo inexistente
# - extensão inválida
# - aba inexistente
# - coluna inexistente
# - arquivo vazio
# - paginação
# - busca

## TODO: Criar testes para PromptCache
# Testar:
# - cache hit
# - cache miss
# - limpeza do cache
# - prompts diferentes
# - system prompts diferentes

## TODO: Criar testes para fallback de modelos

## TODO: Criar testes para retry/backoff

## TODO: Criar testes para function calling

## TODO: Criar testes para sessões/conversas

# ------------------------------------------------------------
# FASE 3 — EXCEL / DATA ANALYSIS
# ------------------------------------------------------------

## TODO: Criar ferramenta describe_dataframe()
# Retornar:
# - número de linhas
# - número de colunas
# - nomes das colunas
# - tipos
# - valores nulos
# - estatísticas básicas

## TODO: Criar ferramenta analyze_dataframe()
# Permitir análises controladas utilizando Pandas.
# Operações iniciais:
# - count
# - sum
# - mean
# - median
# - min
# - max
# - std
# - groupby
# - sort
# - filter

## TODO: Permitir que o Gemini escolha automaticamente a operação
# O usuário deve poder perguntar em linguagem natural sem
# precisar conhecer a ferramenta.

## TODO: Implementar agregações com groupby
# Exemplo:
# "Qual foi o faturamento por mês?"

## TODO: Implementar filtros estruturados
# Exemplo:
# "Mostre clientes com vendas acima de 100 mil."

## TODO: Implementar ordenação
# Exemplo:
# "Quais são os 10 maiores clientes?"

## TODO: Implementar detecção básica de tipos
# Diferenciar automaticamente:
# - numérico
# - texto
# - data
# - booleano

## TODO: Implementar tratamento de datas
# Permitir:
# - agrupamento por mês
# - agrupamento por ano
# - intervalo de datas
# - crescimento temporal

# ------------------------------------------------------------
# FASE 4 — VISUALIZAÇÃO
# ------------------------------------------------------------

## TODO: Criar ferramenta create_chart()

## TODO: Suportar gráfico de linha

## TODO: Suportar gráfico de barras

## TODO: Suportar scatter plot

## TODO: Suportar histograma

## TODO: Suportar boxplot

## TODO: Permitir que o Gemini escolha automaticamente
# o tipo de gráfico baseado na pergunta e nos dados.

## TODO: Salvar gráficos em diretório dedicado
# Exemplo:
# outputs/charts/

## TODO: Evitar sobrescrever gráficos existentes
# Gerar nomes únicos para cada execução.

## TODO: Retornar ao Gemini o caminho/metadata do gráfico criado

# ------------------------------------------------------------
# FASE 5 — TOOL ORCHESTRATION
# ------------------------------------------------------------

## TODO: Implementar loop completo de execução de ferramentas
# Permitir múltiplas chamadas de ferramentas na mesma pergunta.

## TODO: Permitir execução sequencial de ferramentas
# Exemplo:
# list_sheets()
# -> preview_sheet()
# -> read_sheet()
# -> analyze_dataframe()
# -> create_chart()

## TODO: Permitir que uma ferramenta utilize o resultado
# de outra ferramenta como entrada.

## TODO: Adicionar limite máximo de chamadas por interação
# Evitar loops infinitos do modelo.

## TODO: Adicionar timeout por ferramenta

## TODO: Registrar todas as ferramentas executadas
# Registrar:
# - nome
# - argumentos
# - duração
# - sucesso/erro
# - resultado resumido

## TODO: Criar um execution trace por interação
# Permitir visualizar:
# User
# -> Gemini
# -> Tool
# -> Tool
# -> Gemini
# -> Response

# ------------------------------------------------------------
# FASE 6 — SEGURANÇA
# ------------------------------------------------------------

## TODO: Criar camada de validação/autorização das ferramentas

## TODO: Restringir diretórios acessíveis pelo read_file()
# Nunca permitir acesso arbitrário ao filesystem.

## TODO: Criar whitelist de extensões permitidas

## TODO: Criar limite de tamanho dos arquivos

## TODO: Criar limite de linhas retornadas pelas ferramentas

## TODO: Criar limite de tempo de execução das ferramentas

## TODO: Revisar todas as entradas vindas diretamente do Gemini

## TODO: Garantir que ferramentas de banco utilizem queries parametrizadas

## TODO: Impedir acesso a tabelas/colunas não autorizadas

## TODO: Criar política de acesso por ferramenta
# Exemplo:
# ToolPolicy(
#     allowed_tables=[...],
#     allowed_columns=[...],
#     max_rows=1000,
#     timeout=10
# )

# ------------------------------------------------------------
# FASE 7 — OBSERVABILIDADE
# ------------------------------------------------------------

## TODO: Melhorar logging estruturado

## TODO: Registrar duração de cada chamada ao Gemini

## TODO: Registrar duração de cada ferramenta

## TODO: Registrar tokens por interação

## TODO: Registrar modelo utilizado

## TODO: Registrar fallback utilizado

## TODO: Registrar cache hit/miss

## TODO: Criar resumo de custo/consumo por sessão

## TODO: Criar comando /stats no terminal
# Mostrar:
# - chamadas
# - tokens
# - cache hits
# - modelos utilizados
# - ferramentas utilizadas

# ------------------------------------------------------------
# FASE 8 — CONFIGURAÇÃO
# ------------------------------------------------------------

## TODO: Centralizar configurações do projeto

## TODO: Permitir configuração por .env

## TODO: Permitir configuração por YAML

## TODO: Separar configurações de desenvolvimento e produção

## TODO: Tornar modelos fallback configuráveis
# Não deixar a lista de modelos hardcoded.

## TODO: Tornar limites das ferramentas configuráveis
# max_rows
# timeout
# max_retries
# etc.

# ------------------------------------------------------------
# FASE 9 — DATASET DEMONSTRATIVO
# ------------------------------------------------------------

## TODO: Criar dataset Excel 100% fictício para demonstração

## TODO: Criar data/sample_sales.xlsx

## TODO: Criar dados fictícios de:
# - clientes
# - produtos
# - vendas
# - datas
# - valores

## TODO: Criar exemplos reproduzíveis no README

## TODO: Garantir que nenhum dado corporativo ou sensível
# esteja presente no repositório.

# ------------------------------------------------------------
# FASE 10 — EXEMPLOS
# ------------------------------------------------------------

## TODO: Criar examples/basic_chat.py

## TODO: Criar examples/database_query.py

## TODO: Criar examples/excel_analysis.py

## TODO: Criar examples/chart_generation.py

## TODO: Criar examples/tool_orchestration.py

## TODO: Criar exemplos de conversação no README

# ------------------------------------------------------------
# FASE 11 — DOCUMENTAÇÃO
# ------------------------------------------------------------

## TODO: Melhorar README.md

## TODO: Adicionar arquitetura do projeto

## TODO: Adicionar diagrama do fluxo Gemini -> Tools -> Data

## TODO: Adicionar seção de instalação

## TODO: Adicionar configuração da GEMINI_API_KEY

## TODO: Adicionar exemplos de uso

## TODO: Adicionar exemplos de Function Calling

## TODO: Adicionar exemplos de análise de Excel

## TODO: Adicionar exemplos de geração de gráficos

## TODO: Adicionar seção de segurança

## TODO: Adicionar seção de limitações

## TODO: Adicionar roadmap

## TODO: Adicionar screenshots do terminal utilizando apenas dados fictícios

## TODO: Adicionar GIF demonstrando uma interação completa
# Pergunta
# -> Gemini
# -> Tool
# -> Resultado
# -> Gemini
# -> Resposta

# ------------------------------------------------------------
# FASE 12 — CI/CD
# ------------------------------------------------------------

## TODO: Criar GitHub Actions para executar testes automaticamente

## TODO: Executar pytest a cada push

## TODO: Executar pytest a cada Pull Request

## TODO: Testar múltiplas versões do Python

## TODO: Adicionar lint ao pipeline

## TODO: Adicionar validação de imports

## TODO: Adicionar badge de build/testes no README

# ------------------------------------------------------------
# FASE 13 — ARQUITETURA DE AGENTE
# ------------------------------------------------------------

## TODO: Criar conceito explícito de Gemini Data Agent

## TODO: Separar GeminiClient de Agent

# GeminiClient:
# Responsável pela comunicação com a API.
#
# Agent:
# Responsável por:
# - decidir ferramentas
# - executar ferramentas
# - controlar contexto
# - controlar limites
# - montar resposta final

## TODO: Criar classe DataAgent

## TODO: Criar ToolRegistry

## TODO: Criar ToolExecutor

## TODO: Criar ExecutionContext

## TODO: Criar ExecutionTrace

## TODO: Definir ciclo de vida de uma interação

# ------------------------------------------------------------
# FASE 14 — RAG / DOCUMENTOS
# ------------------------------------------------------------

## TODO: Adicionar suporte a documentos PDF

## TODO: Adicionar suporte a DOCX

## TODO: Criar document loader

## TODO: Criar chunking de documentos

## TODO: Implementar embeddings

## TODO: Implementar armazenamento vetorial

## TODO: Criar ferramenta de busca semântica

## TODO: Implementar RAG

## TODO: Permitir perguntas sobre documentos utilizando linguagem natural

# ------------------------------------------------------------
# FASE 15 — INTERFACE WEB
# ------------------------------------------------------------

## TODO: Criar interface web para o Data Agent

## TODO: Permitir upload de Excel/CSV

## TODO: Permitir upload de documentos

## TODO: Exibir histórico da conversa

## TODO: Exibir ferramentas executadas

## TODO: Exibir gráficos gerados

## TODO: Exibir consumo de tokens

## TODO: Exibir execution trace

# ------------------------------------------------------------
# VISÃO FINAL DO PROJETO
# ------------------------------------------------------------

## TODO: Transformar o projeto em um Data/AI Agent completo

# Objetivo final:
#
# Usuário
#   ↓
# Gemini Data Agent
#   ↓
# ┌───────────────┬────────────────┬────────────────┐
# │               │                │                │
# SQL Server    Excel/CSV       Documents        Files
# │               │                │                │
# └───────────────┴────────────────┴────────────────┘
#                       ↓
#                 Data Analysis
#                       ↓
#                 Visualization
#                       ↓
#                    Gemini
#                       ↓
#                   Response
#
# O usuário deve conseguir fazer perguntas em linguagem natural
# e o agente deve decidir autonomamente quais ferramentas utilizar.