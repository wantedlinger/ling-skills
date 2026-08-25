#!/usr/bin/env python3
"""Build a visual style gallery (styles.html) for the generate-word-art skill.

Scans Style/Text Style/* and Style/Illustration Style/*, reads each _style_brief.txt,
and emits a single self-contained styles.html that maps each STYLE NUMBER to its
reference picture(s) + description. Open it in a browser to pick a style by eye, then
type the number into the skill.

Re-run after adding/removing styles:  python build_gallery.py
"""
import re
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STYLE_DIR = ROOT / "Style"
OUT = ROOT / "styles.html"

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
CATEGORIES = ["Text Style", "Illustration Style"]


def natural_key(p: Path):
    """Sort 'Style 2' before 'Style 10'; pull the leading style number out."""
    m = re.search(r"(\d+)", p.name)
    return (int(m.group(1)) if m else 9999, p.name.lower())


def style_number(name: str) -> str:
    m = re.search(r"Style\s*(\d+)", name)
    return m.group(1) if m else name


def rel_url(path: Path) -> str:
    """Browser-safe relative URL from OUT's folder (encode spaces etc.)."""
    rel = path.relative_to(ROOT).as_posix()
    return "/".join(part.replace(" ", "%20").replace("#", "%23") for part in rel.split("/"))


def collect(category: str):
    cat_dir = STYLE_DIR / category
    if not cat_dir.is_dir():
        return []
    cards = []
    for d in sorted([p for p in cat_dir.iterdir() if p.is_dir()], key=natural_key):
        imgs = sorted([p for p in d.iterdir() if p.suffix.lower() in IMG_EXT])
        brief_file = d / "_style_brief.txt"
        brief = brief_file.read_text(encoding="utf-8", errors="replace").strip() if brief_file.exists() else ""
        # note any extra label after the number, e.g. "Irasutoya", "Love"
        tag = re.sub(r"^Style\s*\d+\s*", "", d.name).strip()
        cards.append({
            "num": style_number(d.name),
            "tag": tag,
            "imgs": [rel_url(i) for i in imgs],
            "brief": brief,
            "folder": d.name,
        })
    return cards


def render_section(title: str, cards) -> str:
    if not cards:
        return f"<section><h2>{html.escape(title)}</h2><p class='empty'>No styles found.</p></section>"
    tiles = []
    for c in cards:
        n = len(c["imgs"])
        if n == 0:
            carousel = "<div class='thumbs'><div class='noimg'>no image</div></div>"
        else:
            slides = "".join(
                f"<img src='{u}' loading='lazy' alt='Style {c['num']}' "
                f"class='{'on' if i == 0 else ''}'>"
                for i, u in enumerate(c["imgs"])
            )
            controls = ""
            if n > 1:
                controls = (
                    "<button class='nav prev' aria-label='Previous'>&#8249;</button>"
                    "<button class='nav next' aria-label='Next'>&#8250;</button>"
                    f"<div class='counter'><span class='cur'>1</span>/{n}</div>"
                )
            carousel = (
                f"<div class='thumbs carousel' data-n='{n}' data-i='0' tabindex='0'>"
                f"{slides}{controls}</div>"
            )
        tag = f" <span class='tag'>{html.escape(c['tag'])}</span>" if c["tag"] else ""
        tiles.append(f"""
        <article class="tile">
          {carousel}
          <div class="meta">
            <div class="num">{html.escape(c['num'])}{tag}</div>
            <p class="brief">{html.escape(c['brief'])}</p>
          </div>
        </article>""")
    return f"""
    <section>
      <h2>{html.escape(title)} <span class="count">({len(cards)})</span></h2>
      <div class="grid">{''.join(tiles)}</div>
    </section>"""


