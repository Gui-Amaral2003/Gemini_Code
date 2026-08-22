##TODO: Implementar multiplos parametros no groupby, no momento apenas um parametro é aceito
##TODO: plot_* hoje só suporta chart_type em {"bar", "line"} — scatter/pie ficam para depois

import pandas as pd
from .validation import (
    validate_conditions,
    QueryValidationError,
)
from .database import fetch_table_dataframe
from .filesystem import resolve_file_path
from .plotting import render_and_save, VALID_CHART_TYPES

_VALID_OPERATIONS = {'sum', 'mean', 'count', 'min', 'max', 'nunique', 'median', 'std'}
SPREADSHEET_EXTENSIONS = {".xlsx", ".xls", ".csv"}

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

def _compute_aggregation(
    df: pd.DataFrame,
    operation: str,
    target_column: str | None = None,
    group_by: str | None = None,
    top_n: int | None = None,
    sort_ascending: bool = False,
):
    """
    Núcleo PURO de agregação — sem formatação, sem I/O, sem filtro (o filtro já
    deve ter sido aplicado pelo chamador via _apply_conditions, se aplicável).
 
    Assume que operation/target_column/group_by já foram validados pelo chamador
    (existência de coluna, operação válida, etc.) — esta função não repete essas
    checagens, só calcula.
 
    Retorna (resultado, error):
      - group_by is None  -> resultado é um valor escalar
      - group_by is not None -> resultado é uma pandas Series (index=grupo, values=agregado),
        já ordenada e já cortada em top_n se informado
      - error é None em caso de sucesso, ou uma string de erro pronta para o modelo/usuário
    """
    if df.empty:
        return None, 'Nenhum dado encontrado após aplicar o filtro'
 
    # Agregação sem groupby
    if group_by is None:
        if operation == 'count' and target_column is None:
            resultado = len(df)
        else:
            resultado = getattr(df[target_column], operation)()
        return resultado, None
 
    # Agregação com groupby
    if operation == "count" and target_column is None:
        agrupado = df.groupby(group_by).size()
    else:
        agrupado = df.groupby(group_by)[target_column].agg(operation)
 
    agrupado = agrupado.sort_values(ascending=sort_ascending)
 
    if top_n is not None:
        agrupado = agrupado.head(top_n)
 
    return agrupado, None

def _validate_analysis_inputs(df: pd.DataFrame, operation: str, target_column: str | None, group_by: str | None) -> str | None:
    """Validações compartilhadas por analyze_*/plot_*. Retorna mensagem de erro ou None."""
    if operation not in _VALID_OPERATIONS:
        return (
            f"Operação inválida: {operation}"
            f"Disponíveis: {sorted(_VALID_OPERATIONS)}"
        )
 
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
 
    return None

def _analyze_data(df: pd.DataFrame, operation: str, target_column: str | None = None, group_by: str | None = None, conditions: list[dict] | None = None, top_n: int | None = None, sort_ascending: bool = False) -> str:
    """
    Executa uma agregação (com groupby opcional) sobre um DataFrame já carregado
    e formata o resultado em texto/markdown para o modelo.
 
    operation: sum, mean, count, min, max, nunique, median, std
    target_column: coluna a agregar (opcional se operation="count" e group_by=None)
    group_by: uma única coluna de agrupamento (TODO: suportar múltiplas colunas/métricas)
    conditions: filtro a ser aplicado em pandas sobre o df recebido. Use None quando
        o filtro já tiver sido aplicado antes (ex: tabelas do banco, filtradas no SQL
        por fetch_table_dataframe) para evitar filtrar duas vezes.
    top_n: limita quantas linhas do groupby são retornadas
    sort_ascending: ordena o resultado do groupby pelo valor agregado
    """
    column_types = _infer_column_types(df)
 
    error = _validate_analysis_inputs(df, operation, target_column, group_by)
    if error:
        return error
 
    # Filtro
    try:
        if conditions:
            df = _apply_conditions(df, conditions, column_types)
    except QueryValidationError as e:
        return f"Filtro inválido: {e}"
 
    resultado, error = _compute_aggregation(
        df,
        operation,
        target_column=target_column,
        group_by=group_by,
        top_n=top_n,
        sort_ascending=sort_ascending,
    )
    if error:
        return error
 
    # Sem groupby -> resultado escalar
    if group_by is None:
        return f"Resultado ({operation}{f' de {target_column}' if target_column else ''}): {resultado}"
 
    # Com groupby -> resultado é uma Series
    total_grupos = len(df.groupby(group_by))  # total antes do corte por top_n aplicado em _compute_aggregation
    agrupado = resultado
 
    resultado_df = agrupado.reset_index()
    resultado_df.columns = [group_by, f"{operation}_{target_column or 'count'}"]
 
    tabela_md = resultado_df.to_markdown(index=False)
 
    aviso = ""
    if top_n is not None and total_grupos > top_n:
        aviso = f"\n\n_Mostrando top {top_n} de {total_grupos} grupos. Refine o filtro para ver mais._"
 
    return f"{tabela_md}{aviso}"


