from dataclasses import replace

import pytest

import tools.registry as registry


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
