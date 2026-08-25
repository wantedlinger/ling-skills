"""Central configuration: loads the API key(s) and holds the tunable constants
(models, sizes, pricing, chroma key, style library paths).

Keys are read from a ``.env`` file in this skill's own folder (see ``.env.example``).
Each subcommand calls ``require_keys(...)`` with only the keys it actually needs, so
an OPENAI_API_KEY alone is enough unless you pick a Gemini model.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent      # the skill folder
ENV_FILE = ROOT / ".env"                            # where the API key(s) live

load_dotenv(ENV_FILE)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def require_keys(need_openai: bool = True, need_gemini: bool = False) -> None:
    """Raise with the exact .env path if a needed key is missing."""
    missing = [
        name for name, need, val in (
            ("OPENAI_API_KEY", need_openai, OPENAI_API_KEY),
            ("GEMINI_API_KEY", need_gemini, GEMINI_API_KEY),
        ) if need and not val
    ]
    if missing:
        raise RuntimeError(
            f"Missing API key(s): {', '.join(missing)} — put them in {ENV_FILE}\n"
            f"Copy .env.example to .env and paste the key in. No key yet? "
            f"Ask in #general."
        )


# --- Model identifiers -----------------------------------------------------
# All image models are usable now that we key out the background locally
# (gpt-image-2 doesn't support a transparent background, but we generate opaque
# on green and remove it ourselves, so that limitation no longer applies).
# gemini-3.1-flash-image added 2026-07-08 (bake-off: 6/6 text accuracy, ~3x
# faster than gpt-image-2, but $0.04/img vs gpt-2-low $0.006 — an option, not
# the default; NEW video sets only, for set consistency).
IMAGE_MODELS = ("gpt-image-1.5", "gpt-image-2", "gemini-3.1-flash-image")
IMAGE_MODEL = "gpt-image-2"  # default (user choice 2026-07-08 reaffirmed: cheapest at low)
# gpt-image-2 processes reference images at high fidelity automatically and
# rejects the input_fidelity parameter, so we only send it for other models.
NO_INPUT_FIDELITY_MODELS = ("gpt-image-2",)

QUALITIES = ("low", "medium", "high")
SIZES = ("1024x1024", "1024x1536", "1536x1024")
IMAGE_SIZE = "1024x1024"  # default

# Base art-style description used when NO style reference is selected (the
# no-reference counterpart of an AI-derived style brief). Structural bits
# (white outline, number of supporting graphics) are separate shared controls,
# not part of this text.
DEFAULT_PLAIN_STYLE = "a cute, flat illustration style"
MAX_SUPPORTING_GRAPHICS = 3
DEFAULT_SUPPORTING_GRAPHICS = 1

# Per-image USD output price by model -> quality -> size, from the OpenAI image
# docs. Note the cheapest size differs by model: square is cheapest on 1.5, but
# the non-square sizes are cheapest on 2. Reference-image input tokens are extra
# (see STYLE_REF_USD_ESTIMATE).
IMAGE_USD_COST = {
    "gpt-image-1.5": {
        "low":    {"1024x1024": 0.009, "1024x1536": 0.013, "1536x1024": 0.013},
        "medium": {"1024x1024": 0.034, "1024x1536": 0.050, "1536x1024": 0.050},
        "high":   {"1024x1024": 0.133, "1024x1536": 0.200, "1536x1024": 0.200},
    },
    "gpt-image-2": {
        "low":    {"1024x1024": 0.006, "1024x1536": 0.005, "1536x1024": 0.005},
        "medium": {"1024x1024": 0.053, "1024x1536": 0.041, "1536x1024": 0.041},
        "high":   {"1024x1024": 0.211, "1024x1536": 0.165, "1536x1024": 0.165},
    },
    # Gemini image models have no quality tiers: flat per-image price.
    "gemini-3.1-flash-image": {
        q: {s: 0.04 for s in ("1024x1024", "1024x1536", "1536x1024")}
        for q in ("low", "medium", "high")
    },
}

# Local background removal (chroma key). The model's native transparent mode
# often drops the white outline (alpha-mattes it away), so we generate opaque on
# a flat green background and key it out ourselves, preserving the outline.
CHROMA_RGB = (0, 255, 0)
CHROMA_PROMPT = (
    "a solid, flat, uniform pure green background (RGB 0,255,0), fully opaque, "
    "with no gradient, no drop shadow, and no outer glow"
)

# Opaque solid-black background, kept as literal pixels (no keying/removal) --
# for glow/neon-style art meant to be composited with an Add/Screen blend mode
# in a video editor, where the black needs to actually BE black (not alpha) and
# any glow/bloom bleeding into it is expected, unlike the chroma-key background.
BLACK_PROMPT = (
    "a solid, flat, uniform pure black background (RGB 0,0,0), fully opaque, "
    "no vignette, no texture; any glow, bloom, or light halo cast by the artwork "
    "itself blending softly into the black is expected and desired"
)

# Gemini text pricing, USD per 1M tokens. Kept for the pricing helper; the image
# models above are priced per image, not per token.
GEMINI_PRICING: dict[str, dict[str, float]] = {}

# --- Style reference images ------------------------------------------------
# A "Style" folder holds two categories of reference images. The caller picks one
# style folder per category (by NUMBER); its images are passed to the OpenAI edit
# endpoint so the word art copies the look — not the content.
#
#   Style/
#     Text Style/          <- lettering/typography of the word itself
#       Style 1/  *.jpg
#     Illustration Style/  <- look of the supporting graphic
#       Style 1/  *.jpg
STYLE_ROOT = ROOT / "Style"
STYLE_CATEGORY_TEXT = "Text Style"
STYLE_CATEGORY_ILLUS = "Illustration Style"
STYLE_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
MAX_STYLE_REFS = 4  # cap per category (gpt-image accepts a handful of references)

# Reference images add input-image tokens that our exact per-image output price
# doesn't cover. This rough per-reference-image USD figure keeps cost estimates
# from undercounting styled runs.
STYLE_REF_USD_ESTIMATE = 0.005