# --------------------------------------------------------------------------- #
# Camada 1: obtenção do DataFrame (compartilhada entre analyze_* e plot_*)
# --------------------------------------------------------------------------- #
 
def _load_sheet_dataframe(file_path: str, sheet_name: str | None) -> tuple[pd.DataFrame | None, str | None]:
    """Resolve o caminho e carrega uma planilha/CSV como DataFrame. Retorna (df, error)."""
    resolved_path, error = resolve_file_path(file_path, allowed_extensions=SPREADSHEET_EXTENSIONS)
    if error:
        return None, error
 
    try:
        if resolved_path.suffix.lower() == ".csv":
            df = pd.read_csv(resolved_path)
        else:
            df = pd.read_excel(resolved_path, sheet_name=sheet_name or 0)
        return df, None
    except FileNotFoundError:
        return None, f"Arquivo não encontrado: {resolved_path}"
    except ValueError as e:
        # ex: sheet_name inválido — o próprio pandas/openpyxl lista as abas disponíveis
        return None, f"Erro ao abrir a planilha: {e}"
    except Exception as e:
        return None, f"Erro ao ler o arquivo: {e}"
 
 
# --------------------------------------------------------------------------- #
# Tools expostas ao Gemini — análise (retornam texto)
# --------------------------------------------------------------------------- #
 
def analyze_sheet_data(file_path: str, sheet_name: str | None = None, operation: str = "sum", target_column: str | None = None, group_by: str | None = None, conditions: list[dict] | None = None, top_n: int | None = None, sort_ascending: bool = False) -> str:
    """
    Carrega uma planilha (.xlsx/.csv) e executa uma análise agregada sobre ela.
    Aceita o nome do arquivo (busca automática) ou o caminho completo.
    """
    df, error = _load_sheet_dataframe(file_path, sheet_name)
    if error:
        return error
 
    return _analyze_data(
        df,
        operation=operation,
        target_column=target_column,
        group_by=group_by,
        conditions=conditions,
        top_n=top_n,
        sort_ascending=sort_ascending,
    )
 
 
def analyze_table_data(table: str, operation: str = "sum", target_column: str | None = None, group_by: str | None = None, conditions: list[dict] | None = None, top_n: int | None = None, sort_ascending: bool = False) -> str:
    """
    Carrega uma tabela pré-cadastrada em TABELAS_PERMITIDAS já filtrada no SQL
    (via fetch_table_dataframe, que aplica conditions no WHERE antes do corte
    por MAX_ROWS) e executa uma análise agregada sobre ela. O filtro NÃO é
    reaplicado em pandas — já veio aplicado no banco.
    """
    df, error = fetch_table_dataframe(table, conditions)
    if error:
        return error
 
    return _analyze_data(
        df,
        operation=operation,
        target_column=target_column,
        group_by=group_by,
        conditions=None,
        top_n=top_n,
        sort_ascending=sort_ascending,
    )
 
 
