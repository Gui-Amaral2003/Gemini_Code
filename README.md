# Gemini Client

Um cliente Python robusto e reutilizável para a [Google Gemini API](https://ai.google.dev/) com suporte a conversas persistentes, ferramentas customizáveis, retry automático e logging estruturado.

> ⚠️ **Em Desenvolvimento**: Este projeto ainda está em fase inicial. Novas ferramentas e funcionalidades serão adicionadas frequentemente.

## 🎯 Características

- **Cliente Gemini Wrapper**: Interface simplificada sobre a Interactions API do Gemini com tratamento robusto de erros
- **Conversas Persistentes**: Mantém histórico de conversas localmente e recupera sessões anteriores
- **Ferramentas Customizáveis**: Execute funções Python através do Gemini (leitura de arquivos, consultas em banco de dados, etc.)
- **Retry Automático**: Recuperação automática de falhas transitórias com backoff exponencial
- **Cache Inteligente**: Evita chamadas duplicadas ao Gemini
- **Logging Estruturado**: Rastreamento de uso de tokens em arquivo JSON Lines
- **Terminal Interativo**: CLI amigável para conversas via terminal

## 📋 Requisitos

- Python 3.8+
- Chave de API do Google Gemini (obtenha em [ai.google.dev](https://ai.google.dev/))

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
pip install google-genai rich python-dotenv sqlalchemy
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

## 💡 Exemplos de Uso

### Uso Básico

```python
from gemini_client import GeminiClient

client = GeminiClient()

# Geração simples
response = client.generate("Explique o que é uma CTE em SQL")
print(response.text)
print(f"Tokens usados: {response.total_tokens}")
```

### Conversa com Histórico

```python
from gemini_client import GeminiClient, ChatSession

client = GeminiClient()

# Cria uma sessão nomeada (persistida em disco)
chat = ChatSession(
    client=client,
    session_id="meu_tutor_sql",
    system_instruction="Você é um tutor de SQL experiente."
)

# Envia mensagens (histórico é mantido pelo servidor)
r1 = chat.send("O que é uma CTE?")
print(r1.text)

r2 = chat.send("Me dá um exemplo com JOIN.")
print(r2.text)

# Ver histórico local
for msg in chat.get_history():
    print(f"{msg.role}: {msg.text}\n")
```

### Terminal Interativo

```bash
python gemini_terminal.py
```

Comandos disponíveis:
- `/help` - Mostra ajuda
- `/history` - Mostra histórico da sessão
- `/clear` - Limpa o contexto
- `/tokens` - Mostra consumo de tokens
- `/exit` - Sair

### Usando Ferramentas

O Gemini pode executar ferramentas Python automaticamente:

```python
from gemini_client import GeminiClient

client = GeminiClient()

# Pede ao Gemini que leia um arquivo
response = client.generate(
    "Leia o arquivo config.yaml e resuma seu conteúdo"
)
print(response.text)  # Gemini executa read_file() automaticamente
```

### Registrando Processos Reutilizáveis

```python
from gemini_client import GeminiClient, register_process, run_process

client = GeminiClient()

# Registra um processo nomeado
register_process(
    "triagem_logs",
    system="""Você é um assistente de triagem de logs.
              Responda em 3 seções: 
              1. Causa provável
              2. Tipo de erro (transitório/estrutural)
              3. Sugestão de correção"""
)

# Usa o processo em qualquer lugar
log = "[ERROR] Connection timeout..."
response = run_process(client, "triagem_logs", log)
print(response.text)
```

### Carregando Processos de Arquivo

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
from gemini_client import GeminiClient, load_processes, run_process

client = GeminiClient()
load_processes("process.yaml")

response = run_process(client, "log_triage", seu_log_aqui)
print(response.text)
```

## 📁 Estrutura do Projeto

```
gemini/
├── gemini_client.py           # Cliente principal do Gemini
├── gemini_terminal.py         # CLI interativa
├── tools.py                   # Ferramentas customizáveis
├── process.yaml               # Definição de processos reutilizáveis
├── gemini_cache.json          # Cache de respostas (auto-gerado)
├── gemini_usage_log.jsonl     # Log de uso de tokens (auto-gerado)
├── chat_sessions.json         # Sessões persistidas (auto-gerado)
└── README.md                  # Este arquivo
```

## 🛠️ Ferramentas Disponíveis

### 1. `read_file`

Lê o conteúdo de um arquivo de texto.

```python
# O Gemini pode chamar isto automaticamente
response = client.generate("Qual é o tamanho do arquivo config.yaml?")
```

**Parâmetros:**
- `path` (str): Caminho do arquivo

### 2. `query_table`

Executa consultas SELECT em tabelas pré-cadastradas do banco de dados (apenas SQL Server por enquanto).

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

---

## 🔄 Fluxo de Execução com Ferramentas

```
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
│ Gemini API (Interactions)    │
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
client = GeminiClient()
response = client.generate("Seu prompt aqui")

print(f"Input tokens: {response.input_tokens}")
print(f"Output tokens: {response.output_tokens}")
print(f"Total: {response.total_tokens}")

# Resumo da sessão
summary = client.session_summary()
print(summary)
# {
#     "total_input_tokens": 1234,
#     "total_output_tokens": 5678,
#     "total_calls": 12,
#     "cache_hits": 3
# }
```

### Analisar log de uso

```python
from gemini_client import read_usage_log

logs = read_usage_log("gemini_usage_log.jsonl")
for entry in logs[-5:]:  # Últimas 5 chamadas
    print(f"{entry['timestamp']}: {entry['process']} - {entry['total_tokens']} tokens")
```

## 🤝 Contribuindo

Este projeto está em desenvolvimento ativo. Contribuições são bem-vindas!

- 🐛 Reporte bugs abrindo uma issue
- 🚀 Sugira novas ferramentas (tools)
- 📝 Melhore a documentação
- 💡 Proponha novas funcionalidades

## 📝 Roadmap

- [ ] Novas ferramentas de análise de dados
- [ ] Suporte a outros bancos de dados (PostgreSQL, MySQL, etc.)
- [ ] Integração com armazenamento em nuvem (S3, GCS)
- [ ] Web UI para gerenciar sessões
- [ ] Suporte a embeddings e RAG
- [ ] Validação de schema para consultas SQL mais robusta

## 📄 Licença

[Escolha sua licença - ex: MIT]

## ⚙️ Configuração Avançada

### Personalizar comportamento do cliente

```python
client = GeminiClient(
    api_key="sua_chave",                  # API key do Gemini
    default_model="gemini-3.5-flash",     # Modelo padrão
    max_retries=3,                        # Tentativas em falhas transitórias
    use_cache=True,                       # Usar cache de respostas
    fallback_models=[                     # Modelos de fallback em rate limit
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
# Mais previsível (0.0 a 1.0, padrão 0.7)
response = client.generate(
    "Qual é 2+2?",
    temperature=0.0  # Sempre mesma resposta
)

# Mais criativo
response = client.generate(
    "Escreva uma piada sobre Python",
    temperature=1.0  # Respostas variadas
)
```

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique a [documentação do Gemini API](https://ai.google.dev/docs)
2. Abra uma issue no repositório
3. Consulte os exemplos em `gemini_terminal.py`

---

Desenvolvido com ❤️ para facilitar a integração com Google Gemini em projetos Python.
