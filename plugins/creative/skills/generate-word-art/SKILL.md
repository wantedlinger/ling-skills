---
name: generate-word-art
description: Generate Ling-branded "word art" sticker PNGs — a word rendered in the Ling title lettering, optionally with a supporting illustration (the Ling mascot or a Word-Icon-style graphic), on a transparent background with a white sticker edge. For language-learning videos, thumbnails, and social graphics. One word ⇒ `generate`; a word LIST ⇒ `generate-batch` (ONE command, up to 20 in parallel). Needs an OpenAI API key; costs about $0.01 per image.
---

# Word art generator (Ling)

Makes the orange outlined word stickers you see on Ling social videos — a word in the Ling
title lettering, on a transparent PNG with a white die-cut edge, optionally with a small
illustration next to it. Drop the PNG straight into After Effects, Premiere, Canva or Figma.

## About

- **Privilege level: `can-send`.** It writes only local PNG files, but every image is a paid
  API call on a key you supply, so it **spends money**. Roughly **$0.006–$0.05 per image**
  (default settings ≈ $0.01). A 20-word batch is about 20 cents. Nothing is sent anywhere and
  nothing is published.
- **Owner:** Zinc (Vasu Laeietpiboon), Growth Marketing. Ask in **#general** for a key or for help.
- **Needs:** Python 3.10+ and an `OPENAI_API_KEY`. No other accounts or connections.
- **Works on** macOS, Windows and Linux.

## First run (do this once)

1. **Install the dependencies**
   ```
   pip3 install -r requirements.txt
   ```
   On Windows use `pip` and `python` if `pip3`/`python3` are not found.
2. **Make the `.env` file.** Copy `.env.example` to `.env` in this same folder and paste the
   key after `OPENAI_API_KEY=`.
   **No key?** Ask in **#general** — there is a shared Ling key. (Or make your own at
   https://platform.openai.com/api-keys, but then the images bill to you.)
3. **Ask the user where the PNGs should go**, and use that absolute path for every `--out`.
   A folder inside their current project is usually right. The tool refuses relative paths on
   purpose, so nothing lands in a surprise directory.

## What to ask the user before generating

1. **The word or phrase** — exactly as it should appear, **including the capitalisation you
   want**; the model largely follows the case you feed it.
2. **A supporting graphic?** Describe the object explicitly, or say no.
   **No description ⇒ lettering only.** Nothing is invented.
3. **Which illustration style**, if there is a graphic (see the table below).
4. **Where to save it** (see step 3 above).

Everything else has a working default. Everything is **soft**: if an input is ambiguous the
command flags it and exits **before** any paid call, so a mistake costs $0.

## The styles

Three, and they are fixed — this skill ships the Ling house set and does not add more.
Run `python3 run_cli.py rescan` to print them, or **open `styles.html` to see the reference
art**.

| Category | # | Name | Use it for |
|---|---|---|---|
| Text | **1** | Ling Orange Outline | Every word. Bold rounded sans in hollow Ling orange (`#FF9900`) with a flat peach echo behind it, on a white die-cut sticker. Reads at thumbnail size over busy footage. |
| Illustration | **1** | Ling Mascot | When the graphic should be **the Ling monkey doing something**. Flat vector, cap, cream belly, two dot eyes, no mouth — the pose carries the feeling, so describe a pose. |
| Illustration | **2** | Ling Word Icon | A normal vocabulary word — objects, people, scenes in the Ling Word Icon look. `Style/Illustration Style/Style 2 Ling Word Icon/_composition_recipes.md` holds ready-made framings (solo object, character + prop, building facade…) you can paste into `--graphic`. |

## Generating

**One word** — one command, one PNG:

```
python3 run_cli.py generate \
  --out "/absolute/path/hello.png" \
  --text "Hello" \
  --text-style 1 --illus-style 2 \
  --graphic "a waving hand entering frame from the right"
```

**A word list (2 or more)** — write a `jobs.json` (a JSON list; each object takes the same
flags as `generate`, `out` required, `graphic` may be a string or a list), then run **ONE**
command:

```
python3 run_cli.py generate-batch --jobs "/absolute/path/jobs.json"
```

Up to 20 words run in parallel, and **every job is validated before any of them is paid for**.
**Never launch several `generate` commands as separate tool calls** — they queue one at a time
instead of running together, which is slower for no benefit.

Failed jobs are written to `<jobs>.failed.json` for a one-command rerun. Ctrl-C is safe:
queued jobs are cancelled unpaid.

## Reviewing (always do this)

```
python3 build_output_gallery.py --dir "/absolute/path/to/your/output/folder"
```

