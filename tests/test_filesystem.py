import pytest

from tools import filesystem


# --------------------------------------------------------------------------- #
# resolve_file_path
# --------------------------------------------------------------------------- #

def test_resolve_file_path_direto_existente(tmp_path):
    """Se o path já existe (absoluto ou relativo), usa direto — nem chega a buscar."""
    arquivo = tmp_path / "relatorio.csv"
    arquivo.write_text("a,b\n1,2\n", encoding="utf-8")

    resolved, error = filesystem.resolve_file_path(str(arquivo))

    assert error is None
    assert resolved == arquivo


def test_resolve_file_path_busca_por_nome_um_match(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem, "ALLOWED_SEARCH_DIRS", [tmp_path])

    arquivo = tmp_path / "vendas.xlsx"
    arquivo.write_text("conteudo", encoding="utf-8")

    resolved, error = filesystem.resolve_file_path("vendas")

    assert error is None
    assert resolved == arquivo


def test_resolve_file_path_busca_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem, "ALLOWED_SEARCH_DIRS", [tmp_path])

    arquivo = tmp_path / "Vendas.CSV"
    arquivo.write_text("conteudo", encoding="utf-8")

    resolved, error = filesystem.resolve_file_path("vendas.csv")

    assert error is None
    assert resolved == arquivo


def test_resolve_file_path_filtra_por_allowed_extensions(tmp_path, monkeypatch):
    """Sem extensão no nome pedido, allowed_extensions restringe a busca —
    um arquivo de mesmo stem mas extensão fora da lista não deve casar."""
    monkeypatch.setattr(filesystem, "ALLOWED_SEARCH_DIRS", [tmp_path])

    (tmp_path / "dados.txt").write_text("nao deveria casar", encoding="utf-8")
    esperado = tmp_path / "dados.csv"
    esperado.write_text("deveria casar", encoding="utf-8")

    resolved, error = filesystem.resolve_file_path(
        "dados", allowed_extensions={".csv", ".xlsx"}
    )

    assert error is None
    assert resolved == esperado


def test_resolve_file_path_extensao_no_nome_restringe_mesmo_com_allowed_extensions_mais_amplo(tmp_path, monkeypatch):
    """'relatorio.pdf' não deve casar com 'relatorio.xlsx' mesmo se
    allowed_extensions aceitar ambas — a extensão explícita no nome pedido
    tem prioridade sobre allowed_extensions."""
    monkeypatch.setattr(filesystem, "ALLOWED_SEARCH_DIRS", [tmp_path])

    (tmp_path / "relatorio.xlsx").write_text("planilha", encoding="utf-8")

    resolved, error = filesystem.resolve_file_path(
        "relatorio.pdf", allowed_extensions={".xlsx", ".pdf"}
    )

    assert resolved is None
    assert "não encontrado" in error


def test_resolve_file_path_ambiguo(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem, "ALLOWED_SEARCH_DIRS", [tmp_path])

    subpasta = tmp_path / "sub"
    subpasta.mkdir()
    (tmp_path / "dados.csv").write_text("um", encoding="utf-8")
    (subpasta / "dados.csv").write_text("dois", encoding="utf-8")

    resolved, error = filesystem.resolve_file_path("dados.csv")

    assert resolved is None
    assert "Mais de um arquivo encontrado" in error
    assert "dados.csv" in error


def test_resolve_file_path_nao_encontrado(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem, "ALLOWED_SEARCH_DIRS", [tmp_path])

    resolved, error = filesystem.resolve_file_path("inexistente.csv")

    assert resolved is None
    assert "não encontrado" in error


def test_resolve_file_path_relativo_nao_existente_cai_na_busca(tmp_path, monkeypatch):
    """Um path com diretório embutido que não existe (ex: 'pasta/arquivo.csv')
    não deve ser tratado como direto — cai no fluxo de busca por stem e,
    não encontrando, retorna erro de não encontrado (não um erro de I/O cru)."""
    monkeypatch.setattr(filesystem, "ALLOWED_SEARCH_DIRS", [tmp_path])

    resolved, error = filesystem.resolve_file_path("pasta_inexistente/arquivo.csv")

    assert resolved is None
    assert "não encontrado" in error


