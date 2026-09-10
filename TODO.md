## TODO:

# ============================================================
# ROADMAP — GEMINI DATA AGENT
# ============================================================

# ------------------------------------------------------------
# FASE 1 — ORGANIZAÇÃO E QUALIDADE DO PROJETO
# ------------------------------------------------------------

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

# ------------------------------------------------------------
# FASE 2 — TESTES
# ------------------------------------------------------------
# FINALIZADO NO MOMENTO

# ------------------------------------------------------------
# FASE 3 — EXCEL / DATA ANALYSIS
# ------------------------------------------------------------
# FINALIZADO

# ------------------------------------------------------------
# FASE 4 — VISUALIZAÇÃO
# ------------------------------------------------------------

## TODO: Suportar scatter plot

## TODO: Suportar histograma

## TODO: Suportar boxplot

# ------------------------------------------------------------
# FASE 5 — TOOL ORCHESTRATION
# ------------------------------------------------------------

## TODO: Adicionar limite máximo de chamadas por interação
# Evitar loops infinitos do modelo.

## TODO: Adicionar timeout por ferramenta

# ------------------------------------------------------------
# FASE 6 — SEGURANÇA
# ------------------------------------------------------------

## TODO: Criar limite de tamanho dos arquivos

## TODO: Criar limite de tempo de execução das ferramentas

# ------------------------------------------------------------
# FASE 7 — OBSERVABILIDADE
# ------------------------------------------------------------
# FINALIZADO

# ------------------------------------------------------------
# FASE 8 — CONFIGURAÇÃO
# ------------------------------------------------------------

## TODO: Centralizar configurações do projeto

## TODO: Permitir configuração por .env

## TODO: Permitir configuração por YAML

## TODO: Separar configurações de desenvolvimento e produção

## TODO: Adicionar `/config test` para verificações externas
# Pedir confirmação antes de testar Gemini, SQL Server, Hive e Airflow.
# O teste do Gemini consome uma chamada e deve deixar esse custo explícito.

## TODO: Exportar diagnóstico sanitizado do `/config`
# Nunca incluir secrets, hosts internos, headers HTTP, connection strings,
# prompts ou caminhos pessoais no relatório.

## TODO: Avaliar reparos assistidos de configuração
# Limitar a ações locais, explícitas e reversíveis. Nunca alterar
# credenciais, conexões externas ou permissões automaticamente.

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

# ------------------------------------------------------------
# FASE 11 — DOCUMENTAÇÃO
# ------------------------------------------------------------

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

## TODO: Definir ciclo de vida de uma interação

# ------------------------------------------------------------
# FASE 14 — RAG / DOCUMENTOS
# ------------------------------------------------------------

## TODO: Adicionar suporte a DOCX

## TODO: Criar document loader

## TODO: Criar chunking de documentos

## TODO: Implementar embeddings

## TODO: Implementar armazenamento vetorial

## TODO: Criar ferramenta de busca semântica

## TODO: Implementar RAG

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
