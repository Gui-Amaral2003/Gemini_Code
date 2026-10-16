from dataclasses import replace

import pytest

import tools.registry as registry


def test_lazy_tool_imports_and_calls_target(monkeypatch):
    imported = []

    class Module:
        @staticmethod
        def execute(value):
            return value * 2

    monkeypatch.setattr(registry, "import_module", lambda name: imported.append(name) or Module)

    tool = registry.LazyTool("fake.module:execute")

    assert tool(3) == 6
    assert imported == ["fake.module"]


def test_optional_tool_policies_use_lazy_imports():
    assert isinstance(registry.TOOL_POLICIES["read_sheet"].function, registry.LazyTool)
    assert isinstance(registry.TOOL_POLICIES["read_pdf"].function, registry.LazyTool)
    assert isinstance(registry.TOOL_POLICIES["list_dags"].function, registry.LazyTool)


def test_registry_keys_match_policy_names(monkeypatch):
    policy = registry.TOOL_POLICIES["read_file"]
    monkeypatch.setitem(
        registry.TOOL_POLICIES,
        "read_file",
        replace(policy, name="nome_divergente"),
    )

    with pytest.raises(RuntimeError, match="nomes divergentes"):
        registry._assert_consistency()


def test_confirmation_policy_rejects_timeout(monkeypatch):
    policy = registry.TOOL_POLICIES["create_file"]
    monkeypatch.setitem(
        registry.TOOL_POLICIES,
        "create_file",
        replace(policy, timeout_seconds=10),
    )

    with pytest.raises(RuntimeError, match="tools de confirmação com timeout"):
        registry._assert_consistency()


def test_policy_timeout_must_be_positive(monkeypatch):
    policy = registry.TOOL_POLICIES["read_file"]
    monkeypatch.setitem(
        registry.TOOL_POLICIES,
        "read_file",
        replace(policy, timeout_seconds=0),
    )

    with pytest.raises(RuntimeError, match="timeouts inválidos"):
        registry._assert_consistency()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requires_session_created_file", ""),
        ("requires_session_created_file", 123),
        ("registers_session_created_file", "   "),
        ("registers_session_created_file", []),
    ],
)
def test_session_file_policy_fields_must_be_non_empty_strings(
    monkeypatch, field, value
):
    policy = registry.TOOL_POLICIES["read_file"]
    monkeypatch.setitem(
        registry.TOOL_POLICIES,
        "read_file",
        replace(policy, **{field: value}),
    )

    with pytest.raises(RuntimeError, match="campos de arquivo da sessão inválidos"):
        registry._assert_consistency()
