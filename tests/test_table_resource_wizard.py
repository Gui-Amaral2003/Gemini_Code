from copy import deepcopy
from io import StringIO

import pytest
from rich.console import Console

from gemini import resource_wizard
from gemini import table_resource_wizard as wizard
from tools.catalogs import CatalogError, load_catalog, save_catalog, validate_catalog


def console():
    return Console(file=StringIO(), force_terminal=False, width=120)


def responses(monkeypatch, prompts, confirms=()):
    answers = iter(prompts)
    confirmations = iter(confirms)
    monkeypatch.setattr(wizard.Prompt, "ask", lambda *a, **kw: next(answers))
    monkeypatch.setattr(wizard.Confirm, "ask", lambda *a, **kw: next(confirmations))


def sample_table():
    return {
        "connection": "sqlserver_main",
        "schema": "sales",
        "return_columns": ["id", "status"],
        "filter_columns": {"id": "int", "status": "str"},
    }


def test_add_table_through_resources_persists_types_permissions_and_other_groups(monkeypatch, tmp_path):
    path = tmp_path / "catalogs.toml"
    save_catalog({"airflow": {"dags": {"daily": {"description": "Daily job"}}}}, path)
    responses(monkeypatch, [
        "3", "adicionar", "deals", "sqlserver_main", "sales",
        "adicionar", "id", "int",
        "adicionar", "value", "float",
        "concluir", "salvar", "0",
    ], [True, True, True, False, True])

    resource_wizard.run_resources(console(), path)

    data = load_catalog(path)
    table = data["database"]["tables"]["deals"]
    assert table["return_columns"] == ["id", "value"]
    assert table["filter_columns"] == {"id": "int"}
    assert table["column_types"] == {"id": "int", "value": "float"}
    assert not table.get("editable_columns")
    assert data["airflow"]["dags"]["daily"]["description"] == "Daily job"


def test_cancel_table_edit_preserves_file(monkeypatch, tmp_path):
    path = tmp_path / "catalogs.toml"
    save_catalog({"database": {"tables": {"deals": sample_table()}}}, path)
    before = path.read_bytes()
    responses(monkeypatch, [
        "3", "editar", "deals", "dados", "sqlserver_main", "other",
        "cancelar", "0",
    ])

    resource_wizard.run_resources(console(), path)

    assert path.read_bytes() == before


def test_edit_identity_preserves_existing_write_permissions(monkeypatch):
    table = sample_table()
    table["editable_columns"] = {"status": "str"}
    data = {"database": {"tables": {"deals": deepcopy(table)}}}
    responses(monkeypatch, [
        "editar", "deals", "dados", "sqlserver_main", "archive", "salvar",
    ], [True, True])

    assert wizard.edit_tables(console(), data)
    saved = data["database"]["tables"]["deals"]
    assert saved["schema"] == "archive"
    assert saved["editable_columns"] == table["editable_columns"]
    assert saved["filter_columns"] == table["filter_columns"]


def test_changing_write_destination_requires_specific_confirmation(monkeypatch):
    table = sample_table()
    table["editable_columns"] = {"status": "str"}
    data = {"database": {"tables": {"deals": table}}}
    original = deepcopy(data)
    responses(monkeypatch, [
        "editar", "deals", "dados", "sqlserver_main", "archive", "salvar",
    ], [False])

    assert not wizard.edit_tables(console(), data)
    assert data == original


def test_remove_column_clears_associated_permissions_and_type(monkeypatch):
    table = sample_table()
    table["editable_columns"] = {"status": "str"}
    table["column_types"] = {"id": "int", "status": "str"}
    responses(monkeypatch, ["status"], [True])

    wizard._change_column(console(), table, "remover")

    assert table["return_columns"] == ["id"]
    assert "status" not in table["filter_columns"]
    assert "status" not in table["editable_columns"]
    assert "status" not in table["column_types"]


def test_declining_write_column_confirmation_preserves_column(monkeypatch):
    table = sample_table()
    table["editable_columns"] = {"status": "str"}
    original = deepcopy(table)
    responses(monkeypatch, ["status"], [False])

    wizard._change_column(console(), table, "remover")

    assert table == original


def test_editing_existing_write_column_updates_type_only_after_confirmation(monkeypatch):
    table = sample_table()
    table["editable_columns"] = {"status": "str"}
    responses(monkeypatch, ["status", "int"], [True, True, True])

    wizard._change_column(console(), table, "editar")

    assert table["editable_columns"] == {"status": "int"}
    assert table["filter_columns"]["status"] == "int"
    assert table["column_types"]["status"] == "int"


def test_duplicate_column_rejected_without_modifying_config(monkeypatch):
    table = sample_table()
    original = deepcopy(table)
    responses(monkeypatch, ["id"])

    with pytest.raises(CatalogError, match="já cadastrada"):
        wizard._change_column(console(), table, "adicionar")
    assert table == original


def test_table_without_return_columns_cannot_be_saved(monkeypatch):
    data = {}
    responses(monkeypatch, [
        "adicionar", "deals", "sqlserver_main", "sales",
        "concluir", "salvar", "cancelar",
    ])
    output = console()

    assert not wizard.edit_tables(output, data)
    assert not data
    assert "lista não vazia" in output.file.getvalue()


def test_remove_table_requires_confirmation_and_only_removes_registration(monkeypatch):
    data = {"database": {"tables": {"deals": sample_table(), "other": sample_table()}}}
    responses(monkeypatch, ["remover", "deals"], [True])

    assert wizard.edit_tables(console(), data)
    assert set(data["database"]["tables"]) == {"other"}


def test_invalid_identifier_reprompted(monkeypatch):
    responses(monkeypatch, ["bad;name", "deals"])
    assert wizard._ask_identifier(console(), "Tabela") == "deals"


@pytest.mark.parametrize("change", ["duplicate", "invalid_type", "conflicting_type"])
def test_loader_rejects_invalid_column_metadata(change):
    table = sample_table()
    if change == "duplicate":
        table["return_columns"].append("id")
    elif change == "invalid_type":
        table["column_types"] = {"id": "boolean"}
    else:
        table["column_types"] = {"id": "str"}
    with pytest.raises(CatalogError):
        validate_catalog({"database": {"tables": {"deals": table}}})


def test_keyboard_interrupt_discards_unsaved_table(monkeypatch, tmp_path):
    path = tmp_path / "catalogs.toml"
    save_catalog({}, path)
    before = path.read_bytes()
    answers = iter(["3", "adicionar", "deals"])

    def ask(*args, **kwargs):
        try:
            return next(answers)
        except StopIteration:
            raise KeyboardInterrupt

    monkeypatch.setattr(wizard.Prompt, "ask", ask)
    resource_wizard.run_resources(console(), path)

    assert path.read_bytes() == before

