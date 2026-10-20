import pytest

import tools.optional_deps as optional_deps


def fake_finder(available=()):
    modules = set(available)
    return lambda name: object() if name in modules else None


def test_missing_dependencies_returns_distribution_names():
    missing = optional_deps.missing_dependencies(
        "charts",
        fake_finder({"matplotlib"}),
    )

    assert missing == ["plotext"]


def test_is_available_when_all_modules_exist():
    assert optional_deps.is_available(
        "pdf",
        fake_finder({"pypdf"}),
    )


def test_hive_detects_pure_sasl_by_its_importable_module_name():
    modules = {"sqlalchemy", "pyhive", "thrift", "thrift_sasl", "puresasl"}
    assert optional_deps.is_available("hive", fake_finder(modules))


def test_unknown_extra_has_clear_error():
    with pytest.raises(ValueError, match="Extra desconhecido"):
        optional_deps.is_available("unknown", fake_finder())


def test_require_reports_missing_extra_and_install_command(monkeypatch):
    def import_module(name):
        if name == "plotext":
            raise ModuleNotFoundError(name)
        return object()

    monkeypatch.setattr(optional_deps.importlib, "import_module", import_module)

    with pytest.raises(optional_deps.MissingDependencyError) as raised:
        optional_deps.require("charts")

    message = str(raised.value)
    assert "plotext" in message
    assert "gemini-code-terminal[charts]" in message
    assert "pipx install --force" in message


def test_require_succeeds_when_dependencies_import(monkeypatch):
    monkeypatch.setattr(optional_deps.importlib, "import_module", lambda _name: object())

    assert optional_deps.require("pdf") is None
