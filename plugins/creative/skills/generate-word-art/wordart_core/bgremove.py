"""Chroma-key background removal.

We generate word art opaque on a flat green background (the model keeps the
white outline solid that way) and remove the green here:

1. Flood-fill the background inward from the four corners — this only removes the
   background region that is connected to the edge, so multicolored letters
   (incl. green ones) and their interiors are preserved.
2. A tight global pass clears enclosed background (letter holes) that the edge
   flood-fill can't reach.
3. Edge pixels get green-despill (kills the mint fringe) and the alpha is lightly
   feathered for clean anti-aliased edges.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from wordart_core.logging_setup import get_logger

log = get_logger("bgremove")

_SENTINEL = (255, 0, 255)  # marker colour for flood-filled background

# Key aggressiveness presets (2026-08-17). "normal" reproduces the original
# hardcoded numbers exactly; "aggressive" widens the colour match, widens the
# despill ring and CHOKES the matte by 1px so the residual green fringe on the
# feathered edge is eaten rather than merely desaturated.
KEY_STRENGTHS = {
    "normal":     dict(connect_thresh=120, tight_tol=90.0,  ring=5,  choke=0, feather=1.0),
    "aggressive": dict(connect_thresh=170, tight_tol=145.0, ring=11, choke=1, feather=0.8),
}


def remove_chroma(
    png_bytes: bytes,
    chroma: tuple[int, int, int] = (0, 255, 0),
    connect_thresh: int | None = None,
    tight_tol: float | None = None,
    feather: float | None = None,
    strength: str = "normal",
) -> bytes:
    """Return RGBA PNG bytes with the green background removed.

    *strength* picks a preset from ``KEY_STRENGTHS``; any explicit
    connect_thresh / tight_tol / feather overrides that preset's value.
    """
    preset = KEY_STRENGTHS.get(strength) or KEY_STRENGTHS["normal"]
    connect_thresh = preset["connect_thresh"] if connect_thresh is None else connect_thresh
    tight_tol = preset["tight_tol"] if tight_tol is None else tight_tol
    feather = preset["feather"] if feather is None else feather
    ring_px, choke = preset["ring"], preset["choke"]
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    arr = np.asarray(img).astype(np.float32)

    # Sample the model's actual background colour from the border (it may not be
    # exactly pure green).
    border = np.concatenate([arr[0, :], arr[-1, :], arr[:, 0], arr[:, -1]], axis=0)
    bg_sample = np.median(border, axis=0)

    # (1) connected background via flood-fill from each corner
    flood = img.copy()
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        try:
            ImageDraw.floodfill(flood, seed, _SENTINEL, thresh=connect_thresh)
        except Exception:  # noqa: BLE001 - never let keying crash generation
            log.exception("floodfill failed at %s", seed)
    connected = np.all(np.asarray(flood) == np.array(_SENTINEL), axis=2)

    # (2) enclosed background (letter holes) by tight colour match to the sample
    dist_bg = np.sqrt(((arr - bg_sample) ** 2).sum(axis=2))
    tight = dist_bg < tight_tol
    bg = connected | tight

    alpha = np.where(bg, 0, 255).astype(np.uint8)

    # (2b) choke — erode the kept matte by `choke` px. Despill only *desaturates*
    # the fringe; on a high-contrast edge a mint halo can still survive it, so the
    # aggressive preset simply removes that ring of pixels instead.
    if choke > 0:
        a_img = Image.fromarray(alpha, "L")
        for _ in range(choke):
            a_img = a_img.filter(ImageFilter.MinFilter(3))
        alpha = np.asarray(a_img).copy()
        bg = alpha == 0  # the despill ring must follow the choked matte

    # (3a) green despill on the ring of kept pixels touching the background
    out = arr.copy()
    if chroma[1] >= chroma[0] and chroma[1] >= chroma[2]:  # green-dominant chroma
        bg_img = Image.fromarray((bg * 255).astype(np.uint8), "L")
        ring = (np.asarray(bg_img.filter(ImageFilter.MaxFilter(ring_px))) > 0) & (~bg)
        r, g, b = out[..., 0], out[..., 1], out[..., 2]
        despilled = np.minimum(g, np.maximum(r, b))
        out[..., 1] = np.where(ring, despilled, g)
    out = np.clip(out, 0, 255).astype(np.uint8)

    # (3b) feather alpha for smooth edges, but keep enclosed holes fully clear
    a_img = Image.fromarray(alpha, "L")
    if feather > 0:
        a_img = a_img.filter(ImageFilter.GaussianBlur(feather))
    a = np.asarray(a_img).copy()
    a[tight] = 0

    rgba = np.dstack([out, a]).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def add_outline(
    png_bytes: bytes,
    px: int,
    color: tuple[int, int, int] = (255, 255, 255),
    feather: float = 0.6,
) -> bytes:
    """Grow a solid sticker border *px* pixels wide around the artwork.

    The model-drawn white outline is a prompt instruction, so its thickness is a
    lottery. This adds a deterministic one on top of whatever came back: dilate
    the alpha matte by *px*, paint the new ring *color*, composite the original
    over it. Requires alpha (chroma-keyed or natively transparent) — a no-op on
    an opaque image. px <= 0 returns the input unchanged.
    """
    if px <= 0:
        return png_bytes
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    a = img.getchannel("A")
    if a.getextrema()[0] >= 250:  # opaque ⇒ nothing to outline
        log.warning("add_outline: image has no transparency; skipping")
        return png_bytes

    # binary core, then 1px-per-pass dilation (MaxFilter(3) = 8-connected grow)
    grown = a.point(lambda v: 255 if v >= 128 else 0)
    for _ in range(px):
        grown = grown.filter(ImageFilter.MaxFilter(3))
    if feather > 0:
        grown = grown.filter(ImageFilter.GaussianBlur(feather))

    base = Image.new("RGBA", img.size, color + (0,))
    base.putalpha(grown)
    out = Image.alpha_composite(base, img)

    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()
