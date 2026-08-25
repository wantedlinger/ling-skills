# Word art generator (Ling)

Generates the **orange outlined word stickers** used on Ling social videos: a word in the Ling
title lettering on a transparent PNG with a white die-cut edge, optionally with a small
illustration (the Ling mascot, or a Word-Icon-style graphic). Drop the PNG straight into After
Effects, Premiere, Canva or Figma.

You do not have to read this file — **just ask Claude for the word art you want** and it will
follow `SKILL.md`. This is the reference for what it is doing.

- **Privilege level:** `can-send` — it writes only local files, but each image is a paid API
  call (≈ **$0.01**, range $0.006–$0.05).
- **Owner:** Zinc (Vasu Laeietpiboon), Growth Marketing · questions and API keys: **#general**
- **Needs:** Python 3.10+ and an `OPENAI_API_KEY`. Runs on macOS, Windows and Linux.

## Setup

```bash
pip3 install -r requirements.txt
cp .env.example .env        # then paste your key into .env
```

On Windows use `pip` / `python` if `pip3` / `python3` are not found, and `copy` instead of `cp`.

No key? Ask in **#general** for the shared Ling one, or make your own at
<https://platform.openai.com/api-keys> (then the images bill to you).

## Use

```bash
# see the three bundled styles
python3 run_cli.py rescan
# ...or open styles.html to look at the reference art

# one word
python3 run_cli.py generate \
  --out "/absolute/path/hello.png" \
  --text "Hello" --text-style 1 --illus-style 2 \
  --graphic "a waving hand entering frame from the right"

# a word list: write jobs.json, then ONE command (up to 20 in parallel)
python3 run_cli.py generate-batch --jobs "/absolute/path/jobs.json"

# review the set -- always do this
python3 build_output_gallery.py --dir "/absolute/path/to/output/folder"

# fix the sticker edge without paying again
python3 run_cli.py restroke --in "/abs/in.png" --out "/abs/out.png" --outline-px 16
```

All paths must be **absolute** — that is deliberate, so nothing lands in a surprise folder.

## Styles

Fixed at three; this version does not add more.

| Category | # | Name |
|---|---|---|
| Text | 1 | Ling Orange Outline |
| Illustration | 1 | Ling Mascot |
| Illustration | 2 | Ling Word Icon |

Each style folder holds its reference art plus a `_style_brief.txt` — the written description
that goes into the prompt. Style 2 also has `_composition_recipes.md`, a set of ready-made
framings to paste into `--graphic`.

## How it works

The word and the style brief become a prompt; the image is generated on a flat green background
and the green is **keyed out locally**, which preserves the white sticker edge that the model's
own transparent mode tends to erase. The outline width and the key strength are pure
post-processing, so `restroke` re-tunes them on an existing PNG for **$0**.

## Good to know

- Everything is **soft**: an ambiguous or under-specified input is flagged and the command exits
  non-zero **before** any paid call. A batch validates every job first, so a typo costs $0.
- **No graphic description ⇒ lettering only.** Nothing is invented.
- **Always review the output** in `gallery.html` before using it — check every spelling, and
  never ship an image flagged `KEYING FAILED`.
- Exit codes: `0` ok · `2`/`3` validation ($0) · `4` moderation · `5` generation failed ·
  `6` batch had failures · `7` keying failed · `130` cancelled.

Full instructions, the gotcha list and the definition of done live in **`SKILL.md`**.

## Files

| Path | What it is |
|---|---|
| `SKILL.md` | The instructions Claude follows |
| `run_cli.py` | CLI: `generate`, `generate-batch`, `restroke`, `rescan` |
| `wordart_core/` | Prompt building, image providers, chroma keying, pricing |
| `Style/` | The three bundled styles: reference art + briefs |
| `build_gallery.py` | Rebuilds `styles.html` (the style picker) |
| `build_output_gallery.py` | Builds `gallery.html` (the output review page) |
| `.env.example` | Template for your API key |