# --------------------------------------------------------------------------- #
# Tools expostas ao Gemini — plotagem (retornam dict com file_path em sucesso)
# --------------------------------------------------------------------------- #
 
def _plot_from_dataframe(df: pd.DataFrame, operation: str, target_column: str | None, group_by: str, conditions: list[dict] | None, top_n: int | None, sort_ascending: bool, chart_type: str):
    """Núcleo compartilhado por plot_sheet_data/plot_table_data a partir de um DataFrame já carregado."""
    if chart_type not in VALID_CHART_TYPES:
        return f"Tipo de gráfico inválido: {chart_type}. Disponíveis: {sorted(VALID_CHART_TYPES)}"
 
    if not group_by:
        return (
            "group_by é obrigatório para gerar um gráfico — sem uma coluna de "
            "agrupamento não há categorias para plotar. Para um valor único, "
            "use analyze_sheet_data/analyze_table_data em vez desta ferramenta."
        )
 
    column_types = _infer_column_types(df)
 
    error = _validate_analysis_inputs(df, operation, target_column, group_by)
    if error:
        return error
 
    try:
        if conditions:
            df = _apply_conditions(df, conditions, column_types)
    except QueryValidationError as e:
        return f"Filtro inválido: {e}"
 
    agrupado, error = _compute_aggregation(
        df,
        operation,
        target_column=target_column,
        group_by=group_by,
        top_n=top_n,
        sort_ascending=sort_ascending,
    )
    if error:
        return error
 
    title = f"{operation}_{target_column or 'contagem'} por {group_by}"
    ylabel = f"{operation}({target_column or 'linhas'})"
 
    try:
        filepath = render_and_save(
            agrupado,
            chart_type=chart_type,
            title=title,
            xlabel=group_by,
            ylabel=ylabel,
        )
    except Exception as e:
        return f"Erro ao gerar o gráfico: {e}"
 
    return {
        "status": "ok",
        "message": f"Gráfico ({chart_type}) exibido no terminal. PNG salvo temporariamente em: {filepath}",
        "file_path": str(filepath),
    }
 
 
def plot_sheet_data(file_path: str, sheet_name: str | None = None, operation: str = "sum", target_column: str | None = None, group_by: str | None = None, conditions: list[dict] | None = None, top_n: int | None = None, sort_ascending: bool = False, chart_type: str = "bar"):
    """
    Gera um gráfico a partir de uma agregação sobre uma planilha (.xlsx/.csv):
    exibe direto no terminal (plotext) e salva um PNG temporário em disco.
    Requer group_by. Aceita o nome do arquivo (busca automática) ou caminho completo.
    """
    df, error = _load_sheet_dataframe(file_path, sheet_name)
    if error:
        return error
 
    return _plot_from_dataframe(
        df,
        operation=operation,
        target_column=target_column,
        group_by=group_by,
        conditions=conditions,
        top_n=top_n,
        sort_ascending=sort_ascending,
        chart_type=chart_type,
    )
 
 
def plot_table_data(table: str, operation: str = "sum", target_column: str | None = None, group_by: str | None = None, conditions: list[dict] | None = None, top_n: int | None = None, sort_ascending: bool = False, chart_type: str = "bar"):
    """
    Gera um gráfico a partir de uma agregação sobre uma tabela pré-cadastrada do
    banco: o filtro (conditions) é aplicado no SQL via fetch_table_dataframe,
    antes do corte por MAX_ROWS. Exibe direto no terminal (plotext) e salva um
    PNG temporário em disco. Requer group_by.
    """
    df, error = fetch_table_dataframe(table, conditions)
    if error:
        return error
 
    return _plot_from_dataframe(
        df,
        operation=operation,
        target_column=target_column,
        group_by=group_by,
        conditions=None,
        top_n=top_n,
        sort_ascending=sort_ascending,
        chart_type=chart_type,
    )
