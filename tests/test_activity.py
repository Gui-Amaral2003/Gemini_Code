import json
import logging

from gemini.activity import ActivityRecorder
from gemini.models import ActivityEvent


def test_emit_accumulates_event_and_notifies_callback(tmp_path, monkeypatch):
    recorder = ActivityRecorder(tmp_path / "trace.jsonl")
    captured = []
    recorder.set_callback(captured.append)
    monkeypatch.setattr("gemini.activity.time.time", lambda: 123.5)

    event = recorder.emit(
        "tool_started",
        "Executando search_in_sheet",
        tool="search_in_sheet",
        details={"attempt": 1},
    )

    assert event == ActivityEvent(
        type="tool_started",
        message="Executando search_in_sheet",
        timestamp=123.5,
        tool="search_in_sheet",
        details={"attempt": 1},
    )
    assert recorder.last_activities == [event]
    assert captured == [event]


def test_callback_failure_does_not_interrupt_emit(tmp_path, caplog):
    recorder = ActivityRecorder(tmp_path / "trace.jsonl")
    recorder.set_callback(lambda _event: (_ for _ in ()).throw(RuntimeError("UI falhou")))

    with caplog.at_level(logging.ERROR, logger="gemini_client"):
        event = recorder.emit("request_started", "Preparando")

    assert recorder.last_activities == [event]
    assert "Erro no callback de atividade" in caplog.text


def test_set_callback_none_removes_consumer(tmp_path):
    recorder = ActivityRecorder(tmp_path / "trace.jsonl")
    captured = []
    recorder.set_callback(captured.append)
    recorder.set_callback(None)

    recorder.emit("request_started", "Preparando")

    assert captured == []


def test_reset_clears_activities_without_removing_callback(tmp_path):
    recorder = ActivityRecorder(tmp_path / "trace.jsonl")
    captured = []
    recorder.set_callback(captured.append)
    recorder.emit("first", "Primeiro")

    recorder.reset()
    recorder.emit("second", "Segundo")

    assert [event.type for event in recorder.last_activities] == ["second"]
    assert [event.type for event in captured] == ["first", "second"]


def test_trace_model_attempt_creates_parent_and_writes_valid_jsonl(tmp_path, monkeypatch):
    trace_path = tmp_path / "nested" / "trace.jsonl"
    recorder = ActivityRecorder(trace_path)
    monkeypatch.setattr(
        "gemini.activity.time.strftime",
        lambda _format: "2026-09-10 12:00:00",
    )

    recorder.trace_model_attempt(
        call_id="call-1",
        stage="initial",
        model="gemini-test",
        phase="start",
    )
    recorder.trace_model_attempt(
        call_id="call-1",
        stage="initial",
        model="gemini-test",
        phase="failure",
        error="429 test",
    )

    entries = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert entries == [
        {
            "timestamp": "2026-09-10 12:00:00",
            "call_id": "call-1",
            "stage": "initial",
            "model": "gemini-test",
            "phase": "start",
        },
        {
            "timestamp": "2026-09-10 12:00:00",
            "call_id": "call-1",
            "stage": "initial",
            "model": "gemini-test",
            "phase": "failure",
            "error": "429 test",
        },
    ]


def test_trace_write_failure_is_logged_and_not_raised(tmp_path, monkeypatch, caplog):
    recorder = ActivityRecorder(tmp_path / "trace.jsonl")

    def fail_open(*_args, **_kwargs):
        raise OSError("disco indisponível")

    monkeypatch.setattr("builtins.open", fail_open)

    with caplog.at_level(logging.WARNING, logger="gemini_client"):
        recorder.trace_model_attempt(
            call_id="call-1",
            stage="initial",
            model="gemini-test",
            phase="start",
        )

    assert "Não consegui gravar o log de rastreio" in caplog.text
