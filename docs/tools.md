# Catálogo de ferramentas

As definições expostas ao modelo ficam em `tools/definitions.py`. Implementação e políticas são associadas em `tools/registry.py`.

## Arquivos e scripts

- `read_file`: leitura paginada;
- `create_file`: cria arquivo após confirmação;
- `run_script`: executa somente scripts registrados como criados na sessão.

Scripts passam por validação estática e timeout próprio. Isso reduz risco, mas não substitui um sandbox de sistema operacional.

## Planilhas e CSV

- `list_sheets`, `preview_sheet`, `read_sheet`, `search_in_sheet`;
- `analyze_sheet_data`, `describe_sheet_column`;
- `plot_sheet_data`.

Agregações devem ser feitas por `analyze_sheet_data`; o modelo não deve recalcular totais a partir de uma amostra retornada por `read_sheet`.

## Banco de dados

- `query_table` para leitura;
- `analyze_table_data` e `describe_table_column` para análise;
- `plot_table_data` para visualização;
- `update_table` e `delete_table_rows` para escrita confirmada.

O modelo escolhe somente tabelas, colunas e conexões cadastradas. Filtros são validados e valores são enviados como parâmetros SQL.

## PDF

- `preview_pdf`, `read_pdf`, `search_in_pdf`.

As operações são paginadas e limitadas para evitar inserir documentos inteiros no contexto sem necessidade.

## Git

- status, diff staged/unstaged, log, show e blame;
- `edit_repo_file` para edição confirmada em repositórios permitidos.

## Airflow

- `list_dags`, `get_dag_runs`, `get_task_instances`, `get_task_log`.

A integração atual é somente-leitura e aceita apenas DAGs cadastrados.

## Adicionando uma ferramenta

1. implemente uma função pequena e testável em `tools/`;
2. declare o schema em `TOOL_DEFINITIONS`;
3. registre uma `ToolPolicy` com timeout, roteamento e confirmação apropriados;
4. adicione testes de validação, sucesso, erro e limites;
5. execute `python -m ruff check .` e `python -m pytest -q`.
