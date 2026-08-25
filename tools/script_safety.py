"""
Varredura estática (regex) de scripts antes de run_script os executar.

Não substitui a defesa real (credencial de banco somente leitura) — serve
como camada adicional para pegar o caso óbvio/ingênuo antes mesmo da
tentativa de conexão, e para forçar uma confirmação informada em vez de
cega quando o script mexe com dados.
"""
import re

# Padrões que indicam escrita/alteração de dados via SQL cru dentro do script. Não bloqueiam a execução, mas exigem confirmação reforçada (digitar uma frase, não apenas s/N).
_SQL_WRITE_PATTERNS = {
    "DELETE": re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    "DROP": re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW)\b", re.IGNORECASE),
    "UPDATE": re.compile(r"\bUPDATE\s+.+\bSET\b", re.IGNORECASE),
    "TRUNCATE": re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
    "ALTER": re.compile(r"\bALTER\s+(TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE),
    "INSERT": re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE),
    "GRANT_REVOKE": re.compile(r"\b(GRANT|REVOKE)\b", re.IGNORECASE),
    "EXEC": re.compile(r"\bEXEC(UTE)?\s*\(", re.IGNORECASE),
}

# Padrões perigosos o suficiente para bloquear a execução por completo, sem oferecer confirmação — não há caso de uso legítimo esperado para essas chamadas num script gerado nesta sessão via create_file.
_HARD_BLOCK_PATTERNS = {
    "shell_true": re.compile(r"shell\s*=\s*True"),
    "os_system": re.compile(r"\bos\.system\s*\("),
    "eval": re.compile(r"\beval\s*\("),
    "exec_builtin": re.compile(r"\bexec\s*\("),
    "rmtree": re.compile(r"shutil\.rmtree\s*\("),
    "os_remove": re.compile(r"\bos\.(remove|unlink)\s*\("),
    "credential_access": re.compile(r"DB_CONN_STRING|GEMINI_API_KEYS"),
}

def scan_script(content: str) -> dict:
    """
    Varre o conteúdo de um script em busca de padrões perigosos.

    Retorna:
      {
        "blocked": list[str],     # motivos que bloqueiam a execução por completo
        "sql_writes": list[str],  # operações de escrita SQL (exigem confirmação reforçada)
      }
    """
    blocked = [nome for nome, padrao in _HARD_BLOCK_PATTERNS.items() if padrao.search(content)]
    sql_writes = [nome for nome, padrao in _SQL_WRITE_PATTERNS.items() if padrao.search(content)]
    return {"blocked": blocked, "sql_writes": sql_writes}