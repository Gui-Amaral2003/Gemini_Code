"""
Ferramentas de escrita controlada (UPDATE/DELETE) em tabelas pré-cadastradas.
 
Layer de segurança em cima do que já existe em database.py:
- Mesmo catálogo TABELAS_PERMITIDAS, mas exige a chave 'colunas_editaveis'
  (whitelist própria, separada de colunas_filtro) para qualquer coluna que
  vá para o SET de um UPDATE.
- WHERE (conditions) é SEMPRE obrigatório e não pode vir vazio — bloqueia
  antes mesmo de montar a query, para as duas operações.
- Preview: roda um SELECT COUNT(*) com o mesmo WHERE antes de qualquer
  escrita. O número é mostrado ao usuário na tela de confirmação E
  comparado com o rowcount real após a execução — se divergir (alteração
  concorrente na tabela entre o preview e o commit), a transação é
  revertida e a operação retorna erro.
- Cap de segurança: se o preview indicar mais linhas do que
  MAX_AFFECTED_ROWS, a operação é bloqueada por completo. Não existe
  confirmação que contorne isso — o filtro precisa ficar mais específico.
- Confirmação reforçada (digitar 'EXECUTAR'), mesmo padrão já usado para
  SQL write dentro de run_script (ver script_safety.py / script_runner.py).
- Toda tentativa (sucesso, erro ou cancelamento pelo usuário) é registrada
  em WRITE_AUDIT_LOG_PATH.
 
TODO: DB_CONN_STRING hoje é compartilhada entre leitura e escrita — ver
get_write_engine() abaixo. O plano é migrar para uma DB_CONN_STRING_WRITE
dedicada, com um usuário de banco que só tenha GRANT de UPDATE/DELETE
(nunca DROP/TRUNCATE/ALTER/INSERT). A troca fica isolada nesta função,
sem precisar tocar em update_table/delete_table_rows.
 
TODO: INSERT não está coberto aqui — o padrão de preview (COUNT antes de
executar) não se aplica da mesma forma a uma linha que ainda não existe.
Fica como ferramenta separada, se/quando for necessária.
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional
import sqlalchemy
from .confirmation import confirm_action_typed
from .database import TABELAS_PERMITIDAS, get_engine
from .validation import (
    QueryValidationError,
    _validate_identifier,
    validate_conditions,
    _coerce_value
)

logger = logging.getLogger("gemini_client")

MAX_AFFECTED_ROWS = 500
CONFIRM_PHRASE = "EXECUTAR"
WRITE_AUDIT_LOG_PATH = Path("gemini/db_write_audit_log.jsonl")

def get_write_engine(connection_name: str):
    """
    Engine usada por update_table/delete_table_rows. Hoje recebe a conexão
    da própria tabela (config["connection"]) — na prática, sempre resolve
    para "sqlserver_main", já que Hive não tem colunas_editaveis cadastradas
    (ver TABELAS_PERMITIDAS em database.py). Mantido como parâmetro em vez
    de fixo para não precisar mexer aqui de novo se um dia uma conexão
    Hive/MySQL ACID for liberada para escrita — mas atenção: o SQL deste
    módulo (_build_where, _execute_write) ainda assume colchetes de
    identificador ([schema].[table]), que é sintaxe mssql. Se/quando
    escrita em outro dialeto for necessária, este módulo também precisa
    ficar dialect-aware (mesma lógica de _quote_identifier de database.py).
    """
    return get_engine(connection_name)

def _validate_table_and_columns(table: str, set_values: Optional[dict]) -> tuple[Optional[dict], Optional[str]]:
    """Valida a tabela e, se houver set_values, as colunas contra colunas_editaveis."""
    if table not in TABELAS_PERMITIDAS:
        return None, f"Tabela não permitida: {table}. Disponíveis: {list(TABELAS_PERMITIDAS)}"
 
    config = TABELAS_PERMITIDAS[table]
 
    if set_values is not None:
        colunas_editaveis = config.get("colunas_editaveis", {})
 
        if not colunas_editaveis:
            return None, f"Tabela '{table}' não tem nenhuma coluna liberada para edição."
 
        colunas_invalidas = [c for c in set_values if c not in colunas_editaveis]
        if colunas_invalidas:
            return None, (
                f"Coluna(s) não editável(is): {', '.join(colunas_invalidas)}. "
                f"Editáveis em '{table}': {list(colunas_editaveis)}"
            )
 
    return config, None

def _coerce_set_values(set_values: dict, colunas_editaveis: dict) -> tuple[Optional[dict], Optional[str]]:
    coerced = {}
    for coluna, valor in set_values.items():
        try:
            coerced[coluna] = _coerce_value(valor, colunas_editaveis[coluna], coluna)
        except QueryValidationError as e:
            return None, str(e)
    return coerced, None

def _build_where(config: dict, conditions: dict) -> tuple[Optional[str], Optional[dict], Optional[str]]:
    """Monta a cláusula WHERE parametrizada (params prefixados 'where_'). Vazio é sempre rejeitado."""

    if not conditions:
        return None, None, (
            "Esta operação exige pelo menos uma condição de filtro (WHERE). "
            "Operações sem filtro não são permitidas, mesmo intencionalmente."
        )
    
    try:
        validated = validate_conditions(conditions, config["colunas_filtro"])
    except QueryValidationError as e:
        return None, None, f"Erro ao validar condições: {str(e)}"

    clauses = []
    params = {}

    for i, (coluna, operador, valor) in enumerate(validated):
        param_name = f"where_{i}"
        clauses.append(f"[{coluna}] {operador} :{param_name}")
        params[param_name] = valor

    return " AND ".join(clauses), params, None

def _preview_count(engine, schema: str, table: str, where_sql: str, where_params: dict) -> tuple[Optional[int], Optional[str]]:
    sql = f"SELECT COUNT(*) AS total FROM [{schema}].[{table}] WHERE {where_sql}"
    try:
        with engine.connect() as conn:
            total = conn.execute(sqlalchemy.text(sql), where_params).scalar_one()
    except Exception as e:
        return None, f"Erro ao calcular o preview de linhas afetadas: {e}"
    return int(total), None

def _log_audit(entry: dict) -> None:
    entry["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        WRITE_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(WRITE_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        logger.warning("Não consegui gravar o audit log de escrita: %s", e)

def _execute_write(table, operation: str, conditions: list[dict], set_values: Optional[dict] = None) -> dict:
    config, error = _validate_table_and_columns(table, set_values)
    if error:
        return {"success": False, "error": error}

    schema = config["schema"]
    connection_name = config['connection']
    _validate_identifier(schema, 'schema')
    _validate_identifier(table, 'tabela')

    where_sql, where_params, error = _build_where(config, conditions)
    if error:
        return {"success": False, "error": error}

    set_clause_sql = None
    set_params = {}
    coerced_set = None

    if operation == "UPDATE":
        coerced_set, error = _coerce_set_values(set_values, config["colunas_editaveis"])
        if error:
            return {"success": False, "error": error}

        set_pieces = []
        for i, (coluna, valor) in enumerate(coerced_set.items()):
            _validate_identifier(coluna, 'coluna do SET')
            param_name = f"set_{i}"
            set_pieces.append(f"[{coluna}] = :{param_name}")
            set_params[param_name] = valor
        set_clause_sql = ", ".join(set_pieces)

    engine = get_write_engine(connection_name)

    preview_total, error = _preview_count(engine, schema, table, where_sql, where_params)
    if error:
        return {"success": False, "error": error}

    if preview_total == 0:
        return {"success": False, "error": "Nenhuma linha corresponde às condições fornecidas."}

    if preview_total > MAX_AFFECTED_ROWS:
        return {"success": False, "error": f"Preview indica {preview_total} linhas afetadas, acima do limite de {MAX_AFFECTED_ROWS}. Refine o filtro."}

    if operation == 'UPDATE':
        sql = f"UPDATE [{schema}].[{table}] SET {set_clause_sql} WHERE {where_sql}"
        all_params = {**set_params, **where_params}
    else:
        sql = f"DELETE FROM [{schema}].[{table}] WHERE {where_sql}"
        all_params = where_params

    condicoes_legiveis = "\n".join(f"  - {c['column']} {c['operator']} {c['value']}" for c in conditions)
 
    mensagem = f"⚠ Operação: {operation} em [{schema}].[{table}]\n\n"

    if coerced_set:
        alteracoes = "\n".join(f"  - {k} = {v}" for k, v in coerced_set.items())
        mensagem += f"Alterações:\n{alteracoes}\n\n"
    mensagem += f"Filtro (WHERE):\n{condicoes_legiveis}\n\nLinhas afetadas: {preview_total}\n"
 
    if not confirm_action_typed(mensagem, CONFIRM_PHRASE):
        _log_audit({"operation": operation, "table": table, "success": False, "cancelled": True})
        return {"success": False, "message": "Operação cancelada pelo usuário."}

    try:
        with engine.begin() as conn:
            result = conn.execute(sqlalchemy.text(sql), all_params)
            rowcount = result.rowcount
            if rowcount != preview_total:
                raise RuntimeError(f"Contagem de linhas afetadas diverge do preview: {rowcount} vs {preview_total}.")

    except Exception as e:
        _log_audit({"operation": operation, "table": table, "success": False, "error": str(e), "sql": sql})
        return {"success": False, "error": f"Erro ao executar {operation}: {e}"}
 
    _log_audit({"operation": operation, "table": table, "success": True, "rowcount": rowcount, "sql": sql})
 
    return {
        "success": True,
        "rowcount": rowcount,
        "message": f"{operation} executado com sucesso em [{schema}].[{table}] — {rowcount} linha(s) afetada(s).",
    }

# --------------------------------------------------------------------------- #
# Tools expostas ao Gemini
# --------------------------------------------------------------------------- #
 
def update_table(table: str, set: dict, conditions: list[dict]) -> dict:
    """
    Atualiza (UPDATE) linhas de uma tabela pré-cadastrada. Exige pelo menos
    uma condição de filtro (conditions não pode ser vazio) e mostra ao
    usuário o SQL e a contagem de linhas afetadas antes de pedir
    confirmação reforçada. Bloqueado se o filtro atingir mais de
    MAX_AFFECTED_ROWS linhas.
    """
    if not set:
        return {"success": False, "error": "set não pode ser vazio para um UPDATE."}
    return _execute_write(table, "UPDATE", conditions, set_values=set)
 
 
def delete_table_rows(table: str, conditions: list[dict]) -> dict:
    """
    Apaga (DELETE) linhas de uma tabela pré-cadastrada. Exige pelo menos
    uma condição de filtro (conditions não pode ser vazio) e mostra ao
    usuário o SQL e a contagem de linhas afetadas antes de pedir
    confirmação reforçada. Bloqueado se o filtro atingir mais de
    MAX_AFFECTED_ROWS linhas.
    """
    return _execute_write(table, "DELETE", conditions, set_values=None)