"""Style reference library — scans the on-disk ``Style/`` tree and builds prompts.

Two categories (Text Style, Illustration Style); each holds named style folders
(``Style 1``, ``Style 8 Irasutoya`` …); each folder holds one or more reference
images plus a cached ``_style_brief.txt``. Styles are selected by NUMBER (the
integer in ``Style N``). Selected images are sent to the OpenAI edit endpoint as
style references; the cached brief (Gemini-derived) goes into the prompt text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from wordart_core.config import (
    MAX_STYLE_REFS,
    STYLE_CATEGORY_ILLUS,
    STYLE_CATEGORY_TEXT,
    STYLE_IMAGE_EXTS,
    STYLE_ROOT,
)
from wordart_core.logging_setup import get_logger

log = get_logger("styles")


@dataclass
class StyleFolder:
    """One named style (e.g. 'Style 1') and the reference images inside it."""

    name: str
    path: Path
    images: list[Path]

    @property
    def refs(self) -> list[str]:
        """Capped list of image paths (as str) to send as references."""
        return [str(p) for p in self.images[:MAX_STYLE_REFS]]

    @property
    def number(self) -> int | None:
        return style_number(self.name)


@dataclass
class StyleSet:
    """The current selection: chosen folder per category (or None), plus the
    AI/user style brief describing each (used to build the prompt)."""

    text: StyleFolder | None = None
    illus: StyleFolder | None = None
    text_brief: str = ""
    illus_brief: str = ""

    @property
    def is_empty(self) -> bool:
        return self.text is None and self.illus is None

    @property
    def text_refs(self) -> list[str]:
        return self.text.refs if self.text else []

    @property
    def illus_refs(self) -> list[str]:
        return self.illus.refs if self.illus else []

    @property
    def all_refs(self) -> list[str]:
        """Ordered references: lettering first, then illustration."""
        return self.text_refs + self.illus_refs


def _list_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return [
        p for p in sorted(folder.iterdir())
        if p.is_file() and p.suffix.lower() in STYLE_IMAGE_EXTS
    ]


def list_folders(category: str) -> list[StyleFolder]:
    """Style folders under ``Style/<category>/`` that contain ≥1 image."""
    base = STYLE_ROOT / category
    if not base.is_dir():
        return []
    out: list[StyleFolder] = []
    for sub in sorted(base.iterdir()):
        if not sub.is_dir():
            continue
        imgs = _list_images(sub)
        if imgs:
            out.append(StyleFolder(sub.name, sub, imgs))
    return out


# --- Number → folder resolution -------------------------------------------
# Folder names start with "Style N" optionally followed by a suffix
# ("Style 8 Irasutoya"). Match the leading integer so "Style 1" never matches 10.
_STYLE_NUM_RE = re.compile(r"^\s*style\s+(\d+)\b", re.IGNORECASE)


def style_number(folder_name: str) -> int | None:
    m = _STYLE_NUM_RE.match(folder_name)
    return int(m.group(1)) if m else None


def resolve(category: str, number: int) -> StyleFolder | None:
    """Find the style folder whose leading 'Style N' integer == *number*."""
    for f in list_folders(category):
        if style_number(f.name) == number:
            return f
    return None


# --- Brief persistence -----------------------------------------------------
BRIEF_FILENAME = "_style_brief.txt"


def brief_file(folder: Path) -> Path:
    """Where a folder's saved style brief lives (so it survives restarts)."""
    return Path(folder) / BRIEF_FILENAME


def load_brief(folder: Path) -> str:
    """Return the brief previously saved for *folder*, or '' if none."""
    f = brief_file(folder)
    try:
        if f.is_file():
            return f.read_text(encoding="utf-8").strip()
    except OSError as e:  # pragma: no cover - filesystem edge
        log.warning("Could not read style brief %s: %s", f, e)
    return ""


def save_brief(folder: Path, brief: str) -> None:
    """Persist *brief* alongside the folder's images (empty brief removes it)."""
    f = brief_file(folder)
    try:
        brief = (brief or "").strip()
        if brief:
            f.write_text(brief, encoding="utf-8")
        elif f.is_file():
            f.unlink()
    except OSError as e:  # pragma: no cover - filesystem edge
        log.warning("Could not save style brief %s: %s", f, e)


def brief_is_stale(folder: StyleFolder) -> bool:
    """True if the cached brief is older than the newest reference image — i.e.
    images were added/changed since the brief was written, so it may not reflect
    the current references. False if there is no brief or no images."""
    f = brief_file(folder.path)
    if not f.is_file() or not folder.images:
        return False
    try:
        brief_mtime = f.stat().st_mtime
        newest_img = max(p.stat().st_mtime for p in folder.images)
    except OSError:  # pragma: no cover - filesystem edge
        return False
    return newest_img > brief_mtime


def text_styles() -> list[StyleFolder]:
    return list_folders(STYLE_CATEGORY_TEXT)


def illustration_styles() -> list[StyleFolder]:
    return list_folders(STYLE_CATEGORY_ILLUS)


