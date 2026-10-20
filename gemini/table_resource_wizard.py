"""Editor de allowlists de tabelas, sem abrir conexões com bancos.

TODO: descoberta de colunas e teste de conexão mediante ação explícita.
TODO: gerenciamento de novas permissões de escrita pelo assistente.
"""

from copy import deepcopy

from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from tools.catalogs import CatalogError, validate_catalog, validate_sql_identifier
from tools.db_connections import DB_CONNECTIONS


def _column_names(config):
    return list(dict.fromkeys([
        *config.get("return_columns", []),
        *config.get("filter_columns", {}),
        *config.get("editable_columns", {}),
        *config.get("column_types", {}),
    ]))


def _column_type(config, name):
    return (
        config.get("column_types", {}).get(name)
        or config.get("filter_columns", {}).get(name)
        or config.get("editable_columns", {}).get(name)
    )


def _show_table(console, name, config):
    console.print(f"Tabela: {config['schema']}.{name} · Conexão: {config['connection']}", markup=False)
    summary = Table("Coluna", "Tipo", "Retornar", "Filtrar", "Editar")
    for column in _column_names(config):
        summary.add_row(
            Text(column),
            _column_type(config, column) or "não informado",
            "Sim" if column in config.get("return_columns", []) else "Não",
            "Sim" if column in config.get("filter_columns", {}) else "Não",
            "Sim" if column in config.get("editable_columns", {}) else "Não",
        )
    console.print(summary)
    console.print(
        "Escrita: permissões existentes preservadas; este editor não libera novas colunas."
        if config.get("editable_columns") else "Escrita: desabilitada."
    )


def _ask_identifier(console, label, default=None):
    while True:
        options = {"console": console}
        if default is not None:
            options["default"] = default
        value = Prompt.ask(label, **options).strip()
        try:
            validate_sql_identifier(value, label)
            return value
        except CatalogError as error:
            console.print(str(error), style="red", markup=False)


def _edit_identity(console, config):
    connection = Prompt.ask(
        "Conexão (credenciais em /config edit)",
        choices=list(DB_CONNECTIONS),
        default=config.get("connection", "sqlserver_main"),
        console=console,
    )
    schema = _ask_identifier(console, "Schema", config.get("schema", "dbo"))
    config.update(connection=connection, schema=schema)


def _change_column(console, config, action):
    name = _ask_identifier(console, "Nome da coluna")
    exists = name in _column_names(config)
    if action == "adicionar" and exists:
        raise CatalogError("Coluna já cadastrada. Use editar.")
    if action != "adicionar" and not exists:
        raise CatalogError("Coluna não cadastrada.")
    if name in config.get("editable_columns", {}):
        if not Confirm.ask(
            f"A coluna {name} tem permissão de escrita. Confirmar {action} esta coluna?",
            default=False, console=console,
        ):
            return
    if action == "remover":
        config["return_columns"] = [c for c in config.get("return_columns", []) if c != name]
        for field in ("filter_columns", "editable_columns", "column_types"):
            config.get(field, {}).pop(name, None)
        return
    kind = Prompt.ask(
        "Tipo", choices=["str", "int", "float", "date"],
        default=_column_type(config, name) or "str", console=console,
    )
    returned = Confirm.ask(
        "Permitir retorno nos resultados?",
        default=(name in config.get("return_columns", [])) if exists else True,
        console=console,
    )
    filtered = Confirm.ask(
        "Permitir uso em filtros?",
        default=(name in config.get("filter_columns", {})) if exists else True,
        console=console,
    )
    if not returned and not filtered and name not in config.get("editable_columns", {}):
        raise CatalogError("Selecione pelo menos uma permissão ou use remover.")
    config.setdefault("column_types", {})[name] = kind
    returns = config.setdefault("return_columns", [])
    if returned and name not in returns:
        returns.append(name)
    elif not returned and name in returns:
        returns.remove(name)
    filters = config.setdefault("filter_columns", {})
    if filtered:
        filters[name] = kind
    else:
        filters.pop(name, None)
    if name in config.get("editable_columns", {}):
        config["editable_columns"][name] = kind


def _manage_columns(console, name, config):
    while True:
        _show_table(console, name, config)
        action = Prompt.ask(
            "Colunas", choices=["adicionar", "editar", "remover", "concluir"],
            default="concluir", console=console,
        )
        if action == "concluir":
            return
        try:
            _change_column(console, config, action)
        except CatalogError as error:
            console.print(str(error), style="red", markup=False)


def edit_tables(console, data):
    entries = data.get("database", {}).get("tables", {})
    listing = Table("Tabela", "Conexão", "Escrita")
    for name, config in entries.items():
        listing.add_row(
            Text(f"{config['schema']}.{name}"),
            Text(config["connection"]),
            "Habilitada" if config.get("editable_columns") else "Desabilitada",
        )
    console.print(listing)
    action = Prompt.ask(
        "Ação", choices=["adicionar", "editar", "remover", "voltar"],
        default="voltar", console=console,
    )
    if action == "voltar":
        return False
    name = _ask_identifier(console, "Nome real da tabela")
    if action == "adicionar" and name in entries:
        raise CatalogError("Tabela já cadastrada. Use editar.")
    if action != "adicionar" and name not in entries:
        raise CatalogError("Tabela não cadastrada.")
    if action == "remover":
        _show_table(console, name, entries[name])
        if Confirm.ask(f"Remover o cadastro de {name}? A tabela no banco não será alterada.",
                       default=False, console=console):
            del entries[name]
            return True
        return False
    original = entries.get(name, {})
    config = deepcopy(original)
    if action == "adicionar":
        _edit_identity(console, config)
        config["return_columns"] = []
        config["filter_columns"] = {}
        _manage_columns(console, name, config)
    while True:
        _show_table(console, name, config)
        step = Prompt.ask(
            "Tabela", choices=["dados", "colunas", "salvar", "cancelar"],
            default="salvar", console=console,
        )
        if step == "cancelar":
            return False
        if step == "dados":
            _edit_identity(console, config)
        elif step == "colunas":
            _manage_columns(console, name, config)
        else:
            try:
                validate_catalog({"database": {"tables": {name: config}}})
            except CatalogError as error:
                console.print(str(error), style="red", markup=False)
                continue
            if original.get("editable_columns") and any(
                original.get(key) != config.get(key) for key in ("connection", "schema")
            ):
                if not Confirm.ask(
                    "Esta alteração muda o destino de uma tabela com escrita habilitada. Confirmar?",
                    default=False, console=console,
                ):
                    return False
            console.print("Validação local; existência da tabela e conexão não foram testadas.")
            if not Confirm.ask("Salvar esta tabela?", default=False, console=console):
                return False
            data.setdefault("database", {}).setdefault("tables", {})[name] = config
            return True

