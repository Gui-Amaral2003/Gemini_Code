from pathlib import Path
from typing import Optional

ALLOWED_SEARCH_DIRS = [
    Path.home() / 'Documents'
]

MAX_SEARCH_RESULTS = 5 #Evita listas grandes em caso de nome genérico

def resolve_file_path(
    name_or_path: str,
    allowed_extensions: Optional[set[str]] = None,
) -> tuple[Optional[Path], Optional[str]]:
    """
    Resolve um nome de arquivo (ou path já completo) para um Path existente.

    - Se já for um path absoluto/relativo que existe, usa direto (a checagem
      de extensão, se houver, fica a cargo de quem chama).
    - Caso contrário, busca por nome (case-insensitive) dentro de
      ALLOWED_SEARCH_DIRS.
    - allowed_extensions filtra a busca (ex: {'.xlsx', '.csv'}). Se None,
      aceita qualquer extensão — útil para tools genéricas como read_file.
    - Se o nome já vier com extensão, ela é usada para restringir a busca
      independente de allowed_extensions (assim "relatorio.pdf" não bate
      com "relatorio.xlsx" mesmo que ambos sejam aceitos pelo caller).

    Retorna (path, error_message). Em caso de ambiguidade ou não encontrado,
    error_message já vem formatado para o modelo se autocorrigir.
    """
    direct = Path(name_or_path)
    if direct.exists() and direct.is_file():
        return direct, None

    stem = direct.stem
    suffix = direct.suffix.lower()

    if suffix:
        candidates_ext = {suffix}
    elif allowed_extensions:
        candidates_ext = {e.lower() for e in allowed_extensions}
    else:
        candidates_ext = None  # qualquer extensão

    matches: list[Path] = []
    for base_dir in ALLOWED_SEARCH_DIRS:
        if not base_dir.exists():
            continue
        for path in base_dir.rglob("*"):
            if not path.is_file():
                continue
            if candidates_ext is not None and path.suffix.lower() not in candidates_ext:
                continue
            if path.stem.lower() == stem.lower():
                matches.append(path)

    if not matches:
        return None, (
            f"Arquivo '{name_or_path}' não encontrado em "
            f"{', '.join(str(d) for d in ALLOWED_SEARCH_DIRS)}. "
        )

    if len(matches) > 1:
        listed = "\n".join(f"- {m}" for m in matches[:MAX_SEARCH_RESULTS])
        return None, (
            f"Mais de um arquivo encontrado para '{name_or_path}':\n{listed}\n"
            f"Especifique o caminho completo."
        )

    return matches[0], None
    
def read_file(path: str) -> str:
    """Lê um arquivo de texto. Aceita nome do arquivo (busca automática) ou caminho completo."""

    file_path, error = resolve_file_path(path)
    if error:
        return error

    try:
        return file_path.read_text(encoding="utf-8")

    except UnicodeDecodeError:
        return f"Erro ao decodificar o arquivo: {path}. Certifique-se de que está em UTF-8."

    except OSError as e:
        return f"Erro ao ler o arquivo: {path}. Detalhes: {e}"
