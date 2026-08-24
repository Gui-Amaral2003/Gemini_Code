import pytest

from tools import database
from tools.validation import QueryValidationError


TABELA = "TEST_DOA_DEALS"
SCHEMA = database.TABELAS_PERMITIDAS[TABELA]["schema"]
COLUNAS_RETORNO = database.TABELAS_PERMITIDAS[TABELA]["colunas_retorno"]
COLUNAS_SQL = ", ".join(f"[{c}]" for c in COLUNAS_RETORNO)
SELECT_BASE = f"SELECT TOP {database.MAX_ROWS} {COLUNAS_SQL} FROM [{SCHEMA}].[{TABELA}]"


# --------------------------------------------------------------------------- #
# _build_query
# --------------------------------------------------------------------------- #

def test_build_query_tabela_nao_permitida():
    with pytest.raises(QueryValidationError, match="Tabela não permitida"):
        database._build_query("TABELA_INEXISTENTE", [])


def test_build_query_sem_conditions():
    sql, params = database._build_query(TABELA, [])

    assert sql == SELECT_BASE
    assert params == []


def test_build_query_uma_condition_int():
    sql, params = database._build_query(
        TABELA, [{"column": "ID", "operator": "=", "value": "123"}]
    )

    assert sql == SELECT_BASE + " WHERE [ID] = :param_0"
    assert params == [123]
    assert isinstance(params[0], int)


def test_build_query_uma_condition_str():
    sql, params = database._build_query(
        TABELA, [{"column": "Company", "operator": "!=", "value": "Acme"}]
    )

    assert sql == SELECT_BASE + " WHERE [Company] != :param_0"
    assert params == ["Acme"]


def test_build_query_uma_condition_date():
    sql, params = database._build_query(
        TABELA, [{"column": "Supply_Start", "operator": ">=", "value": "2026-01-01"}]
    )

    assert sql == SELECT_BASE + " WHERE [Supply_Start] >= :param_0"
    assert params == ["2026-01-01"]


def test_build_query_multiplas_conditions_usa_and_e_indices_sequenciais():
    sql, params = database._build_query(
        TABELA,
        [
            {"column": "Company", "operator": "=", "value": "Acme"},
            {"column": "ID", "operator": ">", "value": "10"},
            {"column": "Supply_Start", "operator": ">=", "value": "2026-01-01"},
        ],
    )

    assert sql == (
        SELECT_BASE
        + " WHERE [Company] = :param_0 AND [ID] > :param_1 AND [Supply_Start] >= :param_2"
    )
    assert params == ["Acme", 10, "2026-01-01"]


def test_build_query_operador_like_envolve_valor_em_percent():
    sql, params = database._build_query(
        TABELA, [{"column": "WBC_TERM", "operator": "LIKE", "value": "abc"}]
    )

    assert sql == SELECT_BASE + " WHERE [WBC_TERM] LIKE :param_0"
    assert params == ["%abc%"]


def test_build_query_coluna_de_filtro_invalida_propaga_erro():
    with pytest.raises(QueryValidationError, match="Coluna não permitida"):
        database._build_query(
            TABELA, [{"column": "coluna_inexistente", "operator": "=", "value": "1"}]
        )


def test_build_query_operador_invalido_para_tipo_propaga_erro():
    # ID é 'int' — LIKE não está entre os operadores válidos para esse tipo.
    with pytest.raises(QueryValidationError, match="Operador"):
        database._build_query(
            TABELA, [{"column": "ID", "operator": "LIKE", "value": "1"}]
        )


def test_build_query_bloqueia_coluna_de_retorno_com_identifier_invalido(monkeypatch):
    """Guard de última linha: mesmo que o catálogo TABELAS_PERMITIDAS venha mal
    configurado (coluna de retorno não é um identifier válido), _build_query
    não deve montar SQL — precisa recusar antes de interpolar a string."""
    monkeypatch.setitem(
        database.TABELAS_PERMITIDAS,
        "FAKE_TABLE",
        {
            "schema": "dbo",
            "colunas_filtro": {"ID": "int"},
            "colunas_retorno": ["ID", "col; DROP TABLE"],
        },
    )

    with pytest.raises(QueryValidationError, match="coluna de retorno inválido"):
        database._build_query("FAKE_TABLE", [])


# --------------------------------------------------------------------------- #
# fetch_table_dataframe / query_table — validação roda antes de qualquer I/O
# --------------------------------------------------------------------------- #

def _bloquear_get_engine(monkeypatch):
    """Faz get_engine() explodir se for chamada — usado para provar que o
    caminho de erro de validação nunca chega perto de tentar conectar."""
    def _falha():
        raise AssertionError("get_engine() não deveria ter sido chamada")

    monkeypatch.setattr(database, "get_engine", _falha)


def test_fetch_table_dataframe_tabela_invalida_nao_toca_engine(monkeypatch):
    _bloquear_get_engine(monkeypatch)

    df, error = database.fetch_table_dataframe("TABELA_INEXISTENTE", [])

    assert df is None
    assert error.startswith("Requisição rejeitada:")
    assert "Tabela não permitida" in error


def test_fetch_table_dataframe_condition_invalida_nao_toca_engine(monkeypatch):
    _bloquear_get_engine(monkeypatch)

    df, error = database.fetch_table_dataframe(
        TABELA, [{"column": "coluna_inexistente", "operator": "=", "value": "1"}]
    )

    assert df is None
    assert error.startswith("Requisição rejeitada:")
    assert "Coluna não permitida" in error


def test_query_table_tabela_invalida_retorna_string_de_erro(monkeypatch):
    _bloquear_get_engine(monkeypatch)

    resultado = database.query_table("TABELA_INEXISTENTE", [])

    assert isinstance(resultado, str)
    assert resultado.startswith("Requisição rejeitada:")