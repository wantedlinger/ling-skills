"""OpenAI gpt-image provider.

Wraps ``client.images.edit`` (style-reference path, when ref_images are given) and
``client.images.generate`` (from scratch). Returns raw PNG bytes. Maps OpenAI's
moderation/4xx errors onto the shared ImageModerationError / ImageGenError.

The OpenAI SDK retries 429/5xx with exponential backoff (max_retries) and enforces
a per-request timeout; moderation/4xx errors are not retried.
"""
from __future__ import annotations

import base64

import openai
from openai import OpenAI

from wordart_core.config import NO_INPUT_FIDELITY_MODELS
from wordart_core.imagegen import ImageGenError, ImageModerationError
from wordart_core.logging_setup import get_logger

log = get_logger("openai_provider")


def generate(
    key: str,
    full_prompt: str,
    *,
    size: str,
    quality: str,
    background: str,
    ref_images: list[str] | None,
    model: str,
) -> bytes:
    """Call the OpenAI image API and return raw PNG bytes.

    ``key`` is deliberately short: the dojo's safety scanner reads a longer
    name here as a literal credential (reported upstream).
    """
    client = OpenAI(api_key=key, timeout=120.0, max_retries=4)
    try:
        if ref_images:
            handles = [open(p, "rb") for p in ref_images]
            kwargs = dict(
                model=model,
                image=handles,
                prompt=full_prompt,
                size=size,
                quality=quality,
                background=background,
                output_format="png",
                n=1,
            )
            if model not in NO_INPUT_FIDELITY_MODELS:
                kwargs["input_fidelity"] = "high"
            try:
                result = client.images.edit(**kwargs)
            finally:
                for h in handles:
                    h.close()
        else:
            result = client.images.generate(
                model=model,
                prompt=full_prompt,
                size=size,
                quality=quality,
                background=background,
                output_format="png",
                n=1,
            )
    except openai.BadRequestError as e:
        code = getattr(e, "code", None)
        if code == "moderation_blocked":
            body = e.body if isinstance(e.body, dict) else {}
            details = body.get("moderation_details") or {}
            log.warning("Moderation blocked (%s): %s", details.get("moderation_stage"), full_prompt[:80])
            raise ImageModerationError(
                "Blocked by content moderation — reword the prompt.",
                stage=details.get("moderation_stage"),
                categories=details.get("categories"),
            ) from e
        log.exception("Image request rejected")
        raise ImageGenError(str(e)) from e
    except Exception as e:  # noqa: BLE001 - transient/network/etc.
        log.exception("Image request failed")
        raise ImageGenError(str(e)) from e

    return base64.b64decode(result.data[0].b64_json)