Writes `gallery.html` next to the images — every PNG on a checkerboard so transparency is
visible, with a loud warning on any image that came back opaque. Open it, look at the set,
and check the spelling of every word yourself. **Never hand over a batch you have not looked
at**, especially in a script you cannot read.

## Fixing the sticker edge for $0

The white outline and the background removal are **post-processing, not part of the image** —
so tune them on a PNG you already paid for. Never regenerate to change the edge.

```
python3 run_cli.py restroke --in "/abs/in.png" --out "/abs/out.png" \
  --outline-px 16 --key-strength aggressive --overwrite
```

- `--outline-px N` grows the white sticker border N px. Unsure? Restroke a ladder (0 / 8 / 16 /
  28) and let the user pick — still $0.
- `--key-strength aggressive` removes a residual green fringe (rather than just dulling it).

## Known gotchas

- **`--outline-px` also outlines interior holes.** Around 28 px it starts filling in gaps like
  bike spokes or the space under an arm.
- **Only re-key a PNG that still has green in it.** "Has alpha" is not the test. Re-keying an
  already-outlined file silently eats the entire white border. `restroke` measures this and
  blocks it, but the rule is: re-key from the original output, never from an outlined one.
- **Non-Latin script** (Thai, Hindi, CJK…) auto-gets the Latin spelling and the English gloss
  added. Eyeball that all parts rendered; force it with `--latin-fix on`.
- **A Latin word with a gloss in brackets** — `Uzmi još (Take more)` — does **not** trigger that
  automatically, and the bracketed half often gets dropped. **Pass `--latin-fix on`.**
- **`--latin-fix on` is also the anti-translate flag.** A title shaped like `<word> in <language>`
  is sometimes read as an instruction to translate the word; `on` forces it to render the string
  exactly as written.
- **But if the user's text uses `=` or `→` instead of brackets, leave latin-fix `off`** — its
  instruction literally names brackets, so it will rewrite their layout.
- **Case is not guaranteed uniform across a batch.** If a set must match, pass the target case
  explicitly in every `--text` and check the gallery.
- **Text inside the illustration is a lottery.** Keep any invented lettering in a graphic to
  about 3 characters (a number, a short sign) or leave it out.
- **A restyled meme stops being the meme.** Redrawing a famous image in a flat vector style
  lands between registers and reads as neither. Say so before generating one.
- **Moderation blocks surface as exit 4** with nothing written and nothing charged. Reword.

## Exit codes

`0` ok · `2`/`3` validation flag or missing API key (**$0** — nothing generated) ·
`4` moderation blocked ·
`5` generation failed · `6` batch had failed jobs (rerun `<jobs>.failed.json`) ·
`7` **keying failed** — the PNG is opaque, do not ship it blind · `130` batch cancelled.

## Definition of done

**Pass condition.** For a given word, the command exits `0` and writes a PNG at the requested
absolute path that satisfies all four:

1. The word is spelled **exactly** as supplied, all of it — including any bracketed gloss or
   second line — with no invented, dropped, or duplicated characters.
2. The image has a real alpha channel and the background is transparent (the gallery shows the
   checkerboard through it, and no `KEYING FAILED` warning appears).
3. The lettering is in the requested text style, and any supporting graphic is in the requested
   illustration style.
4. Only the objects described in `--graphic` are present. Nothing was invented; if no graphic
   was described, the image is lettering only.

**Golden example.**
Input: `--text "Kumusta" --text-style 1 --illus-style 2 --graphic "a waving hand entering frame from the right" --out "/tmp/kumusta.png"`
Accepted output: a 1024×1024 transparent PNG showing `Kumusta` — spelled exactly that, one word,
capital K — in hollow orange outlined letters with the pale peach echo behind and a white sticker
edge around the lockup, plus one flat vector waving hand at the side. No other objects, no second
word, no background.

**Adversarial case.**
Input: `--text "" --illus-style 2` with no `--graphic` — nothing to letter and nothing to draw.
Expected: it **refuses** with a `FLAG:` line and exits non-zero **before spending anything**;
it must not guess a word or invent a picture. The same holds for a relative `--out` path, an
`--out` that already exists without `--overwrite`, and a style number that does not exist —
each is a $0 refusal with a message naming the problem, never a best-effort image.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Missing API key(s)` | Copy `.env.example` to `.env` and paste the key. Ask in #general for one. |
| `--out must be an absolute path` | Give the full path to the file, not just `word.png`. |
| `--out already exists` | Add `--overwrite`, or pick a new filename. |
| Exit 4, "moderation" | The wording tripped the safety filter. Reword the text or the graphic. |
| Exit 7, `KEYING FAILED` | The image came back opaque. Rerun that word; do not use the file. |
| A bracketed gloss is missing | Regenerate with `--latin-fix on`. |
| Green fringe around the art | `restroke --key-strength aggressive` — no new image needed. |
