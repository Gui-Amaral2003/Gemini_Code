##TODO: Implementar multiplos parametros no groupby, no momento apenas um parametro é aceito
import pandas as pd
from .validation import (
    validate_conditions,
    QueryValidationError,
    _validate_identifier
)
from .database import TABELAS_PERMITIDAS, MAX_ROWS, QUERY_TIMEOUT_SECONDS
from .filesystem import resolve_file_path
_VALID_OPERATIONS = {'sum', 'mean', 'count', 'min', 'max', 'nunique', 'median', 'std'}

def _infer_column_types(df: pd.DataFrame) -> dict[str, str]:
    tipos = {}
    for coluna, dtype in df.dtypes.items():
        if pd.api.types.is_integer_dtype(dtype):
            tipos[coluna] = "int"
        elif pd.api.types.is_float_dtype(dtype):
            tipos[coluna] = "float"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            tipos[coluna] = "date"
        else:
            tipos[coluna] = "str"
    return tipos

def _apply_conditions(df: pd.DataFrame, conditions: list[dict], column_types: dict[str, str]) -> pd.DataFrame:
    validated = validate_conditions(conditions, column_types)

    mask = pd.Series(True, index = df.index)

    for coluna, operador, valor in validated:
        serie = df[coluna]

        # Coluna é data real (datetime64) mas o valor validado vem como string 'YYYY-MM-DD'
        if column_types[coluna] == 'date':
            valor = pd.to_datetime(valor)

        if operador == "=":
            mask &= (serie == valor)
        elif operador == "!=":
            mask &= (serie != valor)
        elif operador == ">":
            mask &= (serie > valor)
        elif operador == "<":
            mask &= (serie < valor)
        elif operador == ">=":
            mask &= (serie >= valor)
        elif operador == "<=":
            mask &= (serie <= valor)
        elif operador == 'LIKE':
            # Valor já vem envolvido em % pelo validate_conditions
            padrao = valor.strip('%')
            mask &= serie.astype(str).str.contains(padrao, case = False, na = False)
    return df[mask]

def _analyze_data(df: pd.DataFrame, operation: str, target_column: str | None = None, group_by: str | None = None, conditions: list[dict] | None = None, top_n: int | None = None, sort_ascending: bool = False) -> str:
    """
    Executa uma agregação (com groupby opcional) sobre um DataFrame já carregado.

    operation: sum, mean, count, min, max, nunique, median, std
    target_column: coluna a agregar (opcional se operation="count" e group_by=None)
    group_by: uma única coluna de agrupamento (TODO: suportar múltiplas colunas/métricas)
    conditions: mesmo formato de filtro usado em query_table
    top_n: limita quantas linhas do groupby são retornadas
    sort_ascending: ordena o resultado do groupby pelo valor agregado
    """

    if operation not in _VALID_OPERATIONS:
        return (
            f"Operação inválida: {operation}"
            f"Disponíveis: {sorted(_VALID_OPERATIONS)}"
        )

    column_types = _infer_column_types(df)

    # Validação de colunas referenciadas
    if target_column is not None and target_column not in df.columns:
        return (
            f"Coluna de análise não encontrada: {target_column}. "
            f"Disponíveis: {list(df.columns)}"
        )

    if group_by is not None and group_by not in df.columns:
        return (
            f"Coluna de agrupamento não encontrada: {group_by}. "
            f"Disponíveis: {list(df.columns)}"
        )

    if target_column is None and operation != 'count':
        return f"target_column é obrigatório para a operação '{operation}'"

    # Filtro
    try:
        if conditions:
            df = _apply_conditions(df, conditions, column_types)
    except QueryValidationError as e:
        return f"Filtro inválido: {e}"

    if df.empty:
        return 'Nenhum dado encontrado após aplicar o filtro'

    # Agragação sem groupby
    if group_by is None:
        if operation == 'count' and target_column is None:
            resultado = len(df)
        else:
            resultado = getattr(df[target_column], operation)()

        return f"Resultado ({operation}{f' de {target_column}' if target_column else ''}): {resultado}"

    # Agregação com groupby
    if operation == "count" and target_column is None:
        agrupado = df.groupby(group_by).size()
    else:
        agrupado = df.groupby(group_by)[target_column].agg(operation)

    agrupado = agrupado.sort_values(ascending=sort_ascending)

    total_grupos = len(agrupado)

    if top_n is not None:
        agrupado = agrupado.head(top_n)

    resultado_df = agrupado.reset_index()
    resultado_df.columns = [group_by, f"{operation}_{target_column or 'count'}"]

    tabela_md = resultado_df.to_markdown(index=False)

    aviso = ""
    if top_n is not None and total_grupos > top_n:
        aviso = f"\n\n_Mostrando top {top_n} de {total_grupos} grupos. Refine o filtro para ver mais._"

    return f"{tabela_md}{aviso}"

