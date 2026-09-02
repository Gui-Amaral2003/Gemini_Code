# Gemini Terminal

Agente de IA em Python para a [Google Gemini API](https://ai.google.dev/), com suporte a conversas persistentes, ferramentas customizáveis (function calling), retry automático, cache, roteamento entre modelos e terminal interativo.

A biblioteca está organizada em um pacote Python dedicado em `gemini/`. O arquivo `old_gemini_client.py` é mantido apenas como referência da implementação anterior.

> ⚠️ **Em desenvolvimento**: este projeto ainda está em fase inicial. Novas ferramentas e funcionalidades serão adicionadas com frequência.

---

## 🎯 Características

- **Pacote principal em `gemini/`**: organização modular para cliente, sessão, modelos e configurações
- **Cliente Gemini Wrapper**: interface simples sobre a API do Google Gemini, com tratamento robusto de erros
- **Conversas persistentes**: histórico local e recuperação de sessões anteriores
- **Ferramentas customizáveis**: execução de funções Python a partir de decisões do modelo
- **Análise de dados integrada**: sumarização, filtros e agregações em planilhas e tabelas pré-cadastradas
- **Leitura de PDFs**: preview, leitura paginada e busca de texto
- **Ferramentas Git**: leitura de status, diffs, histórico, autoria e edição controlada de arquivos
- **Segurança em camadas**: whitelist de tabelas/colunas/repositórios, confirmação explícita para escrita, audit log
- **Retry automático**: recuperação de falhas transitórias com backoff exponencial
- **Cache inteligente**: evita chamadas duplicadas e reduz custo de tokens
- **Roteamento multi-modelo**: usa um modelo mais barato para sintetizar a resposta depois de ferramentas terminais, preservando o modelo forte para decisões de novas ferramentas
- **Tracking de cota diária (RPD)**: contador local por modelo, estimando quanto do limite diário do free tier já foi usado, com bloqueio (via confirmação) quando todos os modelos configurados estimam cota esgotada
- **Geração de gráficos**: cria gráficos de barra ou linha no terminal e salva PNGs temporários para aprovação do usuário
- **Logging estruturado**: monitoramento de uso em arquivo JSONL
- **Terminal interativo**: CLI com Rich para uso prático

---

## 📋 Requisitos

- Python 3.10+
- Chave de API do Google Gemini: [ai.google.dev](https://ai.google.dev/)
- (Opcional) Acesso a um SQL Server próprio, apenas se você for usar as ferramentas de banco de dados

---

## 🚀 Setup do zero

**Importante:** este repositório não vem com banco de dados, credenciais ou chave de API. Nada aqui roda "pronto" — cada pessoa configura o próprio ambiente. Isso é proposital: o projeto foi desenhado para nunca ter segredos ou dados reais versionados no código.

### 1. Clone o repositório

```bash
git clone https://github.com/Gui-Amaral2003/Gemini_Code
cd Gemini_Code
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

Equivalente manual:

```bash
pip install google-genai rich python-dotenv sqlalchemy pyyaml pyodbc pandas tabulate openpyxl pypdf matplotlib plotext
```

### 3. Crie seu próprio `.env`

Crie um arquivo `.env` na raiz do projeto:

```env
GEMINI_API_KEY=sua_chave_aqui
DB_CONN_STRING=sua_connection_string_aqui

# Opcional — necessário apenas para usar as ferramentas Airflow
AIRFLOW_API_URL=http://sua-vm:8080
AIRFLOW_USERNAME=seu_usuario
AIRFLOW_PASSWORD=sua_senha
```

Uma chave Gemini gratuita pode ser obtida em [ai.google.dev](https://ai.google.dev/).

`DB_CONN_STRING` é **opcional** — veja a seção abaixo antes de decidir se precisa dela.
As variáveis `AIRFLOW_API_URL`, `AIRFLOW_USERNAME` e `AIRFLOW_PASSWORD` também
são opcionais e só são necessárias para usar as ferramentas de monitoramento
do Airflow.

### 4. Banco de dados: múltiplas conexões (SQL Server + Hive)

Sem nenhuma `DB_CONNECTIONS` configurada, tudo funciona normalmente **exceto**
as ferramentas que dependem de banco: `query_table`, `update_table`,
`delete_table_rows`, `analyze_table_data`, `describe_table_column` e
`plot_table_data`.

O projeto suporta múltiplas conexões simultâneas (ex: SQL Server e Hive ao
mesmo tempo), cadastradas em `tools/db_connections.py`. Cada tabela em
`TABELAS_PERMITIDAS` (`tools/database.py`) aponta para uma conexão pelo nome
lógico (`connection`), e o SQL gerado respeita automaticamente o dialeto
daquela conexão (quoting de identificador, posição do `LIMIT`/`TOP`).

Todo o resto — planilhas/CSV, PDFs, arquivos, scripts, Git e Airflow —
funciona sem nenhum banco configurado.

#### Configurando SQL Server

```env
DB_CONN_STRING=sua_connection_string_aqui
```

#### Configurando Hive

```env
HIVE_HOST=seu_host
HIVE_PORT=10000
HIVE_DATABASE=seu_database
HIVE_USER=seu_usuario
HIVE_PASSWORD=sua_senha
```

A conexão com Hive é montada por componentes separados (não por connection
string pronta), o que evita problemas de encoding quando a senha LDAP contém
caracteres especiais (`@`, `:`, etc). Requer os pacotes `pyhive[hive]` e
`thrift` (ver requirements.txt).

**Hive é somente leitura por padrão de design**: tabelas cadastradas com
`connection: "hive_lake"` não devem receber `colunas_editaveis`, porque a
maioria das tabelas Hive não é transacional (ACID) — `update_table`/
`delete_table_rows` continuam assumindo o dialeto SQL Server.

#### Cadastrando tabelas

Em `TABELAS_PERMITIDAS` (`tools/database.py`), cada tabela declara a
conexão a usar:

```python
TABELAS_PERMITIDAS = {
    "SUA_TABELA_SQLSERVER": {
        "connection": "sqlserver_main",
        "schema": "seu_schema",
        "colunas_filtro": {...},
        "colunas_retorno": [...],
        "colunas_editaveis": {...},  # opcional — libera update_table/delete_table_rows
    },
    "SUA_TABELA_HIVE": {
        "connection": "hive_lake",
        "schema": "seu_schema",
        "colunas_filtro": {...},
        "colunas_retorno": [...],
        # sem colunas_editaveis — Hive fica somente leitura
    },
}
```

Para adicionar um banco com sintaxe parecida com um dialeto já cadastrado
(ex: MySQL, que usa crase + `LIMIT` igual ao Hive), não é preciso criar um
dialeto novo em `DB_DIALECTS` — só uma entrada em `DB_CONNECTIONS`
apontando para o dialeto existente.

### 5. Rode o terminal interativo

```bash
python gemini_terminal.py
```

---

## 💡 Importando o pacote

```python
from gemini import GeminiClient, ChatSession, load_processes, run_process
```

O arquivo `old_gemini_client.py` contém a implementação anterior, mantida só para referência. A organização oficial do projeto fica em `gemini/`.

---

## 🧪 Exemplos de uso

### Uso básico

```python
from gemini import GeminiClient

client = GeminiClient()

response = client.generate("Explique o que é uma CTE em SQL")
print(response.text)
print(f"Tokens usados: {response.total_tokens}")
```

### Conversa com histórico

```python
from gemini import GeminiClient, ChatSession

client = GeminiClient()

chat = ChatSession(
    client=client,
    session_id="meu_tutor_sql",
    system_instruction="Você é um tutor de SQL experiente."
)

r1 = chat.send("O que é uma CTE?")
print(r1.text)

r2 = chat.send("Me dá um exemplo com JOIN.")
print(r2.text)

for msg in chat.get_history():
    print(f"{msg.role}: {msg.text}\n")
```

### Terminal interativo

```bash
python gemini_terminal.py
```

Comandos disponíveis:
- `/help` — mostra a ajuda completa
- `/history` — mostra o histórico local da sessão
- `/clear` — limpa o contexto e desvincula a conversa anterior
- `/tools` — lista as ferramentas por categoria
- `/tools <nome>` — mostra a descrição detalhada de uma ferramenta
- `/think` — liga ou desliga a exibição dos resumos de pensamento
- `/logs` — alterna a visibilidade dos logs
- `/tokens` — mostra o consumo de tokens da sessão
- `/exit` — sai do terminal

### Usando ferramentas

O Gemini pode executar ferramentas Python automaticamente:

```python
from gemini import GeminiClient

client = GeminiClient()

response = client.generate(
    "Leia o arquivo config.yaml e resuma seu conteúdo"
)
print(response.text)
```

Para perguntas que exigem soma, média, contagem, mínimo, máximo ou outra agregação, as ferramentas `analyze_sheet_data` e `analyze_table_data` devem ser usadas. As ferramentas `read_sheet`, `preview_sheet` e `query_table` servem para explorar ou exibir dados, não para substituir uma agregação calculada pela ferramenta.

### Roteamento entre modelos

O cliente pode usar um modelo mais barato na etapa de síntese, depois que todas as ferramentas chamadas em uma rodada forem "terminais". Isso reduz o custo sem transferir para o modelo barato a decisão de qual ferramenta chamar. Se o modelo barato pedir outra ferramenta em vez de sintetizar, a rodada é refeita com o modelo padrão.

```python
from gemini import GeminiClient

client = GeminiClient(
    default_model="gemini-3.6-flash",
    cheap_model="gemini-3.5-flash-lite",
)

response = client.generate(
    "Calcule as vendas por segmento em examples/SampleSuperstore.csv"
)
print(response.text)
```

O roteamento considera terminais `analyze_sheet_data`, `analyze_table_data`, `plot_sheet_data`, `plot_table_data`, `search_in_pdf`, `search_in_sheet`, `update_table`, `delete_table_rows`, `git_diff_unstaged`, `git_diff_staged`, `git_show`, `git_blame` e `edit_repo_file`. Ferramentas exploratórias, como `preview_sheet`, `read_sheet`, `query_table`, `read_pdf`, `git_status` e `git_log`, mantêm o modelo forte para a próxima decisão.

### Geração de gráficos

Use `plot_sheet_data` para CSV/Excel ou `plot_table_data` para tabelas pré-cadastradas no banco. Os tipos disponíveis são `bar` e `line`.

```python
from tools.data_analysis import plot_sheet_data

resultado = plot_sheet_data(
    file_path="examples/SampleSuperstore.csv",
    operation="sum",
    target_column="Sales",
    group_by="Segment",
    chart_type="bar",
)
print(resultado)
```

O gráfico também é renderizado no terminal com `plotext`. O PNG é salvo temporariamente em `output/plots_staging/`; a aplicação que chamou o cliente decide se move o arquivo ou o descarta (no terminal interativo, essa decisão é perguntada ao usuário).

### Registrando processos reutilizáveis

```python
from gemini import GeminiClient, register_process, run_process

client = GeminiClient()

register_process(
    "triagem_logs",
    system="""Você é um assistente de triagem de logs.
              Responda em 3 seções:
              1. Causa provável
              2. Tipo de erro (transitório/estrutural)
              3. Sugestão de correção"""
)

log = "[ERROR] Connection timeout..."
response = run_process(client, "triagem_logs", log)
print(response.text)
```

### Carregando processos de arquivo

**process.yaml:**
```yaml
log_triage:
  system: |
    Você é um assistente de triagem de logs de pipelines de dados.
    Responda em 3 partes: causa provável, tipo de erro, sugestão de correção.
  model: null

summarize_pt:
  system: "Resuma o texto em até 3 frases em português claro."
```

**Código:**
```python
from gemini import GeminiClient, load_processes, run_process

client = GeminiClient()
load_processes("process.yaml")

response = run_process(client, "log_triage", seu_log_aqui)
print(response.text)
```

---

## 📁 Estrutura do projeto

```text
.
├── gemini/
│   ├── __init__.py             # Exporta os símbolos públicos do pacote
│   ├── client.py               # Cliente principal do Gemini
│   ├── session.py              # Sessões e histórico de conversa
│   ├── models.py               # Modelos de resposta e mensagens
│   ├── config.py               # Configurações e caminhos padrão
│   ├── cache.py                # Cache de prompts e respostas
│   ├── model_routing.py        # Classificação de tools e roteamento de modelos
│   ├── quota_tracker.py        # Cota diária (RPD) estimada por modelo, com bloqueio via confirmação
│   ├── chat_sessions.json      # Histórico persistente das sessões (gerado localmente)
│   ├── gemini_cache.json       # Cache local de respostas (gerado localmente)
│   ├── gemini_usage_log.jsonl  # Log local de uso da API (gerado localmente)
│   ├── quota_tracker.json      # Contador de RPD do dia atual, por modelo (gerado localmente)
│   └── db_write_audit_log.jsonl # Audit log de escritas no banco (gerado localmente)
├── tools/
│   ├── __init__.py
│   ├── definitions.py          # Definições das ferramentas enviadas ao Gemini
│   ├── registry.py             # Registro das ferramentas executáveis
│   ├── filesystem.py           # read_file / create_file
│   ├── confirmation.py         # Confirmações explícitas para operações sensíveis
│   ├── script_runner.py        # Execução confirmada de scripts Python
│   ├── script_safety.py        # Varredura estática de scripts antes da execução
│   ├── database.py             # Leitura de tabelas pré-cadastradas (query_tableCat)
│   ├── db_connections.py       # Catálogo de conexões e dialetos (SQL Server, Hive)
│   ├── airflow_tool.py         # Monitoramento de DAGs via API v2 do Airflow
│   ├── write_operations.py     # UPDATE/DELETE controlados, com confirmação e audit log
│   ├── spreadsheet.py          # Leitura e busca em planilhas/CSV
│   ├── data_analysis.py        # Agregação e análise de dados em planilhas e tabelas
│   ├── plotting.py             # Renderização no terminal e geração de PNGs
│   ├── pdf_reader.py           # Preview, leitura e busca de texto em PDFs
│   ├── git_tool.py             # Leitura, diffs, histórico, autoria e edição em Git
│   └── validation.py           # Validação de identificadores e filtros
├── old_gemini_client.py        # Implementação anterior, mantida para referência
├── gemini_terminal.py          # CLI interativa
├── process.yaml                # Definição de processos reutilizáveis
├── requirements.txt
├── README.md
├── LICENSE
├── TODO.md
├── examples/
│   └── SampleSuperstore.csv    # Dataset de exemplo para testar as ferramentas de planilha
├── output/                     # Gerado localmente: scripts criados por create_file e gráficos
│   ├── plots/                  # Gráficos que o usuário optou por manter
│   └── plots_staging/          # Gráficos recém-gerados, aguardando decisão do usuário
└── tests/                      # Testes automatizados
```

> Os arquivos marcados como "gerado localmente" não vêm no repositório — são criados durante o uso e ficam fora do controle de versão.

---

## 🛠️ Ferramentas disponíveis

### 1. `read_file`

Lê o conteúdo de um arquivo de texto.

```python
response = client.generate("Qual é o tamanho do arquivo config.yaml?")
```

**Parâmetros:**
- `path` (str): caminho do arquivo

### 2. `create_file`

Cria um arquivo dentro de `output/`. Aceita somente o nome do arquivo, sem diretórios ou caminhos, e permite as extensões `.py`, `.txt`, `.md`, `.csv`, `.json`, `.yaml`, `.yml`, `.sql` e `.log`. Se o arquivo já existir, pede confirmação antes de sobrescrever.

```python
from tools.filesystem import create_file

result = create_file(
    filename="analise.py",
    content="print('Olá')\n",
)
print(result)
```

O retorno indica sucesso ou erro e, quando criado, informa o caminho em `file_path`.

### 3. `run_script`

Executa um script Python após confirmação explícita do usuário. Por segurança, só é permitido executar scripts criados na sessão atual via `create_file`. A execução usa o mesmo interpretador Python do cliente, não usa `shell` e é interrompida após 30 segundos. Antes de rodar, o script passa por uma varredura estática (`tools/script_safety.py`) que bloqueia padrões perigosos (`eval`, `os.system`, `shell=True`, remoção de arquivos, acesso a credenciais) e exige confirmação reforçada quando o script contém SQL de escrita.

```python
from tools.script_runner import run_script

result = run_script("output/analise.py")
print(result["message"])
print(result.get("stdout", ""))
print(result.get("stderr", ""))
```

O resultado inclui `success`, `returncode`, `stdout` e `stderr`, limitados aos últimos 3.000 caracteres.

### 4. `query_table`

Executa consultas SELECT em tabelas pré-cadastradas do banco de dados (foco atual em SQL Server). Requer `DB_CONN_STRING` configurada — veja [Setup do zero](#-setup-do-zero).

```python
from tools.database import query_table

result = query_table(
    table="NOME_DA_SUA_TABELA",
    conditions=[
        {"column": "Empresa", "operator": "=", "value": "Acme Corp"},
        {"column": "Data_Inicio", "operator": ">=", "value": "2026-01-01"}
    ]
)
print(result)
```

`query_table` é somente leitura. Alterações usam as ferramentas separadas `update_table` (UPDATE) e `delete_table_rows` (DELETE), sempre com filtro obrigatório e confirmação explícita. Inserção de linhas (INSERT) ainda não é suportada. Tabelas, colunas de filtro e colunas editáveis são definidas em `TABELAS_PERMITIDAS`, em `tools/database.py` — cada usuário cadastra as suas.

### 5. `update_table` e `delete_table_rows`

Escrita controlada em tabelas pré-cadastradas, com múltiplas camadas de segurança:
- filtro (`conditions`) obrigatório — não é possível rodar sem WHERE;
- preview: um `SELECT COUNT(*)` roda antes da escrita e o total é comparado com o rowcount real após o commit;
- bloqueio automático se o preview indicar mais linhas do que o limite configurado (`MAX_AFFECTED_ROWS`);
- confirmação reforçada (o usuário precisa digitar uma frase, não apenas "s/N");
- toda tentativa — sucesso, erro ou cancelamento — é registrada em `gemini/db_write_audit_log.jsonl`.

```python
from tools.write_operations import update_table

result = update_table(
    table="NOME_DA_SUA_TABELA",
    set={"Status": "Aprovado"},
    conditions=[{"column": "ID", "operator": "=", "value": "123"}],
)
print(result)
```

### 6. `analyze_sheet_data`

Carrega um CSV ou Excel e aplica agregações, filtros e agrupamentos em uma única chamada.

**Operações suportadas:** `sum`, `mean`, `count`, `min`, `max`, `nunique`, `median`, `std`

```python
from tools.data_analysis import analyze_sheet_data

print(analyze_sheet_data(
    file_path="examples/SampleSuperstore.csv",
    operation="sum",
    target_column="Sales",
    group_by="Segment",
    top_n=3,
))
```

### 7. `analyze_table_data`

Mesma lógica de `analyze_sheet_data`, mas sobre uma tabela pré-cadastrada do banco — o filtro é aplicado diretamente no SQL antes do carregamento.

```python
from tools.data_analysis import analyze_table_data

print(analyze_table_data(
    table="NOME_DA_SUA_TABELA",
    operation="count",
    group_by="Empresa",
    top_n=10,
))
```

### 8. `preview_pdf`, `read_pdf` e `search_in_pdf`

Extraem texto de arquivos `.pdf` usando `pypdf`:

- `preview_pdf`: mostra metadados, número de páginas e um trecho da primeira página
- `read_pdf`: lê um intervalo paginado, com `start_page` e `max_pages`
- `search_in_pdf`: busca texto sem diferenciar maiúsculas e minúsculas e retorna o contexto das ocorrências

```python
from tools.pdf_reader import preview_pdf, read_pdf, search_in_pdf

print(preview_pdf("documentos/relatorio.pdf"))
print(read_pdf("documentos/relatorio.pdf", start_page=0, max_pages=5))
print(search_in_pdf("documentos/relatorio.pdf", query="faturamento", max_matches=10))
```

A numeração de `start_page` é baseada em zero. PDFs protegidos por senha, corrompidos ou sem texto extraível retornam uma mensagem explicativa; PDFs escaneados podem exigir OCR, que ainda não está incluído.

### 9. `plot_sheet_data` e `plot_table_data`

Geram gráficos a partir de uma planilha ou tabela permitida, respectivamente. As operações de agregação são as mesmas de `analyze_sheet_data`/`analyze_table_data`; `chart_type` aceita `bar` ou `line`. **Use apenas quando o usuário pedir explicitamente um gráfico** — para um número ou uma tabela, prefira `analyze_sheet_data`/`analyze_table_data`.

```python
from tools.data_analysis import plot_sheet_data

resultado = plot_sheet_data(
    file_path="examples/SampleSuperstore.csv",
    operation="sum",
    target_column="Sales",
    group_by="Segment",
    chart_type="bar",
)
print(resultado)
```

### 10. `describe_sheet_column` e `describe_table_column`

Retornam estatísticas descritivas de uma coluna (min/max/média/desvio para numéricas e datas; valores mais frequentes para texto). Úteis antes de `analyze_*`/`plot_*`, para decidir `operation`/`group_by` com mais segurança.

### 11. Ferramentas Git

`tools/git_tool.py` fornece leitura de repositórios Git locais e uma ferramenta de edição controlada:

- `git_status` — mudanças staged, unstaged e arquivos não rastreados
- `git_diff_unstaged` — mudanças ainda não adicionadas ao stage
- `git_diff_staged` — mudanças já adicionadas ao stage
- `git_log` — histórico de commits, paginado
- `git_show` — mensagem e diff de um commit específico
- `git_blame` — autoria linha a linha de um arquivo
- `edit_repo_file` — edita um arquivo em um repositório marcado como `writable`, substituindo uma ocorrência única de `old_str` por `new_str`. Exige working tree limpo antes de editar (garante que uma recusa do usuário reverte via `git checkout` sem perda), mostra o diff real e exige confirmação reforçada.

Apenas repositórios cadastrados em `GIT_ALLOWED_REPOS` (em `tools/git_tool.py`) podem ser acessados; caminhos são validados para nunca saírem do repositório permitido, e a saída é limitada a 10.000 caracteres. Por padrão, só o próprio projeto (`gemini_code`) está cadastrado, como somente leitura.

```python
from tools.git_tool import git_diff_unstaged, git_log, git_status

print(git_status("gemini_code"))
print(git_diff_unstaged("gemini_code", path="README.md"))
print(git_log("gemini_code", max_commits=5))
```

Para adicionar outro repositório (ou torná-lo editável), inclua a entrada em `GIT_ALLOWED_REPOS`, em `tools/git_tool.py`.

---

## 🔄 Fluxo de execução com ferramentas

```text
┌─────────────────┐
│ Prompt do user  │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────┐
│ GeminiClient.generate()      │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ Gemini API                   │
└────────┬─────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐  ┌──────────────────┐
│ Texto  │  │ Chamada de tool? │
└────────┘  └────────┬─────────┘
                      │ Sim
                      ▼
             ┌─────────────────────┐
             │ Executa ferramenta  │
             │ (ex: read_file)     │
             └────────┬────────────┘
                       │
                       ▼
             ┌─────────────────────┐
             │ Retorna resultado   │
             │ para o Gemini       │
             └────────┬────────────┘
                       │
                       ▼
             ┌─────────────────────┐
             │ Gemini gera texto   │
             │ final com resultado │
             └─────────────────────┘
```

### 12. Ferramentas Airflow

`tools/airflow_tool.py` fornece monitoramento somente-leitura de DAGs via
API v2 do Airflow (Airflow 3.x):

- `list_dags` — lista os DAGs pré-cadastrados com status (pausado/ativo) e agenda
- `get_dag_runs` — execuções mais recentes de um DAG, com estado e datas
- `get_task_instances` — tasks de uma execução específica, com estado e duração
- `get_task_log` — log de uma task específica, útil para investigar falhas

Apenas DAGs cadastrados em `AIRFLOW_ALLOWED_DAGS` (em `tools/airflow_tool.py`)
podem ser consultados — mesmo padrão de whitelist de `TABELAS_PERMITIDAS` e
`GIT_ALLOWED_REPOS`. A autenticação usa um token JWT obtido via login
(`/auth/token`), cacheado em memória e renovado automaticamente se expirar
no meio da sessão.

```env
AIRFLOW_API_URL=http://sua-vm:8080
AIRFLOW_USERNAME=seu_usuario
AIRFLOW_PASSWORD=sua_senha
```

Essas variáveis devem ser definidas no arquivo `.env` da raiz do projeto.
O `GeminiClient` carrega esse arquivo automaticamente ao ser inicializado.
Se você importar e chamar `tools.airflow_tool` diretamente, carregue o `.env`
antes, por exemplo com `python-dotenv`:

```python
from dotenv import load_dotenv

load_dotenv()

from tools.airflow_tool import list_dags, get_dag_runs, get_task_log

print(list_dags())
print(get_dag_runs("seu_dag_id", max_runs=5))
print(get_task_log("seu_dag_id", run_id="...", task_id="...", try_number=1))
```

**Escopo atual: somente leitura.** Disparar (`trigger_dag`) ou pausar/
despausar DAGs ainda não está implementado — fica como TODO futuro, com o
mesmo tratamento de segurança já usado em `update_table`/`edit_repo_file`
(whitelist própria para escrita, confirmação reforçada, audit log dedicado).

Para adicionar um DAG à whitelist, inclua a entrada em `AIRFLOW_ALLOWED_DAGS`,
em `tools/airflow_tool.py`.

---

## 📊 Logging e monitoramento

| Arquivo | Granularidade | Propósito |
|---|---|---|
| `gemini/gemini_usage_log.jsonl` | 1 linha por `generate()` completo | Custo/consumo — tokens agregados de todas as tentativas internas. Fonte do `/tokens` e `session_summary()`. |
| `gemini/interaction_trace_log.jsonl` | 1 linha por tentativa individual de chamada ao modelo (início + fim/erro) | Diagnóstico de latência/hang. Correlacionado por `call_id`; **não** é fonte de custo. Sempre gravado, mesmo com `/logs` oculto. |
| `gemini/quota_tracker.json` | 1 registro por modelo, resetado por dia civil | Cota diária (RPD) estimada localmente — não histórico, só o dia atual. Fonte do `/quote`. Estimativa própria, não o limite real do Google. |
| `gemini/db_write_audit_log.jsonl` | 1 linha por tentativa de `update_table`/`delete_table_rows` | Auditoria de escrita no banco — sucesso, erro ou cancelamento pelo usuário. |
| `gemini/git_write_audit_log.jsonl` | 1 linha por tentativa de `edit_repo_file` | Auditoria de edição de arquivos em repositórios git. |

Todos os quatro são gerados localmente e não fazem parte do repositório.

### Verificar uso de tokens

```python
from gemini import GeminiClient

client = GeminiClient()
response = client.generate("Seu prompt aqui")

print(f"Input tokens: {response.input_tokens}")
print(f"Output tokens: {response.output_tokens}")
print(f"Total: {response.total_tokens}")

summary = client.session_summary()
print(summary)
# {
#     "calls": 12,
#     "cache_hits": 3,
#     "input_tokens": 1234,
#     "output_tokens": 5678,
#     "total_tokens": 6912
# }
```

---

## 🤝 Contribuindo

Este projeto está em desenvolvimento ativo. Contribuições são bem-vindas!

- 🐛 reporte bugs abrindo uma issue
- 🚀 sugira novas ferramentas
- 📝 melhore a documentação
- 💡 proponha novas funcionalidades

---

## 📝 Roadmap

- [x] ferramentas de análise de dados
- [x] ferramentas de leitura e edição controlada em Git
- [ ] credencial de banco somente leitura na camada de infraestrutura
- [x] suporte a outros bancos de dados
- [ ] integração com armazenamento em nuvem
- [ ] web UI para gerenciar sessões
- [ ] suporte a embeddings e RAG
- [ ] validação de schema para consultas SQL mais robusta
- [ ] suporte a INSERT em tabelas pré-cadastradas

---

## 📄 Licença

Este projeto está licenciado sob a [MIT License](LICENSE) — veja o arquivo [LICENSE](LICENSE) para detalhes completos.

---

## ⚙️ Configuração avançada

### Personalizar comportamento do cliente

```python
from gemini import GeminiClient

client = GeminiClient(
    api_key="sua_chave",
    default_model="gemini-3.5-flash",
    cheap_model="gemini-3.5-flash-lite",
    max_retries=3,
    use_cache=True,
    fallback_models=[
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite"
    ]
)
```

### Limitar tokens de saída

```python
response = client.generate(
    "Explique quantum computing",
    max_output_tokens=500
)
```

### Controlar temperatura (criatividade)

```python
response = client.generate(
    "Qual é 2+2?",
    temperature=0.0
)

response = client.generate(
    "Escreva uma piada sobre Python",
    temperature=1.0
)
```

---

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique a [documentação do Gemini API](https://ai.google.dev/docs)
2. Abra uma issue no repositório
3. Consulte os exemplos em `gemini_terminal.py`

---

Desenvolvido com ❤️ para facilitar a integração com a API do Gemini em projetos Python.