def find(category: str, name: str) -> StyleFolder | None:
    for f in list_folders(category):
        if f.name == name:
            return f
    return None


# --- Prompt building -------------------------------------------------------
_GRAPHIC_QTY = {1: "a single", 2: "up to two", 3: "up to three"}
_OUTLINE = "Add a thin, clean white outline (sticker border) around the whole design."
_LATIN_FIX = (
    "Include the Latin characters, the '()' and the English translation as well — "
    "render the entire string exactly as written."
)
# Any character beyond Latin Extended-B (U+024F) → treat the text as non-Latin
# script (CJK, Thai, Devanagari, Cyrillic, …) and apply the Latin fix.
_NON_LATIN_RE = re.compile(r"[^\u0000-\u024f]")


def needs_latin_fix(text: str) -> bool:
    return bool(_NON_LATIN_RE.search(text or ""))


def _clean(s: str) -> str:
    return (s or "").strip().rstrip(".")


def _count_word(n: int) -> str:
    return _GRAPHIC_QTY.get(n, f"up to {n}")


def _graphics_clause(graphics: list[str] | None, n_override: int | None = None) -> str:
    """The 'include N supporting graphic(s)…' (or 'none') sentence.

    Count defaults to the number of described graphics; pass *n_override* to force
    a count (e.g. 0 for lettering-only when no graphic was requested)."""
    descs = [_clean(g) for g in (graphics or []) if _clean(g)]
    n = n_override if n_override is not None else len(descs)
    if n <= 0:
        return "Do not include any supporting graphics; render only the lettering."
    noun = "supporting graphic" if n == 1 else "supporting graphics"
    if descs:
        return f"Include {_count_word(n)} small {noun} depicting: " + "; ".join(descs) + "."
    return f"Include {_count_word(n)} small {noun}."


def plain_prompt(
    word: str,
    style_desc: str = "",
    graphics: list[str] | None = None,
    num_graphics: int | None = None,
    keep_outline: bool = True,
    latin_fix: bool = False,
) -> str:
    """Prompt for a NO-reference run: the caller's typed base style + shared knobs.

    With no *graphics* (and no *num_graphics*), this renders lettering only."""
    style_desc = _clean(style_desc)
    parts = [f'Create word art for the word "{word}".']
    if style_desc:
        parts.append(f"Overall art style: {style_desc}.")
    parts.append(_graphics_clause(graphics, num_graphics))
    parts.append(f'The letters must spell exactly "{word}".')
    if latin_fix:
        parts.append(_LATIN_FIX)
    if keep_outline:
        parts.append(_OUTLINE)
    return " ".join(parts)


def styled_prompt(
    word: str,
    text_brief: str = "",
    illus_brief: str = "",
    graphics: list[str] | None = None,
    num_graphics: int | None = None,
    keep_outline: bool = True,
    latin_fix: bool = False,
) -> str:
    """Prompt for a styled run.

    Unlike the plain prompt, this does NOT assert a generic look — that would
    override the reference. The lettering / illustration look comes entirely from
    the briefs (derived from the reference images), so the prompt text and the
    reference images agree."""
    text_brief = _clean(text_brief)
    illus_brief = _clean(illus_brief)

    descs = [_clean(g) for g in (graphics or []) if _clean(g)]
    n = num_graphics if num_graphics is not None else len(descs)

    parts = [f'Create word art for the word "{word}".']
    if text_brief:
        parts.append(f"Lettering style: {text_brief}.")
    parts.append(_graphics_clause(graphics, num_graphics))
    if n > 0 and illus_brief:
        parts.append(f"Illustration style for the supporting graphic(s): {illus_brief}.")
    parts.append(f'The letters must spell exactly "{word}".')
    parts.append(
        "Closely match the look of the provided reference image(s); use them for "
        "style only — do not copy any words, letters, or specific objects from them."
    )
    if latin_fix:
        parts.append(_LATIN_FIX)
    if keep_outline:
        parts.append(_OUTLINE)
    return " ".join(parts)


def graphic_only_prompt(
    graphics: list[str] | None,
    illus_brief: str = "",
    keep_outline: bool = True,
    styled: bool = False,
) -> str:
    """No lettering at all — render only the supporting graphic(s).

    EXPERIMENTAL: the no-text path is new and lightly tested. The caller should
    require ≥1 graphic before using this builder."""
    descs = [_clean(g) for g in (graphics or []) if _clean(g)]
    if descs:
        noun = "illustration" if len(descs) == 1 else "illustrations"
        body = f"Create {_count_word(len(descs))} {noun} depicting: " + "; ".join(descs) + "."
    else:  # defensive — caller should have required at least one graphic
        body = "Create a single small illustration."
    parts = [body, "Do not include any text, letters, or words anywhere in the image."]
    if styled and _clean(illus_brief):
        parts.append(f"Illustration style: {_clean(illus_brief)}.")
    if styled:
        parts.append(
            "Closely match the look of the provided reference image(s); use them "
            "for style only — do not copy any specific objects from them."
        )
    if keep_outline:
        parts.append(_OUTLINE)
    return " ".join(parts)