SPREADSHEET_EXTENSIONS = {".xlsx", ".xls", ".csv"}

def analyze_sheet_data(
    file_path: str,
    sheet_name: str | None = None,
    operation: str = "sum",
    target_column: str | None = None,
    group_by: str | None = None,
    conditions: list[dict] | None = None,
    top_n: int | None = None,
    sort_ascending: bool = False,
) -> str:
    """
    Carrega uma planilha (.xlsx/.csv) e executa uma análise agregada sobre ela.
    Aceita o nome do arquivo (busca automática) ou o caminho completo.
    """
    resolved_path, error = resolve_file_path(file_path, allowed_extensions=SPREADSHEET_EXTENSIONS)
    if error:
        return error

    try:
        if resolved_path.suffix.lower() == ".csv":
            df = pd.read_csv(resolved_path)
        else:
            df = pd.read_excel(resolved_path, sheet_name=sheet_name or 0)
    except FileNotFoundError:
        return f"Arquivo não encontrado: {resolved_path}"
    except ValueError as e:
        # ex: sheet_name inválido — o próprio pandas/openpyxl lista as abas disponíveis
        return f"Erro ao abrir a planilha: {e}"
    except Exception as e:
        return f"Erro ao ler o arquivo: {e}"

    return _analyze_data(
        df,
        operation=operation,
        target_column=target_column,
        group_by=group_by,
        conditions=conditions,
        top_n=top_n,
        sort_ascending=sort_ascending,
    )

def analyze_table_data(
    table: str,
    operation: str = "sum",
    target_column: str | None = None,
    group_by: str | None = None,
    conditions: list[dict] | None = None,
    top_n: int | None = None,
    sort_ascending: bool = False,
) -> str:
    import os
    import sqlalchemy
    """
    Carrega uma tabela pré-cadastrada em TABELAS_PERMITIDAS (sem aplicar filtro no SQL,
    apenas o limite de segurança MAX_ROWS) e executa uma análise agregada sobre ela.
    O filtro (conditions) é sempre aplicado em pandas, dentro de _analyze_df.
    """
    if table not in TABELAS_PERMITIDAS:
        return (
            f"Tabela não permitida: {table}. "
            f"Disponíveis: {list(TABELAS_PERMITIDAS)}"
        )

    config = TABELAS_PERMITIDAS[table]
    schema = config["schema"]
    colunas_retorno = config["colunas_retorno"]

    _validate_identifier(schema, "schema")
    _validate_identifier(table, "tabela")
    for col in colunas_retorno:
        _validate_identifier(col, "coluna de retorno")

    colunas_sql = ", ".join(f"[{c}]" for c in colunas_retorno)
    sql = f"SELECT TOP {MAX_ROWS} {colunas_sql} FROM [{schema}].[{table}]"

    try:
        conn_string = os.environ.get("DB_CONN_STRING")
        engine = sqlalchemy.create_engine(conn_string, connect_args={"timeout": QUERY_TIMEOUT_SECONDS})

        with engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(sql), conn)
    except Exception as e:
        return f"Erro ao carregar a tabela: {e}"

    if df.empty:
        return "Nenhum dado encontrado na tabela."

    return _analyze_data(
        df,
        operation=operation,
        target_column=target_column,
        group_by=group_by,
        conditions=conditions,
        top_n=top_n,
        sort_ascending=sort_ascending,
    )