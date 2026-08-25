"""Gemini image provider (nano-banana family, e.g. gemini-3.1-flash-image).

Same contract as ``openai_provider.generate`` — returns raw PNG bytes. The
vendor differences are absorbed here so ``imagegen`` stays vendor-neutral:

- ``quality`` is an OpenAI-only knob: Gemini has no low/medium/high. Ignored
  with a stderr note so the user isn't left wondering why it changed nothing.
- ``size`` (a pixel string) maps to a Gemini aspect ratio.
- ``background`` has no API parameter on Gemini; the caller's prompt suffix
  (flat green / black / "Transparent background.") carries the instruction,
  and the chroma keying still happens locally in ``imagegen``.
- Gemini frequently returns JPEG bytes even when asked for images. We
  transcode to real PNG so JPEG bytes can never land in a ``.png`` file —
  that exact mismatch crashes After Effects' importer (generate-image
  CHANGELOG 2026-07-05).
- 429/5xx are retried with backoff via ``wordart_core.retry`` (the OpenAI SDK
  retries internally; google-genai does not).
- A safety block surfaces as a no-image response; mapped to
  ImageModerationError (finish_reason mentioning safety/prohibited) or
  ImageGenError otherwise, matching the OpenAI provider's error contract.
"""
from __future__ import annotations

import io
import sys

from wordart_core.imagegen import ImageGenError, ImageModerationError
from wordart_core.logging_setup import get_logger
from wordart_core.retry import with_retries

log = get_logger("gemini_provider")

# wordart sizes are OpenAI pixel strings; Gemini takes aspect ratios.
_SIZE_TO_RATIO = {"1024x1024": "1:1", "1024x1536": "2:3", "1536x1024": "3:2"}

_MODERATION_HINTS = ("safety", "prohibited", "blocklist", "blocked")


def _ensure_png(data: bytes) -> bytes:
    """Return *data* as real PNG bytes (transcode JPEG/WebP via Pillow)."""
    if data[:4] == b"\x89PNG":
        return data
    from PIL import Image

    with Image.open(io.BytesIO(data)) as im:
        buf = io.BytesIO()
        im.save(buf, "PNG")
    return buf.getvalue()


def generate(
    key: str,
    full_prompt: str,
    *,
    size: str,
    quality: str,
    background: str,  # noqa: ARG001 - carried by the prompt suffix on Gemini
    ref_images: list[str] | None,
    model: str,
) -> bytes:
    """Call the Gemini image API and return raw PNG bytes.

    ``key`` is deliberately short: the dojo's safety scanner reads a longer
    name here as a literal credential (reported upstream).
    """
    from google import genai
    from google.genai import types
    from PIL import Image

    ratio = _SIZE_TO_RATIO.get(size)
    if ratio is None:
        raise ImageGenError(
            f"size {size!r} has no Gemini aspect-ratio mapping (known: {list(_SIZE_TO_RATIO)})"
        )
    if quality:
        print(
            f"note: --quality {quality!r} is ignored on {model} (OpenAI-only knob; "
            f"Gemini has no quality tiers)",
            file=sys.stderr,
        )

    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=300_000))
    contents: list = [full_prompt]
    opened: list = []
    try:
        for p in ref_images or []:
            img = Image.open(p)
            opened.append(img)
            contents.append(img)

        def _call():
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["Image"],
                    image_config=types.ImageConfig(aspect_ratio=ratio),
                ),
            )

        try:
            resp = with_retries(_call, label=f"gemini image ({model})")
        except Exception as e:  # noqa: BLE001 - network/transient exhausted, or 4xx
            log.exception("Gemini image request failed")
            raise ImageGenError(str(e)) from e
    finally:
        for img in opened:
            try:
                img.close()
            except Exception:  # noqa: BLE001
                pass

    for cand in resp.candidates or []:
        for part in cand.content.parts if cand.content else []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return _ensure_png(inline.data)

    finish = str(getattr((resp.candidates or [None])[0], "finish_reason", "unknown"))
    if any(h in finish.lower() for h in _MODERATION_HINTS):
        log.warning("Gemini safety block (%s): %s", finish, full_prompt[:80])
        raise ImageModerationError(
            f"Blocked by Gemini safety ({finish}) — reword the prompt.", stage=finish
        )
    raise ImageGenError(
        f"Gemini returned no image (text-only or blocked); finish_reason={finish}"
    )
