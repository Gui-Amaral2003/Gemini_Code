import pytest

from tools.validation import (
    validate_conditions,
    QueryValidationError,
    _coerce_value
)

@pytest.fixture
def column_types():
    return {
        "ID": "int",
        "Company": "str",
        "Supply_Start": "date",
        "Price": "float",
    }

# --------------------------------------------------------------------------- #
# CASOS DE SUCESSO
# --------------------------------------------------------------------------- #
def test_valid_int_condition(column_types):
    conditions = [{"column": "ID", "operator": "=", "value": "42"}]
 
    result = validate_conditions(conditions, column_types)
 
    assert result == [("ID", "=", 42)]  

def test_valid_str_condition_with_equals(column_types):
    conditions = [{"column": "Company", "operator": "=", "value": "Acme"}]
    result = validate_conditions(conditions, column_types)
    assert result == [("Company", "=", "Acme")]
 
 
def test_empty_conditions_returns_empty_list(column_types):
    # Lista vazia (ou None) não deveria gerar erro nenhum — é o caso de
    # "buscar sem filtro nenhum".
    assert validate_conditions([], column_types) == []
    assert validate_conditions(None, column_types) == []

# --------------------------------------------------------------------------- #
# CASOS DE ERRO
# --------------------------------------------------------------------------- #
def test_column_not_in_catalog_is_rejected(column_types):
    conditions = [{"column": "SenhaSecreta", "operator": "=", "value": "x"}]
 
    with pytest.raises(QueryValidationError):
        validate_conditions(conditions, column_types)
 
 
def test_operator_not_allowed_for_type(column_types):
    # '>' não faz sentido pra uma coluna string no _OPERATORS_BY_TYPE
    conditions = [{"column": "Company", "operator": ">", "value": "Acme"}]
 
    with pytest.raises(QueryValidationError):
        validate_conditions(conditions, column_types)
 
 
def test_invalid_int_value_is_rejected(column_types):
    conditions = [{"column": "ID", "operator": "=", "value": "não-é-numero"}]
 
    with pytest.raises(QueryValidationError):
        validate_conditions(conditions, column_types)
 
 
def test_invalid_date_format_is_rejected(column_types):
    conditions = [{"column": "Supply_Start", "operator": "=", "value": "31/12/2026"}]
 
    with pytest.raises(QueryValidationError):
        validate_conditions(conditions, column_types)
 
 

@pytest.mark.parametrize(
    "raw_value, expected",
    [
        ("busca", "%busca%"),      # sem % -> a função envolve automaticamente
        ("%busca%", "%busca%"),    # já tem % -> não duplica
        ("%busca", "%busca"),      # só um lado -> respeita o que veio
    ],
)
def test_like_operator_wraps_percent(column_types, raw_value, expected):
    conditions = [{"column": "Company", "operator": "LIKE", "value": raw_value}]
    result = validate_conditions(conditions, column_types)
    assert result == [("Company", "LIKE", expected)]
 
 
@pytest.mark.parametrize(
    "value, tipo, expected",
    [
        ("10", "int", 10),
        ("10.5", "float", 10.5),
        ("2026-01-15", "date", "2026-01-15"),
        (123, "str", "123"),
    ],
)
def test_coerce_value_happy_paths(value, tipo, expected):
    assert _coerce_value(value, tipo, coluna="qualquer") == expected
 
 
def test_coerce_value_raises_on_bad_float():
    with pytest.raises(QueryValidationError):
        _coerce_value("não-é-float", "float", coluna="Price")
 