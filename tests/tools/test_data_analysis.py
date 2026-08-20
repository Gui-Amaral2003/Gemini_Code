import pandas as pd
import pytest

from tools.data_analysis import (
    _apply_conditions,
    _compute_aggregation,
    _validate_analysis_inputs,
    _analyze_data,
)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "Region": ["Sul", "Sul", "Norte", "Norte", "Norte", "Sul"],
        "Category": ["A", "B", "A", "A", "B", "A"],
        "Sales": [100, 50, 200, 300, 150, 80],
    })


# --------------------------------------------------------------------------- #
# _compute_aggregation SEM group_by -> retorna um valor escalar (não uma Series)
# --------------------------------------------------------------------------- #
def test_aggregation_sum_without_groupby(sample_df):
    resultado, error = _compute_aggregation(sample_df, "sum", target_column="Sales")

    assert error is None
    assert resultado == 880  # 100+50+200+300+150+80


def test_aggregation_count_without_target_column(sample_df):
    resultado, error = _compute_aggregation(sample_df, "count", target_column=None)

    assert error is None
    assert resultado == 6


def test_aggregation_on_empty_dataframe_returns_error():
    df_vazio = pd.DataFrame(columns=["Region", "Sales"])
    resultado, error = _compute_aggregation(df_vazio, "sum", target_column="Sales")

    assert resultado is None
    assert error == "Nenhum dado encontrado após aplicar o filtro"


# --------------------------------------------------------------------------- #
# _compute_aggregation COM group_by -> retorna uma pandas Series.
# --------------------------------------------------------------------------- #
def test_aggregation_sum_grouped_sorted_descending(sample_df):
    resultado, error = _compute_aggregation(
        sample_df, "sum", target_column="Sales", group_by="Region"
    )

    assert error is None
    # Norte: 200+300+150=650 | Sul: 100+50+80=230
    # sort_ascending=False (padrão) -> maior primeiro
    esperado = pd.Series(
        [650, 230],
        index=pd.Index(["Norte", "Sul"], name="Region"),
        name="Sales",
    )
    pd.testing.assert_series_equal(resultado, esperado)


def test_aggregation_grouped_top_n_limits_rows(sample_df):
    resultado, error = _compute_aggregation(
        sample_df, "sum", target_column="Sales", group_by="Category", top_n=1
    )

    assert error is None
    assert len(resultado) == 1
    # Categoria A: 100+200+300+80=680 | B: 50+150=200 -> top 1 é "A"
    assert resultado.index[0] == "A"


def test_aggregation_grouped_sort_ascending(sample_df):
    resultado, error = _compute_aggregation(
        sample_df, "sum", target_column="Sales", group_by="Region", sort_ascending=True
    )

    assert error is None
    # agora o menor (Sul, 230) deve vir primeiro
    assert list(resultado.index) == ["Sul", "Norte"]


# --------------------------------------------------------------------------- #
# _apply_conditions -> reaproveita validate_conditions (já testado) e aplica 
# os filtros sobre o DataFrame.
# --------------------------------------------------------------------------- #
def test_apply_conditions_numeric_filter(sample_df):
    column_types = {"Region": "str", "Category": "str", "Sales": "int"}
    conditions = [{"column": "Sales", "operator": ">", "value": "100"}]

    filtrado = _apply_conditions(sample_df, conditions, column_types)

    assert len(filtrado) == 3  # 200, 300, 150
    assert filtrado["Sales"].min() > 100


def test_apply_conditions_like_filter(sample_df):
    column_types = {"Region": "str", "Category": "str", "Sales": "int"}
    conditions = [{"column": "Region", "operator": "LIKE", "value": "nort"}]

    filtrado = _apply_conditions(sample_df, conditions, column_types)

    assert len(filtrado) == 3
    assert set(filtrado["Region"]) == {"Norte"}


# --------------------------------------------------------------------------- #
# _validate_analysis_inputs -> mensagens de erro para entrada inválida.
# --------------------------------------------------------------------------- #
def test_validate_inputs_rejects_unknown_operation(sample_df):
    erro = _validate_analysis_inputs(sample_df, "somar_tudo", "Sales", None)
    assert erro is not None
    assert "somar_tudo" in erro


def test_validate_inputs_rejects_unknown_target_column(sample_df):
    erro = _validate_analysis_inputs(sample_df, "sum", "ColunaQueNaoExiste", None)
    assert erro is not None
    assert "ColunaQueNaoExiste" in erro


def test_validate_inputs_requires_target_column_except_count(sample_df):
    erro = _validate_analysis_inputs(sample_df, "sum", None, None)
    assert erro is not None
    assert "target_column" in erro


def test_validate_inputs_accepts_count_without_target_column(sample_df):
    erro = _validate_analysis_inputs(sample_df, "count", None, None)
    assert erro is None


# --------------------------------------------------------------------------- #
# _analyze_data -> o orquestrador de ponta a ponta (valida -> filtra -> agrega
# -> formata). Testamos o TEXTO final, que é o que o modelo realmente recebe.
# --------------------------------------------------------------------------- #
def test_analyze_data_scalar_result_text(sample_df):
    texto = _analyze_data(sample_df, operation="sum", target_column="Sales")
    assert texto == "Resultado (sum de Sales): 880"


def test_analyze_data_grouped_result_is_markdown_table(sample_df):
    texto = _analyze_data(
        sample_df, operation="sum", target_column="Sales", group_by="Region"
    )
    # to_markdown gera uma tabela com | como separador — só garantimos que
    # os nomes das regiões aparecem, sem acoplar no formato exato do markdown.
    assert "Norte" in texto
    assert "Sul" in texto


def test_analyze_data_top_n_warning_appears_when_truncated(sample_df):
    texto = _analyze_data(
        sample_df, operation="sum", target_column="Sales", group_by="Region", top_n=1
    )
    assert "Mostrando top 1 de 2 grupos" in texto


def test_analyze_data_invalid_filter_returns_readable_error(sample_df):
    conditions = [{"column": "ColunaFalsa", "operator": "=", "value": "x"}]
    texto = _analyze_data(sample_df, operation="sum", target_column="Sales", conditions=conditions)
    assert texto.startswith("Filtro inválido:")