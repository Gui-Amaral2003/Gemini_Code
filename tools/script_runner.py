import subprocess
import sys
from pathlib import Path
from .confirmation import confirm_action

MAX_OUTPUT_LENGTH = 3000

def run_script(path: str) -> dict:
    """
    Executa um script Python após confirmação explícita do usuário
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

    if not confirm_action(f"Tem certeza que deseja executar o script '{path}'?"):
        return {
            "success": False,
            "message": "Operação cancelada pelo usuário."
        }

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