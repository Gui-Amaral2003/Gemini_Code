# Changelog

## 0.1.0 — 2026-10-21 (alpha)

Primeira versão distribuível do Gemini Terminal.

### Funcionalidades

- CLI `gemini-terminal`, instalação com `pipx` e integrações opcionais.
- Conversação com Gemini, function calling, fallback e classificação de erros 429.
- Sessões persistentes, histórico, autocomplete, trace e estimativa local de quota.
- Ferramentas para arquivos, Git, CSV/Excel, análise, gráficos, PDF, SQL Server, Hive e Airflow.
- `/config` para diagnóstico local e `/config edit` para configuração assistida.
- `/config resources` para cadastrar Git, DAGs e tabelas com permissões de colunas.
- Catálogos TOML locais validados e gravação atômica.
- Confirmação humana e auditoria para operações sensíveis.

### Correções e distribuição

- Criação do diretório do histórico antes da primeira gravação.
- Detecção do módulo `puresasl` e declaração de `tabulate` nos extras de dados.
- Carregamento tardio de ferramentas e dependências opcionais.
- Arquivo `.env` global compartilhado pela inicialização, assistente e diagnóstico.
- Prioridade das variáveis do ambiente preservada, inclusive no diagnóstico.
- CI com lint, testes em Python 3.11/3.12 e instalação do wheel fora do repositório.

### Migração e limitações

- Os antigos `.env`, sessões e allowlists não são migrados automaticamente. Consulte [configuração](docs/configuration.md).
- Configuração e catálogos exigem reiniciar o terminal após alterações.
- Timeout de espera não encerra uma ferramenta Python já em execução.
- O quota tracker é uma estimativa local; scripts não possuem sandbox de sistema operacional.
- A versão é alpha; valide com dados de teste e consulte [segurança e limites](docs/security.md).