def test_resolve_file_path_ignora_diretorio_inexistente_em_allowed_search_dirs(tmp_path, monkeypatch):
    """Se um dos ALLOWED_SEARCH_DIRS não existir no disco, a busca não deve
    quebrar — só ignora esse diretório e segue procurando nos demais."""
    dir_inexistente = tmp_path / "nao_existe"
    dir_real = tmp_path / "real"
    dir_real.mkdir()
    (dir_real / "dados.csv").write_text("conteudo", encoding="utf-8")

    monkeypatch.setattr(filesystem, "ALLOWED_SEARCH_DIRS", [dir_inexistente, dir_real])

    resolved, error = filesystem.resolve_file_path("dados.csv")

    assert error is None
    assert resolved == dir_real / "dados.csv"


# --------------------------------------------------------------------------- #
# read_file
# --------------------------------------------------------------------------- #

def test_read_file_sucesso(tmp_path):
    arquivo = tmp_path / "notas.txt"
    arquivo.write_text("conteúdo em português com acentuação", encoding="utf-8")

    resultado = filesystem.read_file(str(arquivo))

    assert resultado == "conteúdo em português com acentuação"


def test_read_file_propaga_erro_de_resolve(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem, "ALLOWED_SEARCH_DIRS", [tmp_path])

    resultado = filesystem.read_file("nao_existe.txt")

    assert "não encontrado" in resultado


def test_read_file_erro_de_encoding(tmp_path):
    arquivo = tmp_path / "binario.txt"
    # bytes inválidos em UTF-8 (0xFF não é um byte inicial válido)
    arquivo.write_bytes(b"\xff\xfe\x00\x01")

    resultado = filesystem.read_file(str(arquivo))

    assert "Erro ao decodificar" in resultado


# --------------------------------------------------------------------------- #
# create_file
# --------------------------------------------------------------------------- #

@pytest.fixture
def output_dir(tmp_path, monkeypatch):
    """Redireciona OUTPUT_DIR para dentro de tmp_path em todos os testes de create_file."""
    destino = tmp_path / "output"
    monkeypatch.setattr(filesystem, "OUTPUT_DIR", destino)
    return destino


def test_create_file_rejeita_filename_com_diretorio(output_dir):
    resultado = filesystem.create_file("../fora.py", "print(1)")

    assert "error" in resultado
    assert "somente o nome do arquivo" in resultado["error"]
    assert not output_dir.exists()


def test_create_file_rejeita_filename_com_subpasta(output_dir):
    resultado = filesystem.create_file("sub/dentro.py", "print(1)")

    assert "error" in resultado
    assert "somente o nome do arquivo" in resultado["error"]


def test_create_file_rejeita_extensao_nao_permitida(output_dir):
    resultado = filesystem.create_file("script.exe", "conteudo")

    assert "error" in resultado
    assert "Extensão" in resultado["error"]


def test_create_file_sucesso(output_dir):
    resultado = filesystem.create_file("analise.py", "print('ola')\n")

    assert resultado["success"] is True
    destino = output_dir / "analise.py"
    assert destino.exists()
    assert destino.read_text(encoding="utf-8") == "print('ola')\n"
    assert resultado["file_path"] == str(destino)


def test_create_file_sobrescreve_com_confirmacao(output_dir, monkeypatch):
    destino = output_dir / "existente.py"
    output_dir.mkdir(parents=True)
    destino.write_text("versao antiga", encoding="utf-8")

    monkeypatch.setattr(filesystem, "confirm_action", lambda mensagem: True)

    resultado = filesystem.create_file("existente.py", "versao nova")

    assert resultado["success"] is True
    assert destino.read_text(encoding="utf-8") == "versao nova"


def test_create_file_cancela_sem_confirmacao(output_dir, monkeypatch):
    destino = output_dir / "existente.py"
    output_dir.mkdir(parents=True)
    destino.write_text("versao antiga", encoding="utf-8")

    monkeypatch.setattr(filesystem, "confirm_action", lambda mensagem: False)

    resultado = filesystem.create_file("existente.py", "versao nova")

    assert resultado["success"] is False
    assert "cancelada" in resultado["message"]
    # Conteúdo original preservado — a sobrescrita não deve ter ocorrido.
    assert destino.read_text(encoding="utf-8") == "versao antiga"