#!/usr/bin/env python3
"""Build a review page for the PNGs you just generated.

Scans a folder of output .png files and writes gallery.html next to them: every
image on a checkerboard so you can SEE the transparency, with its filename and
pixel size. This is the review step -- look at the set before you use any of it.

    python3 build_output_gallery.py --dir "/absolute/path/to/your/output/folder"

Then open the gallery.html it prints. No API key, no cost, no network.
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

CHECKER = (
    "background-image:"
    "linear-gradient(45deg,#d8dde2 25%,transparent 25%),"
    "linear-gradient(-45deg,#d8dde2 25%,transparent 25%),"
    "linear-gradient(45deg,transparent 75%,#d8dde2 75%),"
    "linear-gradient(-45deg,transparent 75%,#d8dde2 75%);"
    "background-size:20px 20px;"
    "background-position:0 0,0 10px,10px -10px,-10px 0;"
    "background-color:#f4f6f8;"
)

CSS = """
*{box-sizing:border-box}
body{margin:0;padding:32px;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
     background:#eef1f4;color:#1d2b33}
h1{margin:0 0 4px;font-size:22px}
.sub{color:#5c788a;margin-bottom:28px}
.grid{display:grid;gap:20px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
.tile{background:#fff;border-radius:12px;overflow:hidden;
      box-shadow:0 1px 3px rgba(0,0,0,.12),0 6px 18px rgba(0,0,0,.06)}
.shot{__CHECKER__ display:flex;align-items:center;justify-content:center;
      min-height:240px;padding:12px}
.shot img{max-width:100%;max-height:320px;display:block}
.meta{padding:10px 14px 14px}
.num{display:inline-block;background:#FF9900;color:#fff;font-weight:700;
     border-radius:5px;padding:1px 8px;margin-right:8px;font-size:13px}
.name{font-weight:600;word-break:break-all}
.dim{color:#5c788a;font-size:13px;margin-top:3px}
.warn{color:#b4331f;font-size:13px;margin-top:3px;font-weight:600}
.empty{padding:40px;background:#fff;border-radius:12px;color:#5c788a}
""".replace("__CHECKER__", CHECKER)


def png_info(p: Path) -> tuple[str, str]:
    """(size text, warning text) -- reads the header only, no Pillow needed."""
    try:
        raw = p.read_bytes()
        if raw[:8] != b"\x89PNG\r\n\x1a\n":
            return "", "not a PNG"
        w = int.from_bytes(raw[16:20], "big")
        h = int.from_bytes(raw[20:24], "big")
        colour_type = raw[25]
        alpha = colour_type in (4, 6)
        warn = "" if alpha else "NO transparency -- do not ship this blind"
        return f"{w} x {h} px", warn
    except OSError as e:
        return "", f"unreadable ({e})"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="folder holding the generated .png files")
    ap.add_argument("--out", default=None, help="output html (default: <dir>/gallery.html)")
    args = ap.parse_args()

    folder = Path(args.dir).expanduser()
    if not folder.is_dir():
        print(f"FLAG: not a folder: {folder}", file=sys.stderr)
        sys.exit(2)

    pngs = sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() == ".png")
    out = Path(args.out).expanduser() if args.out else folder / "gallery.html"

    tiles = []
    for i, p in enumerate(pngs, 1):
        size, warn = png_info(p)
        try:
            src = p.relative_to(out.parent).as_posix()
        except ValueError:
            src = p.resolve().as_uri()
        tiles.append(
            f'<article class="tile"><div class="shot">'
            f'<img src="{html.escape(src)}" alt="{html.escape(p.name)}"></div>'
            f'<div class="meta"><span class="num">{i}</span>'
            f'<span class="name">{html.escape(p.name)}</span>'
            f'<div class="dim">{html.escape(size)}</div>'
            + (f'<div class="warn">{html.escape(warn)}</div>' if warn else "")
            + "</div></article>"
        )

    body = ('<div class="grid">' + "".join(tiles) + "</div>") if tiles else \
        '<div class="empty">No .png files in that folder yet.</div>'

    out.write_text(
        "<!doctype html><meta charset='utf-8'>"
        f"<title>Word art -- {html.escape(folder.name)}</title>"
        f"<style>{CSS}</style>"
        f"<h1>Word art review</h1>"
        f"<div class='sub'>{len(pngs)} image(s) in {html.escape(str(folder))} "
        f"&middot; checkerboard = transparent</div>{body}",
        encoding="utf-8",
    )
    print(f"{len(pngs)} image(s) -> {out}")
    print("Open that file in a browser to review the set.")


if __name__ == "__main__":
    main()
