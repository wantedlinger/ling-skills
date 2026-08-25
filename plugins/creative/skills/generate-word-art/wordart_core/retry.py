"""Small retry-with-backoff helper for transient API failures (429/5xx).

Used to wrap Gemini calls. The OpenAI SDK has its own built-in retry/backoff,
so image generation relies on that instead.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

from wordart_core.logging_setup import get_logger

log = get_logger("retry")

T = TypeVar("T")

_TRANSIENT_CODES = {408, 409, 429, 500, 502, 503, 504}
_TRANSIENT_HINTS = (
    "resource_exhausted", "unavailable", "rate limit", "try again",
    "internal error", "deadline", "timeout", "temporarily",
)


def is_transient(e: Exception) -> bool:
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if isinstance(code, int) and code in _TRANSIENT_CODES:
        return True
    msg = str(e).lower()
    return any(h in msg for h in _TRANSIENT_HINTS)


def with_retries(fn: Callable[[], T], *, attempts: int = 4, base_delay: float = 1.0,
                 label: str = "call") -> T:
    """Call fn(); on transient errors retry with exponential backoff."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if i == attempts - 1 or not is_transient(e):
                raise
            delay = base_delay * (2 ** i)
            log.warning("%s failed (%s); retry %d/%d in %.1fs", label, e, i + 1, attempts - 1, delay)
            time.sleep(delay)
    assert last is not None
    raise last
