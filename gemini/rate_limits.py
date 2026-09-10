"""Classificacao de erros 429 retornados pela API do Gemini."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class RateLimitKind(Enum):
    NOT_RATE_LIMIT = "not_rate_limit"
    DAILY_QUOTA = "daily_quota"
    TRANSIENT = "transient"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RateLimitInfo:
    kind: RateLimitKind
    retry_after_seconds: Optional[float] = None
    reason: str = ""


_DAILY_MARKERS = (
    "quota_exceeded",
    "requestsperday",
    "perdayperproject",
    "generate_content_free_tier_requests",
)
_TRANSIENT_MARKERS = (
    "rate_limit_exceeded",
    "too_many_requests",
    "requestsperminute",
    "tokensperminute",
    "requestspersecond",
    "tokenspersecond",
)
_RETRY_DELAY_PATTERN = re.compile(r"(?P<seconds>\d+(?:\.\d+)?)s\b", re.IGNORECASE)


def _response_body(error: Exception) -> dict[str, Any]:
    details = getattr(error, "details", None)
    if not isinstance(details, dict):
        return {}
    nested = details.get("error")
    return nested if isinstance(nested, dict) else details


def _iter_detail_dicts(body: dict[str, Any]):
    details = body.get("details", [])
    if isinstance(details, list):
        yield from (detail for detail in details if isinstance(detail, dict))


def _retry_after_seconds(error: Exception, body: dict[str, Any]) -> Optional[float]:
    for detail in _iter_detail_dicts(body):
        if str(detail.get("@type", "")).endswith("google.rpc.RetryInfo"):
            match = _RETRY_DELAY_PATTERN.search(str(detail.get("retryDelay", "")))
            if match:
                return float(match.group("seconds"))

    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        value = headers.get("retry-after")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            pass
    return None


def classify_rate_limit(error: Exception) -> RateLimitInfo:
    """Classifica um 429 usando dados estruturados e formatos legados."""
    text = str(error).casefold()
    body = _response_body(error)
    is_rate_limit = (
        getattr(error, "code", None) == 429
        or bool(re.search(r"\b429\b", text))
        or str(body.get("status", "")).casefold() == "resource_exhausted"
    )
    if not is_rate_limit:
        return RateLimitInfo(RateLimitKind.NOT_RATE_LIMIT)

    searchable_parts = [text]
    for key in ("reason", "error_code", "code", "message"):
        value = body.get(key)
        if isinstance(value, str):
            searchable_parts.append(value.casefold())

    for detail in _iter_detail_dicts(body):
        searchable_parts.extend(
            str(value).casefold()
            for value in detail.values()
            if isinstance(value, (str, int, float))
        )
        violations = detail.get("violations", [])
        if isinstance(violations, list):
            for violation in violations:
                if isinstance(violation, dict):
                    searchable_parts.extend(
                        str(value).casefold() for value in violation.values()
                    )

    searchable = " ".join(searchable_parts)
    retry_after = _retry_after_seconds(error, body)
    if any(marker in searchable for marker in _DAILY_MARKERS):
        return RateLimitInfo(RateLimitKind.DAILY_QUOTA, retry_after, "daily quota")
    if any(marker in searchable for marker in _TRANSIENT_MARKERS):
        return RateLimitInfo(RateLimitKind.TRANSIENT, retry_after, "transient rate limit")
    return RateLimitInfo(RateLimitKind.UNKNOWN, retry_after, "unclassified 429")
