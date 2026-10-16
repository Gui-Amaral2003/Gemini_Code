"""Catálogos leves compartilhados pelos schemas e pelas implementações.

Este módulo não deve importar dependências opcionais. Assim, as definições
enviadas ao modelo podem ser montadas sem carregar pandas, drivers de banco,
clientes HTTP ou bibliotecas de PDF e gráficos.
"""

from pathlib import Path


TABLES_ALLOWED = {
    "TEST_DOA_DEALS": {
        "connection": "sqlserver_main",
        "schema": "rsk",
        "colunas_filtro": {
            "ID": "int",
            "WBC_TERM": "str",
            "CTG_SUBMITTER": "str",
            "Counterpart_CNPJ": "str",
            "Contract_Type": "str",
            "Supply_Start": "date",
            "Supply_End": "date",
            "Company": "str",
            "Deal_Date": "date",
        },
        "colunas_retorno": [
            "ID",
            "WBC_TERM",
            "CTG_SUBMITTER",
            "Counterpart_CNPJ",
            "Contract_Type",
            "Supply_Start",
            "Supply_End",
            "Company",
            "Deal_Date",
        ],
        "colunas_editaveis": {"WBC_TERM": "str", "Flag": "str", "Status": "str"},
    },
    # Exemplo Hive: mantenha sem "colunas_editaveis" para permanecer read-only.
    # "ALGUMA_TABELA_HIVE": {
    #     "connection": "hive_lake",
    #     "schema": "algum_schema",
    #     "colunas_filtro": {"id": "int", "nome": "str"},
    #     "colunas_retorno": ["id", "nome"],
    # },
}

CHART_TYPES = {"bar", "line"}

GIT_ALLOWED_REPOS: dict[str, dict] = {
    "gemini_code": {
        "path": Path(__file__).resolve().parent.parent,
        "writable": False,
    },
}

AIRFLOW_ALLOWED_DAGS: dict[str, dict] = {
    "ccee_dri_recorrente": {
        "description": "Atualização diária dos dados fechados da CCEE(DRI)."
    },
    "wbc_envio": {"description": "Atualiza a tabela WBC_CTO_FULL"},
}
