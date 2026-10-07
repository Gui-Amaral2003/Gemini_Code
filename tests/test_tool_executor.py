from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from gemini.tool_executor import ToolExecutionContext, ToolExecutor
from tools.registry import ToolPolicy


def make_step(name, arguments=None):
    return SimpleNamespace(name=name, arguments=arguments or {})


@pytest.fixture
def executor_factory():
    executors = []

    def create(policies, events=None, **kwargs):
        captured = events if events is not None else []

        def emit(event_type, message, **details):
            captured.append((event_type, message, details))

        executor = ToolExecutor(
            policies=policies,
            emit_activity=emit,
            default_timeout=kwargs.pop("default_timeout", 1),
            **kwargs,
        )
        executors.append(executor)
        return executor, captured

    yield create

    for executor in executors:
        executor.close()


def test_unknown_tool_returns_error_and_failure_event(executor_factory):
    executor, events = executor_factory({})

    result = executor.execute(make_step("missing"), ToolExecutionContext())

    assert "não está registrada" in result["error"]
    assert [event[0] for event in events] == ["tool_started", "tool_failed"]


def test_successful_tool_receives_arguments(executor_factory):
    policy = ToolPolicy("sum", lambda a, b: a + b)
    executor, events = executor_factory({"sum": policy})

    result = executor.execute(make_step("sum", {"a": 2, "b": 3}), ToolExecutionContext())

    assert result == 5
    assert [event[0] for event in events] == ["tool_started", "tool_completed"]


def test_tool_exception_becomes_error_result(executor_factory):
    def fail():
        raise ValueError("entrada inválida")

    executor, events = executor_factory({"fail": ToolPolicy("fail", fail)})

    result = executor.execute(make_step("fail"), ToolExecutionContext())

    assert result == {"error": "entrada inválida"}
    assert [event[0] for event in events] == ["tool_started", "tool_failed"]


def test_policy_timeout_override_returns_error(executor_factory):
    release_tool = Event()

    def slow_tool():
        release_tool.wait()
        return "concluída em background"

    policy = ToolPolicy("slow", slow_tool, timeout_seconds=0.01)
    executor, events = executor_factory({"slow": policy}, default_timeout=10)

    try:
        result = executor.execute(make_step("slow"), ToolExecutionContext())
    finally:
        release_tool.set()

    assert "excedeu o tempo limite" in result["error"]
    assert [event[0] for event in events] == ["tool_started", "tool_failed"]


def test_default_timeout_is_used_when_policy_has_no_override(executor_factory):
    release_tool = Event()

    def slow_tool():
        release_tool.wait()

    executor, _events = executor_factory(
        {"slow": ToolPolicy("slow", slow_tool)},
        default_timeout=0.01,
    )

    try:
        result = executor.execute(make_step("slow"), ToolExecutionContext())
    finally:
        release_tool.set()

    assert "(0.01s)" in result["error"]


def test_confirmation_policy_bypasses_pool(executor_factory):
    policy = ToolPolicy(
        "confirmed",
        lambda: "executada diretamente",
        requires_confirmation=True,
    )
    executor, events = executor_factory({"confirmed": policy})
    original_pool = executor._pool
    executor._pool = SimpleNamespace(
        submit=lambda *_args, **_kwargs: pytest.fail(
            "tool com confirmação não deve entrar no pool"
        ),
        shutdown=lambda **_kwargs: None,
    )

    try:
        result = executor.execute(make_step("confirmed"), ToolExecutionContext())
    finally:
        executor._pool = original_pool

    assert result == "executada diretamente"
    assert [event[0] for event in events] == ["tool_started", "tool_completed"]


def test_session_file_restriction_blocks_unregistered_path(executor_factory, tmp_path):
    executed = []
    policy = ToolPolicy(
        "run",
        lambda path: executed.append(path),
        requires_confirmation=True,
        requires_session_created_file="path",
    )
    executor, events = executor_factory({"run": policy})

    result = executor.execute(
        make_step("run", {"path": str(tmp_path / "script.py")}),
        ToolExecutionContext(),
    )

    assert "Execução bloqueada" in result["error"]
    assert executed == []
    assert [event[0] for event in events] == ["tool_started", "tool_failed"]


def test_registered_file_can_be_consumed_in_later_execution(executor_factory, tmp_path):
    created_path = tmp_path / "script.py"
    create_policy = ToolPolicy(
        "writer",
        lambda: {"success": True, "output_path": str(created_path)},
        requires_confirmation=True,
        registers_session_created_file="output_path",
    )
    run_policy = ToolPolicy(
        "runner",
        lambda path: f"executado: {path}",
        requires_confirmation=True,
        requires_session_created_file="path",
    )
    executor, _events = executor_factory({"writer": create_policy, "runner": run_policy})
    context = ToolExecutionContext()

    executor.execute(make_step("writer"), context)
    result = executor.execute(make_step("runner", {"path": str(created_path)}), context)

    assert context.created_files == {created_path.resolve()}
    assert result == f"executado: {created_path}"


def test_generated_files_are_recorded_without_clearing_created_files(
    executor_factory, tmp_path
):
    generated_path = tmp_path / "chart.png"
    policy = ToolPolicy(
        "plot",
        lambda: {"file_path": str(generated_path)},
        generate_file=True,
    )
    executor, _events = executor_factory({"plot": policy})
    existing = (tmp_path / "script.py").resolve()
    context = ToolExecutionContext(created_files={existing})

    executor.execute(make_step("plot"), context)

    assert context.created_files == {existing}
    assert context.generated_files == [generated_path]


def test_context_generated_files_can_be_reset_without_losing_session_files(tmp_path):
    created = (tmp_path / "script.py").resolve()
    context = ToolExecutionContext(
        created_files={created},
        generated_files=[Path("old-chart.png")],
    )

    context.generated_files = []

    assert context.created_files == {created}
    assert context.generated_files == []


def test_context_manager_closes_pool():
    executor = ToolExecutor(
        {"known": ToolPolicy("known", lambda: "ok")},
        lambda *_args, **_kwargs: None,
        default_timeout=1,
    )

    with executor as managed:
        assert managed is executor

    result = executor.execute(make_step("known"), ToolExecutionContext())

    assert "cannot schedule new futures" in result["error"]