def main():
    sections = [render_section(cat, collect(cat)) for cat in CATEGORIES]
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Word &amp; Graphic — Style Gallery</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0;
         background: #fafafa; color: #1a1a1a; }}
  header {{ position: sticky; top: 0; background: #111; color: #fff; padding: 14px 22px;
           z-index: 5; box-shadow: 0 2px 8px rgba(0,0,0,.25); }}
  header h1 {{ margin: 0; font-size: 17px; font-weight: 650; }}
  header p {{ margin: 4px 0 0; font-size: 12.5px; opacity: .75; }}
  main {{ padding: 8px 22px 60px; }}
  section {{ margin-top: 26px; }}
  h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: .06em;
        color: #555; border-bottom: 2px solid #e3e3e3; padding-bottom: 6px; }}
  h2 .count {{ color: #aaa; font-weight: 400; }}
  .grid {{ display: grid; gap: 16px; margin-top: 14px;
           grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }}
  .tile {{ background: #fff; border: 1px solid #e6e6e6; border-radius: 12px;
           overflow: hidden; display: flex; flex-direction: column;
           box-shadow: 0 1px 3px rgba(0,0,0,.06); transition: transform .12s, box-shadow .12s; }}
  .tile:hover {{ transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,.12); }}
  .thumbs {{ position: relative; background:
             repeating-conic-gradient(#eee 0 25%, #fff 0 50%) 0 0 / 20px 20px;
             min-height: 180px; display: flex; align-items: center; justify-content: center;
             outline: none; }}
  .carousel:focus-visible {{ box-shadow: inset 0 0 0 3px #4c8dff; }}
  .thumbs img {{ display: none; width: 100%; height: 180px; object-fit: contain; }}
  .thumbs img.on {{ display: block; }}
  .nav {{ position: absolute; top: 50%; transform: translateY(-50%); width: 30px; height: 44px;
          border: none; background: rgba(0,0,0,.42); color: #fff; font-size: 24px; line-height: 1;
          cursor: pointer; opacity: 0; transition: opacity .12s, background .12s; z-index: 2; }}
  .nav:hover {{ background: rgba(0,0,0,.68); }}
  .nav.prev {{ left: 0; border-radius: 0 6px 6px 0; }}
  .nav.next {{ right: 0; border-radius: 6px 0 0 6px; }}
  .tile:hover .nav, .carousel:focus-within .nav, .carousel:focus .nav {{ opacity: 1; }}
  .counter {{ position: absolute; bottom: 6px; right: 8px; z-index: 2;
              background: rgba(0,0,0,.55); color: #fff; font-size: 11px; font-weight: 600;
              padding: 2px 7px; border-radius: 10px; }}
  .noimg {{ color: #bbb; font-size: 12px; padding: 40px; }}
  .meta {{ padding: 10px 13px 14px; }}
  .num {{ font-size: 26px; font-weight: 800; line-height: 1; }}
  .tag {{ font-size: 11px; font-weight: 600; vertical-align: middle; margin-left: 6px;
          background: #ffe9b0; color: #7a5b00; padding: 2px 7px; border-radius: 10px; }}
  .brief {{ font-size: 12.5px; line-height: 1.45; color: #444; margin: 8px 0 0; }}
  .empty {{ color: #999; }}
</style>
</head>
<body>
<header>
  <h1>Word &amp; Graphic — Style Gallery</h1>
  <p>Pick by picture, then type the <b>number</b> into the skill. Two independent choices: a Text Style and an Illustration Style.</p>
</header>
<main>
{''.join(sections)}
</main>
<script>
(function () {{
  function show(car, idx) {{
    var imgs = car.querySelectorAll('img');
    if (!imgs.length) return;
    var n = imgs.length;
    idx = ((idx % n) + n) % n;            // wrap around
    imgs.forEach(function (im, i) {{ im.classList.toggle('on', i === idx); }});
    car.dataset.i = idx;
    var cur = car.querySelector('.counter .cur');
    if (cur) cur.textContent = idx + 1;
  }}
  function step(car, d) {{ show(car, parseInt(car.dataset.i || '0', 10) + d); }}

  document.querySelectorAll('.carousel').forEach(function (car) {{
    var prev = car.querySelector('.nav.prev');
    var next = car.querySelector('.nav.next');
    if (prev) prev.addEventListener('click', function (e) {{ e.stopPropagation(); car.focus(); step(car, -1); }});
    if (next) next.addEventListener('click', function (e) {{ e.stopPropagation(); car.focus(); step(car, 1); }});
  }});

  // Arrow keys drive whichever carousel is hovered (preferred) or focused.
  var hovered = null;
  document.querySelectorAll('.tile').forEach(function (tile) {{
    var car = tile.querySelector('.carousel');
    if (!car) return;
    tile.addEventListener('mouseenter', function () {{ hovered = car; }});
    tile.addEventListener('mouseleave', function () {{ if (hovered === car) hovered = null; }});
  }});
  document.addEventListener('keydown', function (e) {{
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    var target = hovered;
    if (!target) {{
      var a = document.activeElement;
      if (a && a.classList.contains('carousel')) target = a;
    }}
    if (!target || (target.querySelectorAll('img').length < 2)) return;
    e.preventDefault();
    step(target, e.key === 'ArrowRight' ? 1 : -1);
  }});
}})();
</script>
</body>
</html>"""
    OUT.write_text(doc, encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
