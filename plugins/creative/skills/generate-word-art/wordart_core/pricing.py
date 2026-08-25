"""Cost accounting for image + Gemini usage, with USD->THB conversion."""
from __future__ import annotations

import threading

from wordart_core.config import GEMINI_PRICING, IMAGE_MODEL, IMAGE_USD_COST


def usd_for(quality: str, size: str = "1024x1024", model: str = IMAGE_MODEL) -> float:
    by_model = IMAGE_USD_COST.get(model) or next(iter(IMAGE_USD_COST.values()))
    by_size = by_model.get(quality, by_model["low"])
    return by_size.get(size, next(iter(by_size.values())))


def usage_from(resp) -> tuple[int, int]:
    """Return (input_tokens, output_tokens) from a google-genai response.

    Output includes thinking tokens, which are billed as output.
    """
    um = getattr(resp, "usage_metadata", None)
    if um is None:
        return 0, 0
    in_tok = getattr(um, "prompt_token_count", 0) or 0
    cand = getattr(um, "candidates_token_count", 0) or 0
    thoughts = getattr(um, "thoughts_token_count", 0) or 0
    total = getattr(um, "total_token_count", 0) or 0
    out_tok = cand + thoughts
    if total and (total - in_tok) > out_tok:
        out_tok = total - in_tok
    return in_tok, out_tok


def gemini_usd(model: str, in_tok: int, out_tok: int) -> float:
    price = GEMINI_PRICING.get(model)
    if not price:
        return 0.0
    return in_tok / 1_000_000 * price["input"] + out_tok / 1_000_000 * price["output"]


class CostTracker:
    """Thread-safe running total of all spend for the current session."""

    def __init__(self, usd_to_thb: float):
        self._usd = 0.0
        self._rate = usd_to_thb
        self._lock = threading.Lock()

    def add_image(self, quality: str, size: str = "1024x1024", model: str = IMAGE_MODEL) -> None:
        self.add_usd(usd_for(quality, size, model))

    def add_usd(self, amount: float) -> None:
        with self._lock:
            self._usd += max(0.0, amount)

    def set_rate(self, usd_to_thb: float) -> None:
        with self._lock:
            self._rate = usd_to_thb

    @property
    def usd(self) -> float:
        with self._lock:
            return self._usd

    @property
    def thb(self) -> float:
        with self._lock:
            return self._usd * self._rate
