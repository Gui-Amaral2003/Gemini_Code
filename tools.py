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





# Funções que o Python realmente pode executar.
TOOLS = {
    "read_file": read_file,
}


# Descrição das ferramentas que será enviada ao Gemini.
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "read_file",
        "description": "Lê o conteúdo de um arquivo de texto.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho do arquivo que deve ser lido.",
                }
            },
            "required": ["path"],
        },
    }
]