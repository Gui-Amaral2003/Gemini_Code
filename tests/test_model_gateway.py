from types import SimpleNamespace

import httpx
import pytest

from gemini.exceptions import GeminiTimeoutError, ModelFallbackExhausted
from gemini.model_gateway import ModelCallResult, ModelGateway, ModelRequest


class FakeInteractions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeModels:
    def __init__(self):
        self.calls = []

    def count_tokens(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(total_tokens=42)


class FakeApi:
    def __init__(self, responses):
        self.interactions = FakeInteractions(responses)
        self.models = FakeModels()


class FakeQuota:
    def __init__(self, exhausted=()):
        self.exhausted = set(exhausted)
        self.registered = []

    def is_exhausted(self, model):
        return model in self.exhausted

    def register_call(self, model):
        self.registered.append(model)

    def used_today(self, _model):
        return 20

    def limit(self, _model):
        return 20


def make_gateway(
    responses,
    *,
    exhausted=(),
    confirm=lambda _message: False,
    max_rate_limit_retries=2,
):
    api = FakeApi(responses)
    quota = FakeQuota(exhausted)
    events = []
    traces = []
    sleeps = []

    def emit(event_type, message, **details):
        events.append((event_type, message, details))

    gateway = ModelGateway(
        api_client=api,
        default_model="default",
        fallback_models=["fallback-1", "fallback-2"],
        quota_tracker=quota,
        emit_activity=emit,
        trace_attempt=lambda **entry: traces.append(entry),
        confirm_quota_override=confirm,
        request_timeout=15,
        max_rate_limit_retries=max_rate_limit_retries,
        sleep=sleeps.append,
        random_jitter=lambda _start, _end: 0.25,
    )
    return gateway, api, quota, events, traces, sleeps


def test_successful_call_returns_interaction_and_selected_model():
    interaction = SimpleNamespace(id="interaction-1")
    gateway, api, quota, events, _traces, _sleeps = make_gateway([interaction])

    result = gateway.create(ModelRequest(input="hello", preferred_model="preferred"))

    assert result == ModelCallResult(interaction, "preferred")
    assert api.interactions.calls[0] == {
        "model": "preferred",
        "input": "hello",
        "tools": None,
        "previous_interaction_id": None,
        "timeout": 15,
    }
    assert quota.registered == ["preferred"]
    assert [event[0] for event in events] == [
        "model_selected",
        "api_attempt_started",
        "api_attempt_completed",
    ]


def test_model_order_removes_duplicates():
    gateway, *_rest = make_gateway([])

    assert gateway._models_to_try("fallback-1") == [
        "fallback-1",
        "default",
        "fallback-2",
    ]


def test_non_rate_limit_error_is_propagated_without_fallback():
    gateway, api, quota, *_rest = make_gateway([ValueError("invalid request")])

    with pytest.raises(ValueError, match="invalid request"):
        gateway.create(ModelRequest(input="hello"))

    assert len(api.interactions.calls) == 1
    assert quota.registered == ["default"]


@pytest.mark.parametrize(
    "error",
    [
        Exception("429 generate_content_free_tier_requests"),
        Exception("429 Resource exhausted"),
    ],
)
def test_daily_or_unknown_429_falls_back_without_same_model_retry(error):
    interaction = SimpleNamespace(id="fallback")
    gateway, api, quota, events, *_rest = make_gateway([error, interaction])

    result = gateway.create(ModelRequest(input="hello"))

    assert result.model == "fallback-1"
    assert [call["model"] for call in api.interactions.calls] == ["default", "fallback-1"]
    assert quota.registered == ["default", "fallback-1"]
    assert "fallback_selected" in [event[0] for event in events]


def test_transient_429_retries_same_model_with_retry_info():
    error = Exception("429 rate_limit_exceeded requestsPerMinute")
    error.details = {
        "error": {
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "2.5s",
                }
            ],
        }
    }
    interaction = SimpleNamespace(id="success")
    gateway, api, quota, _events, _traces, sleeps = make_gateway([error, interaction])

    result = gateway.create(ModelRequest(input="hello"))

    assert result.model == "default"
    assert [call["model"] for call in api.interactions.calls] == ["default", "default"]
    assert quota.registered == ["default", "default"]
    assert sleeps == [2.5]


def test_transient_429_uses_exponential_backoff_when_retry_info_is_absent():
    errors = [Exception("429 rate_limit_exceeded") for _ in range(2)]
    interaction = SimpleNamespace(id="success")
    gateway, _api, _quota, _events, _traces, sleeps = make_gateway(
        [*errors, interaction]
    )

    gateway.create(ModelRequest(input="hello"))

    assert sleeps == [1.25, 2.25]


def test_timeout_is_normalized_and_not_retried():
    gateway, api, quota, *_rest = make_gateway([httpx.ReadTimeout("slow")])

    with pytest.raises(GeminiTimeoutError, match="15s"):
        gateway.create(ModelRequest(input="hello"))

    assert len(api.interactions.calls) == 1
    assert quota.registered == ["default"]


def test_exhausted_models_are_skipped():
    interaction = SimpleNamespace(id="fallback")
    gateway, api, quota, events, *_rest = make_gateway(
        [interaction], exhausted={"default"}
    )

    result = gateway.create(ModelRequest(input="hello"))

    assert result.model == "fallback-1"
    assert api.interactions.calls[0]["model"] == "fallback-1"
    assert quota.registered == ["fallback-1"]
    assert events[0][0] == "models_skipped"


def test_all_locally_exhausted_can_be_cancelled():
    gateway, api, quota, *_rest = make_gateway(
        [],
        exhausted={"default", "fallback-1", "fallback-2"},
    )

    with pytest.raises(RuntimeError, match="cancelada pelo usuário"):
        gateway.create(ModelRequest(input="hello"))

    assert api.interactions.calls == []
    assert quota.registered == []


def test_all_locally_exhausted_can_be_overridden():
    interaction = SimpleNamespace(id="forced")
    gateway, api, quota, *_rest = make_gateway(
        [interaction],
        exhausted={"default", "fallback-1", "fallback-2"},
        confirm=lambda _message: True,
    )

    result = gateway.create(ModelRequest(input="hello"))

    assert result.model == "default"
    assert api.interactions.calls[0]["model"] == "default"
    assert quota.registered == ["default"]


def test_trace_records_each_model_attempt():
    interaction = SimpleNamespace(id="fallback")
    gateway, _api, _quota, _events, traces, _sleeps = make_gateway(
        [Exception("429 Resource exhausted"), interaction]
    )

    gateway.create(ModelRequest(input="hello", call_id="call-1", stage="initial"))

    assert [(entry["model"], entry["phase"]) for entry in traces] == [
        ("default", "start"),
        ("default", "failure"),
        ("fallback-1", "start"),
        ("fallback-1", "success"),
    ]


def test_all_rate_limited_models_raise_structured_error():
    errors = [Exception("429 Resource exhausted") for _ in range(3)]
    gateway, *_rest = make_gateway(errors)

    with pytest.raises(ModelFallbackExhausted) as captured:
        gateway.create(ModelRequest(input="hello"))

    assert captured.value.attempted_models == ["default", "fallback-1", "fallback-2"]
    assert captured.value.last_error is errors[-1]


def test_count_tokens_uses_requested_or_default_model():
    gateway, api, *_rest = make_gateway([])

    assert gateway.count_tokens("hello") == 42
    assert gateway.count_tokens("hello", "custom") == 42
    assert api.models.calls == [
        {"model": "default", "contents": "hello"},
        {"model": "custom", "contents": "hello"},
    ]
