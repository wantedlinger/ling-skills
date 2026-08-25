"""Headless entry point for the generate-word-art skill.

`generate` is atomic (one PNG); `generate-batch` runs a whole word list from a
jobs.json with up to 20 JOBS in parallel (jobs = different words; that cap is
NOT the `--n`-style variations knob other tools have). Everything is SOFT:
ambiguous/under-specified inputs are flagged and the command exits non-zero
BEFORE any paid image call — batch validates ALL jobs first ($0 on any flag).

Subcommands:
  generate        one styled word-art / graphic-only PNG
  generate-batch  a word list from a jobs.json (≤20 parallel, all-or-nothing validation)
  rescan          list the bundled styles by NUMBER (no API key needed)

Models: gpt-image-2 (default) / gpt-image-1.5 / gemini-3.1-flash-image
(~3x faster, no quality tiers, new-video sets only — see SKILL.md).
Run `python run_cli.py <subcommand> -h` for flags. Pass ABSOLUTE paths.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from wordart_core import config, styles

# friendly category key -> on-disk category name / Gemini "kind"
CAT = {"text": config.STYLE_CATEGORY_TEXT, "illus": config.STYLE_CATEGORY_ILLUS}
KIND = {"text": "text", "illus": "illustration"}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _die(msg: str, code: int = 2) -> "NoReturn":  # type: ignore[name-defined]
    """Print a SOFT flag and exit non-zero (no paid call has happened)."""
    print(f"FLAG: {msg}", file=sys.stderr)
    sys.exit(code)


class JobFlag(Exception):
    """A SOFT validation flag for one job. Single commands turn it into a
    _die() exit (see main()); generate-batch collects one per bad job so the
    user sees ALL problems at once — still before any paid call."""

    def __init__(self, msg: str, code: int = 2):
        super().__init__(msg)
        self.code = code


def _parse_style(value: str | None) -> int | None:
    """'none'/empty -> None; otherwise an int style number."""
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in ("", "none"):
        return None
    if not v.isdigit():
        raise JobFlag(f"style must be an integer or 'none', got {value!r}")
    return int(v)


def _brief_status(folder: styles.StyleFolder) -> str:
    """'cached' | 'MISSING'. Every bundled style ships with its brief, so
    MISSING means a file was deleted, not that one needs deriving."""
    return "cached" if styles.load_brief(folder.path) else "MISSING"


def _style_summary(folder: styles.StyleFolder) -> str:
    """The one-line human description in _summary.txt (blank if absent)."""
    f = folder.path / "_summary.txt"
    try:
        return f.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except (OSError, IndexError):
        return ""


def _resolve_style(cat_key: str, number: int):
    """Resolve a style number to a folder or SOFT-fail with a helpful hint."""
    folder = styles.resolve(CAT[cat_key], number)
    if folder is None:
        raise JobFlag(
            f"{cat_key}-style {number} did not resolve — run "
            f"`rescan --category {cat_key}` to see available numbers."
        )
    return folder


def _ensure_brief(cat_key: str, folder: styles.StyleFolder) -> tuple[str, str]:
    """Return (brief, note) from the style's bundled ``_style_brief.txt``.

    The brief is the written description of the style that goes into the prompt;
    every bundled style ships with one, so a missing file is a broken install
    rather than something to re-derive."""
    brief = styles.load_brief(folder.path)
    if not brief:
        raise JobFlag(
            f"no _style_brief.txt for {cat_key} style {folder.number} "
            f"{folder.name!r} — reinstall the plugin to restore it."
        )
    return brief, "cached"


# --------------------------------------------------------------------------- #
# generate
# --------------------------------------------------------------------------- #
def _build_job(args: argparse.Namespace) -> dict:
    """Validate one job's inputs and build its prompt + refs (no paid image call).

    Shared by `generate` (one job, JobFlag -> _die in main()) and
    `generate-batch` (many jobs, JobFlags collected).
    """
    out = Path(args.out)
    if not out.is_absolute():
        raise JobFlag(f"--out must be an absolute path, got {args.out!r}")
    if out.exists() and not args.overwrite:
        raise JobFlag(f"--out already exists: {out} (pass --overwrite to replace)", code=3)

    text = (args.text or "").strip()
    graphics = [g for g in (args.graphic or []) if g.strip()]
    text_num = _parse_style(args.text_style)
    illus_num = _parse_style(args.illus_style)

    text_folder = illus_folder = None
    text_brief = illus_brief = ""
    notes: list[str] = []

    # ---- mode selection -------------------------------------------------- #
    if text:
        if graphics:
            mode = "word+graphic"
        else:
            mode = "lettering-only"
            if illus_num is not None:
                notes.append("illus-style ignored (no --graphic, so no supporting graphic)")
                illus_num = None
        # resolve lettering style (used in both word+graphic and lettering-only)
        if text_num is not None:
            text_folder = _resolve_style("text", text_num)
            text_brief, n = _ensure_brief("text", text_folder)
            notes.append(f"text-style brief: {n}")
        # resolve illustration style only when there is a graphic
        if mode == "word+graphic" and illus_num is not None:
            illus_folder = _resolve_style("illus", illus_num)
            illus_brief, n = _ensure_brief("illus", illus_folder)
            notes.append(f"illus-style brief: {n}")
    else:
        # graphic-only (EXPERIMENTAL)
        if not graphics:
            raise JobFlag("nothing to generate: provide --text and/or at least one --graphic")
        mode = "graphic-only"
        notes.append("graphic-only mode is EXPERIMENTAL — inspect the result")
        if text_num is not None:
            notes.append("text-style ignored (graphic-only mode has no lettering)")
        if illus_num is not None:
            illus_folder = _resolve_style("illus", illus_num)
            illus_brief, n = _ensure_brief("illus", illus_folder)
            notes.append(f"illus-style brief: {n}")

    # ---- references ------------------------------------------------------ #
    if mode == "word+graphic":
        refs = (text_folder.refs if text_folder else []) + (illus_folder.refs if illus_folder else [])
    elif mode == "lettering-only":
        refs = text_folder.refs if text_folder else []
    else:  # graphic-only
        refs = illus_folder.refs if illus_folder else []
    styled = bool(refs)

    # ---- latin fix (text modes only) ------------------------------------ #
    latin_applied = False
    if mode != "graphic-only":
        if args.latin_fix == "on":
            latin_applied = True
        elif args.latin_fix == "auto":
            latin_applied = styles.needs_latin_fix(text)

    keep_outline = not args.no_outline

    # ---- build prompt ---------------------------------------------------- #
    if mode == "graphic-only":
        prompt = styles.graphic_only_prompt(
            graphics, illus_brief=illus_brief, keep_outline=keep_outline, styled=styled,
        )
    else:
        # lettering-only always means 0 graphics; otherwise honor the user's
        # --num-graphics (was parsed but ignored until 2026-07-05; None = derive
        # from the graphics description).
        num_graphics = 0 if (mode == "lettering-only") else args.num_graphics
        if styled:
            prompt = styles.styled_prompt(
                text, text_brief=text_brief, illus_brief=illus_brief,
                graphics=graphics, num_graphics=num_graphics,
                keep_outline=keep_outline, latin_fix=latin_applied,
            )
        else:
            prompt = styles.plain_prompt(
                text, style_desc=args.plain_style,
                graphics=graphics, num_graphics=num_graphics,
                keep_outline=keep_outline, latin_fix=latin_applied,
            )

    background = args.background
    routed_transparent = False
    if background == "transparent" and args.model.startswith("gemini"):
        # Gemini image models are RGB-only — they CANNOT emit alpha, and the
        # "Transparent background." prompt suffix is a silent no-op (user
        # decision 2026-07-09, verified against Google docs). Route through
        # the chroma path instead: generate on flat green, key locally.
        # gpt models keep their native transparent param.
        background = "chroma"
        routed_transparent = True
        notes.append("Gemini can't output alpha (RGB-only) — transparent "
                     "routed via chroma (flat green, keyed locally)")

    chroma = config.CHROMA_RGB if background == "chroma" else None
    opaque_bg_prompt = config.BLACK_PROMPT if background == "black" else None

    return {
        "out": out, "mode": mode, "text": text, "graphics": graphics,
        "text_folder": text_folder, "illus_folder": illus_folder,
        "prompt": prompt, "refs": refs, "latin_applied": latin_applied,
        "chroma": chroma, "opaque_bg_prompt": opaque_bg_prompt, "notes": notes,
        "model": args.model, "quality": args.quality, "size": args.size,
        # any of chroma / native transparent / Gemini-routed transparent must
        # yield a PNG with real alpha — checked after write, single AND batch
        "expect_alpha": background in ("chroma", "transparent"),
        "routed_transparent": routed_transparent,
    }


def _api_key_for(model: str) -> str:
    return config.GEMINI_API_KEY if model.startswith("gemini") else config.OPENAI_API_KEY


def cmd_generate(args: argparse.Namespace) -> None:
    from wordart_core import imagegen  # local import: pulls in the SDKs only when generating

    # validate the inputs FIRST: a bad flag must be reported as a bad flag, not
    # as a missing key, and neither costs anything.
    job = _build_job(args)

    is_gemini = args.model.startswith("gemini")
    config.require_keys(need_openai=not is_gemini, need_gemini=is_gemini)

    # ---- generate -------------------------------------------------------- #
    try:
        data = imagegen.generate_image(
            _api_key_for(args.model), job["prompt"], quality=args.quality, size=args.size,
            chroma=job["chroma"], opaque_bg_prompt=job["opaque_bg_prompt"],
            ref_images=job["refs"] or None, model=args.model,
            key_strength=args.key_strength, outline_px=args.outline_px,
        )
    except imagegen.ImageModerationError as e:
        print(f"MODERATION BLOCKED — reword. ({e})", file=sys.stderr)
        sys.exit(4)
    except imagegen.ImageGenError as e:
        print(f"IMAGE GENERATION FAILED: {e}", file=sys.stderr)
        sys.exit(5)

    out = job["out"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)

    # ---- keying / transparency check (same as batch, 2026-07-09) ---------- #
    keyfail = False
    if job["expect_alpha"]:
        try:
            keyfail = not _alpha_ok(data)
        except Exception:  # noqa: BLE001 — can't probe ⇒ don't claim "keyed"
            keyfail = True

    # ---- report ---------------------------------------------------------- #
    kb = len(data) / 1024
    bg = ("black (opaque)" if job["opaque_bg_prompt"]
          else "transparent→chroma→keyed" if job["routed_transparent"]
          else "chroma→keyed" if job["chroma"]
          else "transparent")
    if keyfail:
        bg += "  !! KEYING FAILED (opaque)"
    print("=== DONE ===")
    print(f"out:         {out}  ({args.size}, {kb:.0f} KB)")
    print(f"mode:        {job['mode']}")
    if job["mode"] != "graphic-only":
        print(f"text:        {job['text']!r}  (latin-fix: {'applied' if job['latin_applied'] else 'no'})")
    if job["text_folder"]:
        print(f"text-style:  {job['text_folder'].number}  {job['text_folder'].name!r}")
    if job["illus_folder"]:
        print(f"illus-style: {job['illus_folder'].number}  {job['illus_folder'].name!r}")
    print(f"graphics:    {len(job['graphics'])}  {job['graphics']}")
    print(f"model/qual:  {args.model} / {args.quality}    background: {bg}")
    stroke = (f"+{args.outline_px}px white border" if args.outline_px
              else "model-drawn outline only")
    print(f"key/outline: {args.key_strength}    {stroke}")
    print(f"refs sent:   {len(job['refs'])}")
    for n in job["notes"]:
        print(f"note:        {n}")
    print(f"prompt:      {job['prompt']}")
    if keyfail:
        print(f"!! KEYING FAILED — {out} has NO transparency (opaque); the model "
              f"likely ignored the flat green background. Regenerate (or key "
              f"manually) — don't ship it blind.", file=sys.stderr)
        sys.exit(7)


# --------------------------------------------------------------------------- #
# generate-batch
# --------------------------------------------------------------------------- #
MAX_PARALLEL = 20  # jobs (different words) in parallel; variations are a different knob

# jobs.json fields = the `generate` flags (hyphens or underscores both accepted)
_JOB_DEFAULTS = {
    "text": "", "text_style": None, "illus_style": None, "graphic": [],
    "num_graphics": None, "size": config.IMAGE_SIZE, "model": config.IMAGE_MODEL,
    "quality": "low", "background": "chroma", "no_outline": False,
    "latin_fix": "auto", "plain_style": config.DEFAULT_PLAIN_STYLE, "overwrite": False,
    "outline_px": 0, "key_strength": "normal",
}


def _job_namespace(raw: dict, idx: int) -> argparse.Namespace:
    """One jobs.json entry -> the same Namespace `generate` would produce.
    Unknown keys are flagged (typo protection), 'graphic' accepts str or list."""
    norm: dict = {}
    for k, v in raw.items():
        key = k.strip().lower().replace("-", "_")
        if key == "out":
            norm["out"] = v
            continue
        if key not in _JOB_DEFAULTS:
            raise JobFlag(f"job {idx}: unknown field {k!r} (known: out, "
                          f"{', '.join(sorted(_JOB_DEFAULTS))})")
        norm[key] = v
    if not norm.get("out"):
        raise JobFlag(f"job {idx}: missing required field 'out'")
    merged = {**_JOB_DEFAULTS, **norm}

    # ---- type validation (2026-07-09): wrong-typed jobs.json values become
    # collected FLAGs, not raw tracebacks — user still sees ALL problems, $0.
    def _bad(field: str, want: str) -> "NoReturn":  # type: ignore[name-defined]
        raise JobFlag(f"job {idx}: field {field!r} must be {want}, got "
                      f"{type(merged[field]).__name__}: {merged[field]!r}")

    if not isinstance(merged["out"], str):
        _bad("out", "a string (absolute .png path)")
    if merged["text"] is None:
        merged["text"] = ""  # JSON null ⇒ same as omitted (back-compat)
    for f in ("text", "size", "model", "quality", "background", "latin_fix",
              "plain_style", "key_strength"):
        if not isinstance(merged[f], str):
            _bad(f, "a string")
    op = merged["outline_px"]
    if isinstance(op, bool) or not isinstance(op, int) or op < 0:
        _bad("outline_px", "a non-negative integer (unquoted)")
    if merged["key_strength"] not in ("normal", "aggressive"):
        raise JobFlag(f"job {idx}: bad key_strength {merged['key_strength']!r} "
                      f"(normal|aggressive)")
    for f in ("no_outline", "overwrite"):
        if not isinstance(merged[f], bool):
            # NB a quoted "false" is truthy — flag, don't guess (flipped a
            # user's outline silently before this check existed)
            _bad(f, "a JSON boolean (true/false, unquoted)")
    ng = merged["num_graphics"]
    if ng is not None and (isinstance(ng, bool) or not isinstance(ng, int)):
        _bad("num_graphics", "an integer (unquoted) or null")
    g = merged.get("graphic") or []
    if isinstance(g, str):
        g = [g]
    if not isinstance(g, list) or not all(isinstance(x, str) for x in g):
        _bad("graphic", "a string or a list of strings")
    merged["graphic"] = g
    if merged["background"] not in ("chroma", "transparent", "black"):
        raise JobFlag(f"job {idx}: bad background {merged['background']!r}")
    if merged["model"] not in config.IMAGE_MODELS:
        raise JobFlag(f"job {idx}: unknown model {merged['model']!r} "
                      f"(known: {list(config.IMAGE_MODELS)})")
    if merged["quality"] not in config.QUALITIES:
        raise JobFlag(f"job {idx}: bad quality {merged['quality']!r}")
    if merged["size"] not in config.SIZES:
        raise JobFlag(f"job {idx}: bad size {merged['size']!r}")
    ts = merged["text_style"]
    ils = merged["illus_style"]
    merged["text_style"] = None if ts is None else str(ts)
    merged["illus_style"] = None if ils is None else str(ils)
    return argparse.Namespace(**merged)


def _alpha_ok(data: bytes) -> bool:
    """True if the PNG actually carries transparency (keying succeeded)."""
    import io

    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:
        if "A" not in im.getbands():
            return False
        a_min, _ = im.getchannel("A").getextrema()
        return a_min < 128


def cmd_generate_batch(args: argparse.Namespace) -> None:
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from wordart_core import imagegen

    jobs_path = Path(args.jobs)
    if not jobs_path.is_absolute():
        _die(f"--jobs must be an absolute path, got {args.jobs!r}")
    if not jobs_path.is_file():
        _die(f"--jobs not found: {jobs_path}")
    try:
        raw_jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _die(f"--jobs is not valid JSON: {e}")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        _die("--jobs must be a non-empty JSON list of job objects")
    if not all(isinstance(j, dict) for j in raw_jobs):
        _die("--jobs entries must all be JSON objects")

    parallel = max(1, min(args.parallel, MAX_PARALLEL, len(raw_jobs)))

    # ---- Phase A: validate EVERYTHING before any paid call ---------------- #
    flags: list[str] = []
    ns_jobs: list[argparse.Namespace | None] = []
    for i, raw in enumerate(raw_jobs):
        try:
            ns = _job_namespace(raw, i)
            ns_jobs.append(ns)
        except JobFlag as e:
            ns_jobs.append(None)
            flags.append(str(e))
            continue
        try:
            _build_job(ns)
        except JobFlag as e:
            flags.append(f"job {i}: {e}")
        except Exception as e:  # noqa: BLE001 — belt-and-braces: any crash on
            # user input must surface as a collected FLAG, never a traceback
            flags.append(f"job {i}: invalid input ({type(e).__name__}: {e})")
    # duplicate outputs WITHIN the batch would silently overwrite each other;
    # normcase+resolve so Windows' case-insensitive filesystem can't hide a
    # collision (CASE.png == case.png; also catches X\..\X\ forms)
    outs = [os.path.normcase(str(Path(ns.out).resolve()))
            for ns in ns_jobs if ns is not None]
    for dup in {o for o in outs if outs.count(o) > 1}:
        flags.append(f"duplicate out path across jobs: {dup}")
    if flags:
        for f in flags:
            print(f"FLAG: {f}", file=sys.stderr)
        print(f"FLAG: {len(flags)} problem(s) — nothing was generated, $0 spent.",
              file=sys.stderr)
        sys.exit(2)

    # keys: everything the batch will actually touch, checked up front
    models = {ns.model for ns in ns_jobs}
    config.require_keys(
        need_openai=any(not m.startswith("gemini") for m in models),
        need_gemini=any(m.startswith("gemini") for m in models),
    )

    # build the final jobs (no paid image call in here — collect any residual
    # flag and die cleanly rather than half-launching the batch)
    built = []
    for i, ns in enumerate(ns_jobs):
        try:
            built.append(_build_job(ns))
        except JobFlag as e:
            flags.append(f"job {i}: {e}")
        except Exception as e:  # noqa: BLE001 — same belt-and-braces as Phase A
            flags.append(f"job {i}: invalid input ({type(e).__name__}: {e})")
    if flags:
        for f in flags:
            print(f"FLAG: {f}", file=sys.stderr)
        print("FLAG: nothing was generated (brief-describe cost only).", file=sys.stderr)
        sys.exit(2)

    # ---- Phase B: generate, up to 20 jobs wide ----------------------------- #
    print(f"=== batch: {len(built)} job(s), {parallel} in parallel ===")
    t_batch = time.perf_counter()

    def _run(i: int) -> dict:
        ns, job = ns_jobs[i], built[i]
        row = {"i": i, "out": str(job["out"]), "text": job["text"], "model": ns.model}
        t0 = time.perf_counter()
        wrote = False
        try:
            data = imagegen.generate_image(
                _api_key_for(ns.model), job["prompt"], quality=ns.quality, size=ns.size,
                chroma=job["chroma"], opaque_bg_prompt=job["opaque_bg_prompt"],
                ref_images=job["refs"] or None, model=ns.model,
                key_strength=ns.key_strength, outline_px=ns.outline_px,
            )
            job["out"].parent.mkdir(parents=True, exist_ok=True)
            job["out"].write_bytes(data)
            wrote = True
            row["ok"] = True
            row["kb"] = round(len(data) / 1024)
            if job["expect_alpha"] and not _alpha_ok(data):
                row["keying_failed"] = True   # LOUD: opaque image kept, must not slip through
        except imagegen.ImageModerationError as e:
            row["ok"] = False
            row["error"] = f"MODERATION BLOCKED — reword. ({e})"
        except Exception as e:  # noqa: BLE001
            row["ok"] = False
            row["error"] = f"{type(e).__name__}: {e}"
            if wrote:
                # the PNG landed before the failure (e.g. the alpha probe choked
                # on corrupt bytes) — remove it so the failed.json rerun isn't
                # blocked by its own "--out already exists" flag
                job["out"].unlink(missing_ok=True)
        row["seconds"] = round(time.perf_counter() - t0, 1)
        return row

    def _print_row(r: dict) -> None:
        if r.get("ok") and r.get("keying_failed"):
            print(f"  [{r['i']:02d} !! KEYING FAILED] {r['seconds']}s  {r['out']}  "
                  f"(image is OPAQUE — model likely ignored the green background; "
                  f"regenerate or key manually)", file=sys.stderr)
        elif r.get("ok"):
            print(f"  [{r['i']:02d} done] {r['seconds']}s  {r['out']}")
        else:
            print(f"  [{r['i']:02d} FAIL] {r['seconds']}s  {r['text']!r}: {r['error']}",
                  file=sys.stderr)

    rows: list[dict] = []
    interrupted = False
    ex = ThreadPoolExecutor(max_workers=parallel)
    futs = [ex.submit(_run, i) for i in range(len(built))]
    try:
        for fut in as_completed(futs):
            r = fut.result()
            rows.append(r)
            _print_row(r)
    except KeyboardInterrupt:
        # Ctrl-C (2026-07-09): cancel every queued job NOW — no further paid
        # call may fire — let in-flight ones finish, and STILL fall through to
        # Phase C so the summary + failed.json get written (cancelled jobs are
        # marked and land in failed.json for a rerun).
        interrupted = True
        ex.shutdown(wait=False, cancel_futures=True)
        done_is = {r["i"] for r in rows}
        pending = [(i, f) for i, f in enumerate(futs) if i not in done_is]
        n_cancelled = sum(1 for _, f in pending if f.cancelled())
        print(f"\n!! interrupted — cancelled {n_cancelled} queued job(s), waiting "
              f"for {len(pending) - n_cancelled} in flight (Ctrl-C again to stop "
              f"waiting) …", file=sys.stderr)
        abandoned = False
        for i, f in pending:
            row = {"i": i, "out": str(built[i]["out"]), "text": built[i]["text"],
                   "model": ns_jobs[i].model, "ok": False, "seconds": 0.0}
            if f.cancelled():
                row["error"] = "interrupted — cancelled before start (no API call made)"
            elif abandoned:
                row["error"] = "interrupted — in flight, result not collected"
            else:
                try:
                    row = f.result()  # in flight: let it finish, keep its real row
                except KeyboardInterrupt:
                    abandoned = True
                    row["error"] = "interrupted — in flight, result not collected"
                except Exception as e:  # noqa: BLE001 — _run catches everything;
                    # this is unreachable belt-and-braces
                    row["error"] = f"{type(e).__name__}: {e}"
            rows.append(row)
            _print_row(row)
    finally:
        ex.shutdown(wait=False)

    # ---- Phase C: summary + rerun file for the failures -------------------- #
    rows.sort(key=lambda r: r["i"])
    ok = [r for r in rows if r.get("ok")]
    bad = [r for r in rows if not r.get("ok")]
    keyfail = [r for r in rows if r.get("keying_failed")]
    print("=== BATCH INTERRUPTED (Ctrl-C) ===" if interrupted else "=== BATCH DONE ===")
    print(f"ok: {len(ok)}/{len(rows)}   wall: {time.perf_counter()-t_batch:.1f}s")
    if keyfail:
        print(f"KEYING FAILED on {len(keyfail)} image(s) — they are OPAQUE, inspect before use: ")
        for r in keyfail:
            print(f"  - {r['out']}")
    if bad or keyfail:
        failed_path = jobs_path.with_suffix(".failed.json")
        # keying-failed jobs are rerunnable too — their opaque PNG is on disk,
        # so the rerun row needs overwrite:true to pass its own exists-check
        rerun = ([raw_jobs[r["i"]] for r in bad]
                 + [{**raw_jobs[r["i"]], "overwrite": True} for r in keyfail])
        failed_path.write_text(
            json.dumps(rerun, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"failed: {len(bad)}   keying-failed: {len(keyfail)} — rerun just those with:",
              file=sys.stderr)
        print(f'  python run_cli.py generate-batch --jobs "{failed_path}"', file=sys.stderr)
    if bad:
        sys.exit(6)       # hard failures (incl. interrupted/cancelled jobs)
    if keyfail:
        sys.exit(7)       # every job "succeeded" but N outputs are opaque
    if interrupted:
        sys.exit(130)     # Ctrl-C after all rows finished — still non-zero


# --------------------------------------------------------------------------- #
# rescan
# --------------------------------------------------------------------------- #
def cmd_rescan(args: argparse.Namespace) -> None:
    cats = ["text", "illus"] if args.category == "all" else [args.category]
    report: dict[str, list] = {}
    for ck in cats:
        rows = []
        for f in styles.list_folders(CAT[ck]):
            rows.append({
                "number": f.number,
                "name": f.name,
                "images": len(f.images),
                "brief": _brief_status(f),
                "summary": _style_summary(f),
            })
        report[ck] = rows

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    for ck in cats:
        label = CAT[ck]
        print(f"{label}:")
        if not report[ck]:
            print("  (no style folders with images)")
        for r in report[ck]:
            num = "?" if r["number"] is None else str(r["number"])
            print(f"  {num:<3} {r['name']}")
            if r["summary"]:
                print(f"      {r['summary']}")
            if r["brief"] == "MISSING":
                print(f"      !! no _style_brief.txt — reinstall the plugin")
        print()
    print("Pick a style by its NUMBER. Open styles.html to see the reference art.")


# --------------------------------------------------------------------------- #
# restroke — post-process an existing PNG (no model call, $0)
# --------------------------------------------------------------------------- #
def cmd_restroke(args: argparse.Namespace) -> None:
    """Re-key and/or thicken the sticker border on a PNG that already exists.

    Outline width and key aggressiveness are pure post-processing, so tuning them
    must never cost another image. Re-keying works on an already-keyed file too:
    keying only zeroes the ALPHA, the green is still sitting in the RGB channels.
    """
    from wordart_core import bgremove

    src, out = Path(args.src), Path(args.out)
    for label, p in (("--in", src), ("--out", out)):
        if not p.is_absolute():
            _die(f"{label} must be an absolute path, got {p}")
        if p.suffix.lower() != ".png":
            _die(f"{label} must be a .png, got {p.name}")
    if not src.is_file():
        _die(f"--in not found: {src}")
    if out.exists() and not args.overwrite:
        _die(f"--out exists (use --overwrite): {out}")
    if args.key_strength is None and args.outline_px <= 0:
        _die("nothing to do — pass --key-strength and/or --outline-px")

    data = src.read_bytes()

    # Re-keying a png that has NO CHROMA LEFT silently destroys it: remove_chroma
    # drops the incoming alpha and rebuilds the matte from colour, so with no green
    # to find it keys off the wrong signal. Measured on the mascot set: all 138,708
    # white-border pixels gone, exit code 0, no warning.
    # NB the test is residual green, NOT "has alpha" — a `generate` output is keyed
    # AND still green in RGB (keying only zeroes ALPHA), so it re-keys just fine.
    # Only add_outline zeroes the RGB. Measured separation: 0.71 vs 0.0000.
    if args.key_strength and not args.force_rekey:
        import numpy as _np
        from PIL import Image as _Im
        import io as _io
        with _Im.open(_io.BytesIO(data)) as _im:
            _rgb = _np.asarray(_im.convert("RGB")).astype(int)
        _greenish = ((_rgb[..., 1] - _np.maximum(_rgb[..., 0], _rgb[..., 2])) > 60).mean()
        if _greenish < 0.01:
            _die(f"--in has no green left to key ({src.name}: {_greenish:.4f} green-dominant) "
                 f"— re-keying would rebuild the matte from the wrong signal and eat the white "
                 f"border. Re-key the ORIGINAL generate output instead (outline-only restroke "
                 f"needs no --key-strength), or pass --force-rekey if you really mean it.")

    steps = []
    if args.key_strength:
        data = bgremove.remove_chroma(data, config.CHROMA_RGB, strength=args.key_strength)
        steps.append(f"re-keyed ({args.key_strength})")
    if args.outline_px > 0:
        data = bgremove.add_outline(data, args.outline_px)
        steps.append(f"+{args.outline_px}px white border")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)

    keyfail = not _alpha_ok(data)
    print("=== RESTROKED ===")
    print(f"in:          {src}")
    print(f"out:         {out}  ({len(data) / 1024:.0f} KB)")
    print(f"applied:     {', '.join(steps)}")
    if keyfail:
        print(f"!! NO TRANSPARENCY in {out} — the source had no green left to key "
              f"(already flattened?). Don't ship it blind.", file=sys.stderr)
        sys.exit(7)


# --------------------------------------------------------------------------- #
# argument parsing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_cli.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate one PNG")
    g.add_argument("--out", required=True, help="absolute output .png path")
    g.add_argument("--text", default="", help="the word/phrase; empty ⇒ graphic-only mode")
    g.add_argument("--text-style", default=None, help="text style NUMBER or 'none' (default none)")
    g.add_argument("--illus-style", default=None, help="illustration style NUMBER or 'none' (default none)")
    g.add_argument("--graphic", action="append", default=[],
                   help="supporting-graphic object description (repeatable); absent ⇒ no graphic")
    g.add_argument("--num-graphics", type=int, default=None, dest="num_graphics",
                   help="override the supporting-graphic count")
    g.add_argument("--size", default=config.IMAGE_SIZE, choices=config.SIZES)
    g.add_argument("--model", default=config.IMAGE_MODEL, choices=config.IMAGE_MODELS)
    g.add_argument("--quality", default="low", choices=config.QUALITIES)
    g.add_argument("--background", default="chroma", choices=("chroma", "transparent", "black"))
    g.add_argument("--no-outline", action="store_true", help="drop the white sticker outline")
    g.add_argument("--outline-px", type=int, default=0, dest="outline_px",
                   help="grow a deterministic white sticker border N px wide after "
                        "keying (0 = only the thin one the model drew)")
    g.add_argument("--key-strength", default="normal", dest="key_strength",
                   choices=("normal", "aggressive"),
                   help="green-removal aggressiveness (aggressive = wider colour "
                        "match + wider despill + 1px matte choke)")
    g.add_argument("--latin-fix", default="auto", choices=("auto", "on", "off"),
                   help="add the Latin+()+English instruction (auto = detect non-Latin script)")
    g.add_argument("--plain-style", default=config.DEFAULT_PLAIN_STYLE,
                   help="base art style for no-reference runs")
    g.add_argument("--overwrite", action="store_true", help="replace an existing --out")
    g.set_defaults(func=cmd_generate)

    b = sub.add_parser(
        "generate-batch",
        help="generate a whole word list from a jobs.json, up to 20 jobs in parallel",
    )
    b.add_argument("--jobs", required=True,
                   help="absolute path to a JSON list of job objects; fields = the "
                        "`generate` flags (out is required; hyphens/underscores both fine; "
                        "graphic may be a string or a list)")
    b.add_argument("--parallel", type=int, default=MAX_PARALLEL,
                   help=f"max concurrent jobs (capped at {MAX_PARALLEL})")
    b.set_defaults(func=cmd_generate_batch)

    s = sub.add_parser(
        "restroke",
        help="re-key / re-outline an EXISTING png — no model call, $0",
    )
    s.add_argument("--in", dest="src", required=True, help="absolute source .png path")
    s.add_argument("--out", required=True, help="absolute output .png path")
    s.add_argument("--outline-px", type=int, default=0, dest="outline_px",
                   help="white sticker border width in px (0 = leave as-is)")
    s.add_argument("--key-strength", default=None, dest="key_strength",
                   choices=("normal", "aggressive"),
                   help="re-key the green background at this strength; omit to keep "
                        "the existing alpha (required if the source is still opaque)")
    s.add_argument("--force-rekey", action="store_true", dest="force_rekey",
                   help="allow --key-strength on a source that already has alpha "
                        "(it will eat the white border — you almost never want this)")
    s.add_argument("--overwrite", action="store_true", help="replace an existing --out")
    s.set_defaults(func=cmd_restroke)

    r = sub.add_parser("rescan", help="list styles by number + brief status")
    r.add_argument("--category", default="all", choices=("text", "illus", "all"))
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_rescan)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except JobFlag as e:
        _die(str(e), e.code)
    except RuntimeError as e:
        # require_keys() and friends: a setup problem, not a bug. Show the fix,
        # not a traceback -- this is the first thing a new user hits.
        _die(str(e), 2)


if __name__ == "__main__":
    main()
