"""
Módulo neutro de validação de condições de filtro.
Não depende de SQL nem de pandas — é reaproveitado tanto por database.py
(query_table) quanto por data_analysis.py (analyze_data).
"""
import re
from typing import Any

class QueryValidationError(ValueError):
    """Erro de validação de query."""


_OPERATORS_BY_TYPE = {
    "int": {"=", "!=", ">", "<", ">=", "<="},
    "float": {"=", "!=", ">", "<", ">=", "<="},
    "date": {"=", "!=", ">", "<", ">=", "<="},
    "str": {"=", "!=", "LIKE"}
}

# Validação extra de indentificadores válidos
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _validate_identifier(name: str, label: str) -> None:
    if not _IDENTIFIER_RE.match(name):
        raise QueryValidationError(f"{label} inválido: {name!r}")

def _coerce_value(value, tipo: str, coluna: str):
    """Converte o valor para o tipo esperado"""
    try:
        if tipo == 'int':
            return int(value)
        if tipo == 'float':
            return float(value)
        if tipo == 'date':
            # Aceita YYYY-MM-DD, deixa o driver validar o formato final
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
                raise ValueError
            return str(value)
        if tipo == 'str':
            return str(value)

    except (ValueError, TypeError) as e:
        raise QueryValidationError(f"Erro ao converter valor para coluna {coluna}: {value}. Detalhes: {e}")

def validate_conditions(
    conditions: list[dict],
    column_types: dict[str, str],
) -> list[tuple[str, str, Any]]:
    """
    Valida cada condição de filtro contra column_types (coluna -> tipo esperado).

    Cada condição deve ter as chaves 'column', 'operator' e 'value'.

    Retorna uma lista de tuplas (column, operator, coerced_value) já validadas,
    neutra em relação ao consumidor (SQL ou pandas).

    Lança QueryValidationError em caso de coluna/operador/valor inválido.
    """
    validated: list[tuple[str, str, Any]] = []

    for cond in conditions or []:
        column = cond.get("column")
        operator = cond.get("operator")
        value = cond.get("value")

        if column not in column_types:
            raise QueryValidationError(
                f"Coluna não permitida para filtro: {column}. "
                f"Disponíveis: {list(column_types)}"
            )

        _validate_identifier(column, "coluna de filtro")

        expected_type = column_types[column]
        valid_operators = _OPERATORS_BY_TYPE[expected_type]

        if operator not in valid_operators:
            raise QueryValidationError(
                f"Operador '{operator}' não é permitido para a coluna '{column}' "
                f"(tipo {expected_type}). Permitidos: {sorted(valid_operators)}"
            )

        coerced_value = _coerce_value(value, expected_type, column)

        if operator == "LIKE":
            # o próprio valor pode ter % embutido; se não tiver, envolve automaticamente
            if "%" not in coerced_value:
                coerced_value = f"%{coerced_value}%"

        validated.append((column, operator, coerced_value))

    return validated