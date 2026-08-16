import random
import time

from google.genai import errors as genai_errors


RETRYABLE_ERRORS = (
    genai_errors.ServerError,
    ConnectionError,
    TimeoutError,
)


def calculate_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> float:

    delay = min(
        max_delay,
        base_delay * (2 ** attempt),
    )

    return delay + random.uniform(0, 0.5)