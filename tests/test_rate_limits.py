from google.genai.errors import APIError

from gemini.rate_limits import RateLimitKind, classify_rate_limit


def make_api_error(body):
    return APIError(429, {"error": body})


def test_classifies_daily_quota_from_quota_failure():
    error = make_api_error(
        {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [
                        {
                            "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                            "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                        }
                    ],
                }
            ],
        }
    )

    assert classify_rate_limit(error).kind is RateLimitKind.DAILY_QUOTA


def test_classifies_legacy_daily_quota_message():
    error = Exception(
        "429 Quota exceeded for metric "
        "generativelanguage.googleapis.com/generate_content_free_tier_requests"
    )

    assert classify_rate_limit(error).kind is RateLimitKind.DAILY_QUOTA


def test_classifies_transient_limit_and_extracts_retry_delay():
    error = make_api_error(
        {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": "GenerateRequestsPerMinutePerProject"}],
                },
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "2.5s",
                },
            ],
        }
    )

    result = classify_rate_limit(error)

    assert result.kind is RateLimitKind.TRANSIENT
    assert result.retry_after_seconds == 2.5


def test_unknown_429_is_not_assumed_transient():
    result = classify_rate_limit(Exception("429 Resource exhausted"))

    assert result.kind is RateLimitKind.UNKNOWN


def test_non_429_is_not_rate_limit():
    result = classify_rate_limit(ConnectionError("network down"))

    assert result.kind is RateLimitKind.NOT_RATE_LIMIT
