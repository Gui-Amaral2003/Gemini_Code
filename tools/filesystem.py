from pathlib import Path

def read_file(path: str) -> str:
    """Lê um arquivo de texto."""

    file_path = Path(path)

    if not file_path.exists():
        return f"Arquivo não encontrado: {path}"

    if not file_path.is_file():
        return f"O caminho não é um arquivo: {path}"

    try:
        return file_path.read_text(encoding="utf-8")

    except UnicodeDecodeError:
        return f"Erro ao decodificar o arquivo: {path}. Certifique-se de que está em UTF-8."

    except OSError as e:
        return f"Erro ao ler o arquivo: {path}. Detalhes: {e}"
