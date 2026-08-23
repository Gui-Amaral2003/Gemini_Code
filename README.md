# Gemini Client

Cliente Python para a [Google Gemini API](https://ai.google.dev/) com suporte a conversas persistentes, ferramentas customizáveis, retry automático, cache, roteamento entre modelos e terminal interativo.

A biblioteca foi reorganizada em um pacote Python dedicado em `gemini/`. O arquivo `old_gemini_client.py` é mantido como referência para a implementação anterior.

> ⚠️ **Em Desenvolvimento**: Este projeto ainda está em fase inicial. Novas ferramentas e funcionalidades serão adicionadas frequentemente.

## 🎯 Características

- **Pacote principal em `gemini/`**: organização modular para cliente, sessão, modelos e configurações
- **Cliente Gemini Wrapper**: interface simples sobre a API do Google Gemini com tratamento robusto de erros
- **Conversas persistentes**: histórico local e recuperação de sessões anteriores
- **Ferramentas customizáveis**: execução de funções Python a partir do modelo
- **Análise de dados integrada**: sumarização, filtros e agregações em planilhas e tabelas pré-cadastradas
- **Leitura de PDFs**: preview, leitura paginada e busca de texto em arquivos PDF
- **Retry automático**: recuperação de falhas transitórias com backoff exponencial
- **Cache inteligente**: evita chamadas duplicadas e reduz custo de tokens
- **Roteamento multi-modelo**: usa um modelo mais barato para sintetizar a resposta depois de ferramentas terminais, preservando o modelo forte para decisões de novas ferramentas
- **Geração de gráficos**: cria gráficos de barras ou linhas no terminal e salva PNGs temporários para aprovação do usuário
- **Logging estruturado**: monitoramento de uso com arquivo JSONL
- **Terminal interativo**: CLI de demonstração e uso prático

## 📋 Requisitos

- Python 3.10+
- Chave de API do Google Gemini: [ai.google.dev](https://ai.google.dev/)

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone <seu-repositorio>
cd gemini
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

Ou manualmente:

```bash
pip install google-genai rich python-dotenv sqlalchemy pandas openpyxl tabulate pyyaml pyodbc
```

### 3. Configure a API Key

Defina sua chave de API do Gemini de uma destas formas:

**Opção A: Variável de ambiente**
```bash
export GEMINI_API_KEY=sua_chave_aqui
```

**Opção B: Arquivo `.env` (recomendado)**
```
# .env
GEMINI_API_KEY=sua_chave_aqui
DB_CONN_STRING=sua_connection_string_opcional
```

## 💡 Importando o pacote

A importação recomendada agora é via o pacote `gemini`:

```python
from gemini import GeminiClient, ChatSession, load_processes, run_process
```

O arquivo `old_gemini_client.py` contém a implementação anterior para referência. A organização oficial do projeto fica em `gemini/`.

## 🧪 Exemplos de Uso

### Uso Básico

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
- `/help` - mostra ajuda
- `/history` - mostra histórico da sessão
- `/clear` - limpa o contexto
- `/tokens` - mostra consumo de tokens
- `/exit` - sai do terminal

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

Para perguntas que exigem soma, média, contagem, mínimo, máximo ou outra agregação,
as ferramentas `analyze_sheet_data` e `analyze_table_data` devem ser usadas. As
ferramentas `read_sheet`, `preview_sheet` e `query_table` servem para explorar ou
exibir dados, não para substituir uma agregação calculada pela ferramenta.

### Roteamento entre modelos

O cliente pode usar um modelo mais barato na etapa de síntese depois que todas as
ferramentas chamadas em uma rodada forem terminais. Isso reduz o custo sem transferir
para o modelo barato a decisão de qual ferramenta chamar. Se o modelo barato pedir
outra ferramenta, a rodada é refeita com o modelo padrão.

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

O roteamento considera terminais `analyze_sheet_data`, `analyze_table_data`,
`plot_sheet_data`, `plot_table_data`, `search_in_pdf` e `search_in_sheet`. Ferramentas
exploratórias, como `preview_sheet`, `read_sheet`, `query_table` e `read_pdf`, mantêm
o modelo forte para a próxima decisão.

### Geração de gráficos

Use `plot_sheet_data` para CSV/Excel ou `plot_table_data` para tabelas permitidas no
banco. Os tipos disponíveis são `bar` e `line`.

```python
response = client.generate(
    "Gere um gráfico de barras das vendas por segmento em "
    "examples/SampleSuperstore.csv"
)

for file_path in response.generated_files:
    print(f"PNG gerado: {file_path}")
```

As ferramentas exibem uma versão no terminal e salvam o PNG em
`output/plots_staging/`. O `GeminiResponse.generated_files` contém os arquivos
gerados. No terminal interativo, o usuário decide se cada arquivo será movido para
`output/plots/` ou descartado.

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

## 📁 Estrutura do Projeto

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
│   └── ...
├── tools/
│   ├── __init__.py
│   ├── definitions.py
│   ├── filesystem.py
│   ├── confirmation.py          # Confirmações explícitas para operações sensíveis
│   ├── script_runner.py         # Execução confirmada de scripts Python
│   ├── database.py
│   ├── spreadsheet.py
│   ├── data_analysis.py        # Agregação e análise de dados em CSV/XLSX e tabelas
│   ├── pdf_reader.py           # Preview, leitura e busca de texto em PDFs
│   ├── plotting.py             # Renderização no terminal e geração de PNGs
│   ├── git_tool.py              # Leitura de status, diffs, histórico e autoria Git
│   └── registry.py              # Registro das ferramentas executáveis
├── old_gemini_client.py        # Implementação anterior, mantida para referência
├── gemini_terminal.py          # CLI interativa
├── process.yaml                # Definição de processos reutilizáveis
├── requirements.txt
├── README.md
├── LICENSE
├── TODO.md
├── examples/
├── tests/
└── ...
```

## 🛠️ Ferramentas Disponíveis

### 1. `read_file`

Lê o conteúdo de um arquivo de texto.

```python
response = client.generate("Qual é o tamanho do arquivo config.yaml?")
```

**Parâmetros:**
- `path` (str): Caminho do arquivo

### 2. `create_file`

Cria um arquivo dentro de `output/`. A ferramenta aceita somente o nome do arquivo,
sem diretórios ou caminhos, e permite as extensões `.py`, `.txt`, `.md`, `.csv`,
`.json`, `.yaml`, `.yml`, `.sql` e `.log`. Se o arquivo já existir, solicita
confirmação antes de sobrescrevê-lo.

```python
from tools import create_file

result = create_file(
    filename="analise.py",
    content="print('Olá')\n",
)
print(result)
```

O retorno indica sucesso ou erro e, quando criado, informa o caminho em
`file_path`.

### 3. `run_script`

Executa um script Python após confirmação explícita do usuário. O caminho pode ser
o arquivo criado por `create_file` ou outro arquivo `.py` existente. A execução usa
o mesmo interpretador Python do cliente, não usa `shell`, e é interrompida após 30
segundos.

```python
from tools import run_script

result = run_script("output/analise.py")
print(result["message"])
print(result.get("stdout", ""))
print(result.get("stderr", ""))
```

O resultado inclui `success`, `returncode`, `stdout` e `stderr`. Para evitar respostas
excessivamente grandes, `stdout` e `stderr` ficam limitados aos últimos 3.000
caracteres. Scripts cancelados, inexistentes, que não sejam arquivos `.py`, ou que
excedam o tempo limite retornam uma mensagem de erro ou cancelamento.

### 4. `query_table`

Executa consultas SELECT em tabelas pré-cadastradas do banco de dados (atualmente com foco em SQL Server).

**Tabelas suportadas:**
- `TEST_DOA_DEALS` (schema `rsk`)

**Exemplo:**
```python
from tools import query_table

result = query_table(
    table="TEST_DOA_DEALS",
    conditions=[
        {"column": "Company", "operator": "=", "value": "Acme Corp"},
        {"column": "Supply_Start", "operator": ">=", "value": "2026-01-01"}
    ]
)
print(result)
```

### 5. `analyze_sheet_data`

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

### 6. `analyze_table_data`

Executa a mesma lógica sobre uma tabela permitida do banco de dados, aplicando filtros em memória após o carregamento.

```python
from tools.data_analysis import analyze_table_data

print(analyze_table_data(
    table="TEST_DOA_DEALS",
    operation="count",
    group_by="Company",
    top_n=10,
))
```

### 7. `preview_pdf`, `read_pdf` e `search_in_pdf`

As ferramentas de PDF extraem texto de arquivos `.pdf` usando `pypdf`:

- `preview_pdf`: mostra metadados, número de páginas e um trecho da primeira página
- `read_pdf`: lê um intervalo paginado, com `start_page` e `max_pages`
- `search_in_pdf`: busca texto sem diferenciar maiúsculas e minúsculas e retorna o contexto das ocorrências

```python
from tools.pdf_reader import preview_pdf, read_pdf, search_in_pdf

print(preview_pdf("documentos/relatorio.pdf"))
print(read_pdf("documentos/relatorio.pdf", start_page=0, max_pages=5))
print(search_in_pdf("documentos/relatorio.pdf", query="faturamento", max_matches=10))
```

A numeração de `start_page` é baseada em zero. Quando ainda houver páginas, `read_pdf` informa o próximo valor de `start_page` para continuar. PDFs protegidos por senha, corrompidos ou sem texto extraível retornam uma mensagem explicativa; PDFs escaneados podem exigir OCR, que ainda não está incluído.

### 8. `plot_sheet_data` e `plot_table_data`

Geram gráficos a partir de uma planilha ou tabela permitida, respectivamente. As
operações de agregação são as mesmas de `analyze_sheet_data` e `analyze_table_data`;
`chart_type` aceita `bar` ou `line`.

```python
from tools.data_analysis import plot_sheet_data

png_path = plot_sheet_data(
    file_path="examples/SampleSuperstore.csv",
    operation="sum",
    target_column="Sales",
    group_by="Segment",
    chart_type="bar",
)
print(png_path)
```

O gráfico também é renderizado no terminal com `plotext`. O arquivo PNG é salvo
temporariamente em `output/plots_staging/`; a aplicação que chamou o cliente é
responsável por movê-lo ou removê-lo.

### 9. Ferramentas Git

O módulo `tools/git_tool.py` fornece ferramentas somente leitura para consultar
repositórios Git locais:

- `git_status`: mostra mudanças staged, unstaged e arquivos não rastreados
- `git_diff_unstaged`: mostra mudanças ainda não adicionadas ao stage
- `git_diff_staged`: mostra mudanças já adicionadas ao stage
- `git_log`: lista o histórico de commits com paginação
- `git_show`: mostra a mensagem e o diff de um commit
- `git_blame`: mostra a autoria linha a linha de um arquivo

Por segurança, as ferramentas aceitam somente nomes de repositórios definidos em
`GIT_ALLOWED_REPOS`; não executam comandos de escrita e não recebem flags livres
do modelo. Caminhos de arquivos são validados para permanecerem dentro do
repositório permitido, e a saída é limitada a 10.000 caracteres.

O repositório deste projeto já vem cadastrado com o nome `gemini_code`:

```python
from tools import git_diff_unstaged, git_log, git_status

print(git_status("gemini_code"))
print(git_diff_unstaged("gemini_code", path="README.md"))
print(git_log("gemini_code", max_commits=5))
```

Para adicionar outro repositório, inclua seu nome e caminho em `GIT_ALLOWED_REPOS`
no arquivo `tools/git_tool.py`.

---

## 🔄 Fluxo de Execução com Ferramentas

```text
┌─────────────────┐
│ Prompt do User  │
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
    │          │
    ▼          ▼
┌────────┐  ┌──────────────────┐
│ Texto  │  │ Chamada de Tool? │
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
            │ para Gemini         │
            └────────┬────────────┘
                     │
                     ▼
            ┌─────────────────────┐
            │ Gemini gera texto   │
            │ final com resultado │
            └─────────────────────┘
```

## 📊 Logging e Monitoramento

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

## 🤝 Contribuindo

Este projeto está em desenvolvimento ativo. Contribuições são bem-vindas!

- 🐛 reporte bugs abrindo uma issue
- 🚀 sugira novas ferramentas
- 📝 melhore a documentação
- 💡 proponha novas funcionalidades

## 📝 Roadmap

- [x] ferramentas de análise de dados
- [ ] suporte a outros bancos de dados
- [ ] integração com armazenamento em nuvem
- [ ] web UI para gerenciar sessões
- [ ] suporte a embeddings e RAG
- [ ] validação de schema para consultas SQL mais robusta

## 📄 Licença

Este projeto está licenciado sob a [MIT License](LICENSE) - veja o arquivo [LICENSE](LICENSE) para detalhes completos.

## ⚙️ Configuração Avançada

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

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique a [documentação do Gemini API](https://ai.google.dev/docs)
2. Abra uma issue no repositório
3. Consulte os exemplos em `gemini_terminal.py`

---

Desenvolvido com ❤️ para facilitar a integração com Google Gemini em projetos Python.
