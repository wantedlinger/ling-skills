"""Image-generation provider seam.

Each provider module exposes one function with a fixed contract:

    generate(api_key, full_prompt, *, size, quality, background, ref_images, model) -> bytes

returning raw PNG bytes (opaque or transparent per *background*; the caller does
any local chroma keying). ``get_provider`` dispatches by model name so a future
non-OpenAI vendor is one new module + one line here.
"""
from __future__ import annotations


def get_provider(model: str):
    """Return the provider module that handles *model*."""
    if model.startswith("gpt-image"):
        from wordart_core.providers import openai_provider
        return openai_provider
    if model.startswith("gemini"):
        from wordart_core.providers import gemini_provider
        return gemini_provider
    raise ValueError(
        f"No image provider registered for model {model!r}. "
        f"Add one in wordart_core/providers/ and register it in get_provider()."
    )
