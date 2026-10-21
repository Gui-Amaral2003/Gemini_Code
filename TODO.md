# Roadmap e pendências

A versão 0.1.0 alpha já foi publicada. Este arquivo reúne entregas existentes,
trabalho pendente e ideias futuras; não representa uma sequência obrigatória de
implementação. O histórico de versões fica no [CHANGELOG](CHANGELOG.md).

## Entregue na 0.1.0

- [x] Registry central de ferramentas com `ToolPolicy`, validação de consistência e carregamento lazy.
- [x] Separação de gateway de modelos, executor de ferramentas, atividade e sessões.
- [x] Limite de rodadas de function calling para controlar loops do modelo.
- [x] Timeout de chamadas ao modelo e de espera por ferramentas, com exceção das que aguardam confirmação humana.
- [x] Confirmação de operações sensíveis e auditoria de escrita.
- [x] Planilhas CSV/Excel, consultas e análises em banco, PDFs e gráficos de barras/linhas.
- [x] Trace, timeline, consumo de tokens e estimativa local de quota.
- [x] Sessões persistentes, histórico e autocomplete no terminal.
- [x] Configuração global por `.env`, com prioridade das variáveis do ambiente.
- [x] `/config` para diagnóstico local e `/config edit` para configuração assistida.
- [x] Catálogos TOML locais e `/config resources` para Git, Airflow e tabelas.
- [x] Processos reutilizáveis carregados de YAML/JSON pela API Python.
- [x] Empacotamento, comando `gemini-terminal` e extras de instalação.
- [x] CI com Ruff, pytest em Python 3.11/3.12 e smoke test do wheel.
- [x] Documentação de arquitetura, configuração, segurança e limitações.
- [x] Demonstração reproduzível com CSV fictício e imagem SVG no README.

Testes, segurança e observabilidade continuam sendo atividades de manutenção;
essas áreas não são consideradas encerradas.

## Organização e qualidade

- [ ] Dividir as responsabilidades de `gemini_terminal.py`: loop, comandos, renderização e callbacks.
- [ ] Separar os schemas de `tools/definitions.py` por categoria, preservando a interface pública.
- [ ] Padronizar resultados de ferramentas com campos como sucesso, dados, erro e metadados.
- [ ] Extrair a responsabilidade de agente de `GeminiClient`, com um ciclo de interação explícito.
- [ ] Organizar a navegação local para distinguir código, resultados e artefatos regeneráveis.

## Testes e distribuição

- [ ] Criar avaliações comportamentais: escolha de ferramentas, respeito às restrições e confirmação de escrita.
- [ ] Ampliar testes de instalações mínimas e de extras isolados, incluindo execução real de ferramentas.
- [ ] Automatizar build e anexação de artefatos em futuras releases.
- [ ] Manter testes de regressão para problemas encontrados em uso real.

## Dados e ferramentas

### Planilhas e análise

- [ ] Suportar agrupamento por múltiplas colunas.
- [ ] Suportar múltiplas métricas e agregações na mesma execução.
- [ ] Adicionar scatter, histograma e boxplot; avaliar pie conforme os casos de uso.

### Documentos

- [ ] Extrair tabelas de PDFs.
- [ ] Suportar PDFs escaneados com OCR.
- [ ] Avaliar suporte a DOCX.

### Banco, Git e Airflow

- [ ] Separar credenciais de leitura e escrita em banco, com privilégios mínimos.
- [ ] Avaliar INSERT como operação própria, com validação e confirmação adequadas.
- [ ] Avaliar execução, pausa e retomada de DAGs com allowlist de escrita e confirmação.
- [ ] Avaliar commit de alterações aprovadas pelo usuário e integração com PRs/issues do GitHub.

Essas operações de escrita exigem revisão das políticas antes de serem
habilitadas; a existência do TODO não implica liberação automática.

## Configuração

- [ ] Recarregar configuração e catálogos de forma explícita e consistente, sem reiniciar.
- [ ] Tornar modelos principal, barato e fallback configuráveis pelo usuário.
- [ ] Tornar limites operacionais configuráveis: linhas, retries e timeouts.
- [ ] Permitir gerenciar permissões de escrita de tabelas pelo assistente, com confirmação específica.
- [ ] Detectar edições concorrentes e apresentar diff antes de salvar catálogos.
- [ ] Avaliar perfis separados para desenvolvimento e produção.
- [ ] Adicionar teste explícito de conexão e descoberta de colunas de banco.
- [ ] Adicionar `/config test` com confirmação antes de acessar Gemini, SQL Server, Hive ou Airflow. O teste de Gemini deve informar o consumo de uma chamada.
- [ ] Exportar diagnóstico sanitizado, sem segredos, hosts internos, headers, connection strings, prompts ou caminhos pessoais.
- [ ] Avaliar reparos assistidos somente para ações locais, explícitas e reversíveis.

O YAML de processos contém instruções reutilizáveis para o modelo; ele não
substitui o `.env` de credenciais nem o TOML de recursos e permissões.

## Segurança e limites

- [ ] Definir limites de tamanho para arquivos antes da leitura.
- [ ] Priorizar timeouts nativos para operações remotas e revisar cancelamento de execução.
- [ ] Avaliar isolamento de scripts em container ou sandbox de sistema operacional.
- [ ] Revisar periodicamente arquivos versionados e exemplos para evitar exposição de dados privados.

O timeout do executor limita a espera; ele não encerra uma função Python que
já começou. Ferramentas que aguardam confirmação humana não usam esse wrapper.

## Documentação e exemplos

- [ ] Revisar a origem do Excel demonstrativo e preparar um exemplo 100% fictício quando necessário.
- [ ] Criar exemplos Python de conversa, consulta de banco, análise de planilha, gráficos e orquestração.
- [ ] Adicionar uma demonstração animada com dados fictícios, se complementar o SVG existente.
- [ ] Manter README, catálogos de exemplo e instruções de instalação alinhados ao código.

## Ideias futuras — sem compromisso de versão

- [ ] RAG: loaders de documentos, chunking, embeddings, armazenamento vetorial e busca semântica.
- [ ] Interface web: upload de dados/documentos, conversa, ferramentas executadas, gráficos, tokens e trace.

Essas frentes ficam depois da consolidação do terminal e da validação de
necessidades reais dos usuários.
