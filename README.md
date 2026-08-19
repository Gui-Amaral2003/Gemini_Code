# Gemini Client

Cliente Python para a [Google Gemini API](https://ai.google.dev/) com suporte a conversas persistentes, ferramentas customizáveis, retry automático, cache e terminal interativo.

A biblioteca foi reorganizada em um pacote Python dedicado em `gemini/`, mantendo compatibilidade via o wrapper no arquivo raiz `gemini_client.py`.

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
- **Logging estruturado**: monitoramento de uso com arquivo JSONL
- **Terminal interativo**: CLI de demonstração e uso prático

## 📋 Requisitos

- Python 3.8+
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

O arquivo raiz `gemini_client.py` continua funcionando como compatibilidade para imports antigos, mas a organização oficial do projeto passou a ficar em `gemini/`.

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
│   ├── retry.py                # Lógica de retry
│   └── ...
├── tools/
│   ├── __init__.py
│   ├── definitions.py
│   ├── filesystem.py
│   ├── database.py
│   ├── spreadsheet.py
│   ├── data_analysis.py        # Agregação e análise de dados em CSV/XLSX e tabelas
│   ├── pdf_reader.py           # Preview, leitura e busca de texto em PDFs
│   ├── registry.py
│   └── tools.py
├── gemini_client.py            # Compatibilidade para imports antigos
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

### 2. `query_table`

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

### 3. `analyze_sheet_data`

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

### 4. `analyze_table_data`

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

### 5. `preview_pdf`, `read_pdf` e `search_in_pdf`

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
#     "total_input_tokens": 1234,
#     "total_output_tokens": 5678,
#     "total_calls": 12,
#     "cache_hits": 3
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
