import subprocess
import sys
from pathlib import Path
from .confirmation import confirm_action, confirm_action_typed
from .script_safety import scan_script

MAX_OUTPUT_LENGTH = 3000
MAX_CONFIRM_PREVIEW = 800
CONFIRM_PHRASE = "EXECUTAR"

def run_script(path: str) -> dict:
    """
    Executa um script Python após confirmação explícita do usuário. Scripts
    são varridos por padrões perigosos antes da execução (ver script_safety.py):
    padrões críticos bloqueiam por completo; operações de escrita SQL exigem
    confirmação reforçada (digitar uma frase) em vez de s/N.
    """
    script_path = Path(path)

    if script_path.suffix.lower() != '.py':
        return {
            "error": "Apenas arquivos .py podem ser executados."
        }

    if not script_path.exists():
        return {
            "error": f"O arquivo '{path}' não existe."
        }

    if not script_path.is_file():
        return {
            "error": f"O caminho '{path}' não é um arquivo."
        }

    try:
        conteudo = script_path.read_text(encoding="utf-8")
    except OSError as e:
        return {"error": f"Erro ao ler o script para validação: {e}"}

    scan = scan_script(conteudo)

    if scan["blocked"]:
        return {
            "success": False,
            "error": (
                "Execução bloqueada por segurança. O script contém padrão(ões) não "
                f"permitido(s): {', '.join(scan['blocked'])}. run_script não executa "
                "scripts com chamadas de shell, eval/exec, remoção de arquivos do "
                "sistema ou acesso a credenciais sensíveis."
            ),
        }

    preview = conteudo[:MAX_CONFIRM_PREVIEW]
    if len(conteudo) > MAX_CONFIRM_PREVIEW:
        preview += "\n...[truncado]"

    if scan["sql_writes"]:
        mensagem = (
            f"⚠ O script '{path}' contém operação(ões) de escrita em banco de dados "
            f"({', '.join(scan['sql_writes'])}).\n\nConteúdo:\n{preview}"
        )
        if not confirm_action_typed(mensagem, CONFIRM_PHRASE):
            return {
                "success": False,
                "message": "Operação cancelada — confirmação reforçada não fornecida.",
            }
    else:
        mensagem = f"Tem certeza que deseja executar o script '{path}'?\n\nConteúdo:\n{preview}"
        if not confirm_action(mensagem):
            return {"success": False, "message": "Operação cancelada pelo usuário."}

    try:
        process = subprocess.run(
            [sys.executable, str(script_path)],
            shell=False,
            timeout=30,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "O script excedeu o limite de execução de 30 segundos."
        }
    except OSError as e:
        return {
            "success": False,
            "error": f"Erro ao executar o script: {e}"
        }

    stdout = process.stdout[-MAX_OUTPUT_LENGTH:]
    stderr = process.stderr[-MAX_OUTPUT_LENGTH:]

    if process.returncode != 0:
        return {
            "success": False,
            "returncode": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "message": "O script terminou com erro.",
        }

    return {
        "success": True,
        "returncode": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "message": "Script executado com sucesso.",
    }