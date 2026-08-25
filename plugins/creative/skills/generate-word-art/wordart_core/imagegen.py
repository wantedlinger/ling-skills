"""Word-art image generation — vendor-neutral orchestrator.

`generate_image` builds the background-specific prompt suffix, dispatches to the
right provider (see ``providers/``) by model name, and — for chroma runs — keys
out the green background locally to preserve the white sticker outline.

The provider does the actual vendor API call and returns raw PNG bytes. Adding a
new vendor is one new file in ``providers/`` plus one line in its registry; this
module does not change.
"""
from __future__ import annotations

from wordart_core.config import CHROMA_PROMPT, IMAGE_MODEL, IMAGE_SIZE
from wordart_core import bgremove
from wordart_core.providers import get_provider
from wordart_core.logging_setup import get_logger

log = get_logger("imagegen")


class ImageModerationError(RuntimeError):
    """Raised when the prompt/word is blocked by moderation (do not auto-retry)."""

    def __init__(self, message: str, stage: str | None = None, categories=None):
        super().__init__(message)
        self.stage = stage
        self.categories = categories or []


class ImageGenError(RuntimeError):
    pass


def generate_image(
    api_key: str, prompt: str, quality: str = "low", size: str = IMAGE_SIZE,
    chroma: tuple[int, int, int] | None = None,
    opaque_bg_prompt: str | None = None,
    ref_images: list[str] | None = None,
    model: str = IMAGE_MODEL,
    key_strength: str = "normal",
    outline_px: int = 0,
) -> bytes:
    """Generate one PNG and return its raw bytes.

    If *chroma* is given, generate opaque on that flat colour and key it out
    locally (preserves the white outline). If *opaque_bg_prompt* is given instead,
    generate opaque on that described background and return it AS-IS (no keying) --
    for solid-colour-background art (e.g. black, for Screen/Add blend compositing)
    where the background must stay literal pixels, not alpha. Otherwise request
    native transparency.

    If *ref_images* (file paths) are given, the provider uses its style-reference
    path; the caller is responsible for telling the model — in *prompt* — which
    references are which.
    """
    if chroma:
        full_prompt = f"{prompt} The artwork must sit on {CHROMA_PROMPT}."
        background = "opaque"
    elif opaque_bg_prompt:
        full_prompt = f"{prompt} The artwork must sit on {opaque_bg_prompt}."
        background = "opaque"
    else:
        full_prompt = f"{prompt} Transparent background."
        background = "transparent"

    provider = get_provider(model)
    data = provider.generate(
        api_key, full_prompt,
        size=size, quality=quality, background=background,
        ref_images=ref_images, model=model,
    )

    if chroma:
        try:
            data = bgremove.remove_chroma(data, chroma, strength=key_strength)
        except Exception:  # noqa: BLE001 - keep the opaque image rather than fail
            log.exception("Local background removal failed; returning opaque image")

    # Deterministic sticker border, drawn on the alpha we now have (keyed or
    # natively transparent). Never on `black` — that mode is opaque by design.
    if outline_px > 0 and not opaque_bg_prompt:
        try:
            data = bgremove.add_outline(data, outline_px)
        except Exception:  # noqa: BLE001 - an un-thickened image beats no image
            log.exception("add_outline failed; returning un-outlined image")
    return data
