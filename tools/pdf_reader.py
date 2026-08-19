##TODO: Suporte a extração de tabelas
##TODO: Suporte a PDFs escaneados via OCR
from pathlib import Path
from typing import Optional
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from .filesystem import resolve_file_path

PDF_EXTENSIONS = {'.pdf'}
PREVIEW_CHARS = 500
CONTEXT_CHARS = 150 # tamanho do trecho de contexto para cada lado do match em search_in_pdf

def _validate_pdf_path(path: str) -> tuple[Optional[Path], Optional[str]]:
    return resolve_file_path(path, allowed_extensions=PDF_EXTENSIONS)

def _load_reader(file_path: Path) -> tuple[Optional[PdfReader], Optional[str]]:
    """Abre o pdf e trata os casos de arquivo protegido/corrompido. Retorna (reader, error_message)"""
    try:
        reader = PdfReader(file_path)

        if reader.is_encrypted:
            # Tenta senha vazia
            try:
                result = reader.decrypt("")
            except Exception:
                result = None

            if not result:
                return None, (
                    f"PDF protegido por senha, não é possível extrair o texto: {file_path.name}"
                )
        return reader, None

    except PdfReadError as e:
        return None, f"Erro ao ler o PDF (arquivo corrompido ou inválido): {e}"
    except Exception as e:
        return None, f"Erro ao abrir o PDF: {e}"

def _extract_page_text(reader: PdfReader, page_index: int) -> str:
    """Extrai o texto de uma página. Retorna string vazia se não houver texto extraível"""
    try:
        return reader.pages[page_index].extract_text() or ""
    except Exception:
        return ""

def preview_pdf(path: str) -> str:
    """
    Mostra o número de páginas, metadados básicos (título/autor) e um preview do
    texto da primeira página. Use antes de ler ou buscar dados para entender a
    estrutura do documento e detectar se ele tem texto extraível.
    """
    file_path, error = _validate_pdf_path(path)
    if error:
        return error

    reader, error = _load_reader(file_path)
    if error:
        return error

    total_pages = len(reader.pages)

    metadata = reader.metadata
    titulo = (metadata.title if metadata and metadata.title else None) or "N/A"
    autor = (metadata.author if metadata and metadata.author else None) or 'N/A'

    first_page_text = _extract_page_text(reader, 0) if total_pages > 0 else ""

    header = (
        f"Arquivo: {file_path.name}\n"
        f"Total de páginas: {total_pages}\n"
        f"Título: {titulo}\n"
        f"Autor: {autor}\n"
    )

    if not first_page_text.strip():
        return header + (
            "\n[Página 1: nenhum texto extraível — possível página escaneada/imagem. "
            "Este PDF pode não ter texto extraível em outras páginas também.]"
        )

    preview = first_page_text[:PREVIEW_CHARS]
    if len(first_page_text) > PREVIEW_CHARS:
        preview += '...'

    return header + f"\nPreview (página 1):\n{preview}"

def read_pdf(path: str, start_page: int = 0, max_pages: int = 10) -> str:
    """
    Lê o texto das páginas de um PDF de forma paginada, começando em start_page
    (0-indexado) e trazendo no máximo max_pages páginas. Indica no final se há
    mais páginas disponíveis e qual start_page usar para continuar a leitura.
    """
    file_path, error = _validate_pdf_path(path)
    if error:
        return error

    reader, error = _load_reader(file_path)
    if error:
        return error

    total_pages = len(reader.pages)

    if total_pages == 0:
        return f"O PDF não contém páginas: {file_path.name}"

    if start_page >= total_pages:
        return (
            f"start_page ({start_page}) é maior ou igual ao total de páginas ({total_pages}). "
            f"Não há mais dados para ler."
        )

    end_page = min(start_page + max_pages, total_pages)

    blocos = []
    houve_texto = False

    for page_index in range(start_page, end_page):
        texto = _extract_page_text(reader, page_index)
        numero_pagina = page_index + 1 #Exobido 1-indexado para o user

        if texto.strip():
            houve_texto = True
            blocos.append(f"--- Página {numero_pagina} ---\n{texto}")
        else:
            blocos.append(
                f"--- Página {numero_pagina} ---\n"
                f"[nenhum texto extraível — possível página escaneada/imagem]"
            )

    footer = f"\n\nMostrando páginas {start_page + 1} a {end_page} de {total_pages}."
 
    if end_page < total_pages:
        footer += f" Para continuar a leitura, use start_page={end_page} na próxima chamada."
 
    if not houve_texto:
        footer += (
            "\n\nAviso: nenhuma página deste intervalo teve texto extraível. "
            "O PDF pode ser majoritariamente escaneado/imagem."
        )
 
    return "\n\n".join(blocos) + footer

def search_in_pdf(path: str, query: str, max_matches: int = 20) -> str:
    """
    Busca um texto (substring, sem diferenciar maiúsculas/minúsculas) em todas as
    páginas de um PDF. Retorna o número da página e um trecho de contexto ao redor
    de cada ocorrência, limitado a max_matches. Útil para localizar um trecho
    específico sem precisar ler o documento inteiro.
    """
    file_path, error = _validate_pdf_path(path)
    if error:
        return error
 
    reader, error = _load_reader(file_path)
    if error:
        return error
 
    total_pages = len(reader.pages)
    query_lower = query.lower()
 
    matches = []
 
    for page_index in range(total_pages):
        texto = _extract_page_text(reader, page_index)
        if not texto:
            continue
 
        texto_lower = texto.lower()
        start_search = 0
 
        while True:
            idx = texto_lower.find(query_lower, start_search)
            if idx == -1:
                break
 
            context_start = max(0, idx - CONTEXT_CHARS)
            context_end = min(len(texto), idx + len(query) + CONTEXT_CHARS)
 
            trecho = texto[context_start:context_end].replace("\n", " ").strip()
            prefixo = "..." if context_start > 0 else ""
            sufixo = "..." if context_end < len(texto) else ""
 
            matches.append((page_index + 1, f"{prefixo}{trecho}{sufixo}"))
 
            start_search = idx + len(query)
 
            if len(matches) >= max_matches:
                break
 
        if len(matches) >= max_matches:
            break
 
    if not matches:
        return f"Nenhuma correspondência encontrada para '{query}'."
 
    linhas = [f"Página {pagina}: {trecho}" for pagina, trecho in matches]
    resultado = "\n\n".join(linhas)
 
    footer = f"\n\n{len(matches)} ocorrência(s) encontrada(s)."
    if len(matches) >= max_matches:
        footer += f" Limitado a {max_matches} — refine a busca se necessário."
 
    return resultado + footer
 