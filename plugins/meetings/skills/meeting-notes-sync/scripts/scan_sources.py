#!/usr/bin/env python3
"""Find Google Meet artifacts that haven't been synced to ClickUp yet.

Read-only. Scans both personal Meet folders ("Meet Recordings" and the newer
"Google Meet") and every Shared Drive "Meeting Notes & Recordings" folder,
recursing into subfolders, then groups artifacts into meeting sets and returns
the ones not already recorded in the state file.

Folders are discovered by name at run time rather than by hardcoded ID. The
same IDs living in two files is how folder routing silently drifts, and
a deleted-and-recreated folder changes its ID without telling anyone.

Usage:
    python scan_sources.py                    # new meetings since last run
    python scan_sources.py --since 2026-08-01 # override the state file
    python scan_sources.py --dry-run          # don't read or write state
    python scan_sources.py --json             # machine-readable output
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "processed.json"

# Google renamed/restructured where Meet artifacts land (~2026-07-29 on this
# account). Scan both: the old folder still holds history, and accounts
# mid-rollout can write to either.
PERSONAL_FOLDERS = ["Meet Recordings", "Google Meet"]
SHARED_FOLDER = "Meeting Notes & Recordings"

# "<Title> - <YYYY/MM/DD HH:MM TZ> - <Kind>"
ARTIFACT_RE = re.compile(
    r"^(?P<title>.+?)\s+-\s+"
    r"(?P<date>\d{4}/\d{2}/\d{2})\s+(?P<time>\d{2}:\d{2})\s+(?P<tz>\S+)"
    r"\s+-\s+(?P<kind>Notes by Gemini|Transcript|Recording(?:\s+\d+)?)$"
)

KIND_PRIORITY = {"Notes by Gemini": 0, "Transcript": 1, "Recording": 2}


def gws(args, params):
    """Call the gws CLI and return parsed JSON."""
    cmd = ["gws"] + args + ["--params", json.dumps(params)]
    # Force UTF-8. Without it Python decodes with the locale codec, which is
    # cp1252 on Windows and throws on any non-ASCII name in a calendar event
    # or filename -- Thai and accented names are routine on this team.
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"gws {' '.join(args)} failed (exit {proc.returncode}):\n"
            f"{(proc.stderr or '').strip()}"
        )
    out = proc.stdout or ""
    start = out.find("{")
    if start == -1:
        raise RuntimeError(f"gws {' '.join(args)} returned no JSON:\n{out.strip()}")
    return json.loads(out[start:])


def q(value):
    """Escape a value for a Drive query string literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def walk_folders(root_id, label, depth=0, max_depth=3):
    """Yield (folder_id, label) for a folder and everything under it.

    Recursion is not optional. Google's newer "Google Meet" folder groups
    artifacts into a subfolder per meeting -- "<Title> (recurring)/" for a
    series, "<Title> - <timestamp>/" for a one-off -- so a flat listing of the
    root returns only folders and zero files.
    """
    out = [(root_id, label)]
    if depth >= max_depth:
        return out
    for sub in list_children(root_id, folders_only=True):
        out.extend(walk_folders(sub["id"], f"{label}/{sub['name']}", depth + 1, max_depth))
    return out


def find_folders():
    """Locate every folder to scan. Returns [(folder_id, label)]."""
    folders = []

    # Both personal folders, always. Google moved Meet output from
    # "Meet Recordings" to "Google Meet" around 2026-07-29 on this account, and
    # the two overlapped for several days rather than cutting over cleanly.
    # The old folder is frozen, not deleted, so keep reading both -- and a
    # teammate mid-rollout may still be writing to either.
    for name in PERSONAL_FOLDERS:
        found = gws(
            ["drive", "files", "list"],
            {
                "q": f"name = '{q(name)}' and mimeType = 'application/vnd.google-apps.folder' "
                     f"and trashed = false and 'root' in parents",
                "fields": "files(id,name)",
            },
        ).get("files", [])
        for f in found:
            folders.extend(walk_folders(f["id"], f"My Drive/{f['name']}"))

    shared = gws(
        ["drive", "files", "list"],
        {
            "q": f"name = '{q(SHARED_FOLDER)}' and mimeType = 'application/vnd.google-apps.folder' "
                 f"and trashed = false",
            "corpora": "allDrives",
            "includeItemsFromAllDrives": True,
            "supportsAllDrives": True,
            "fields": "files(id,name,driveId)",
            "pageSize": 100,
        },
    ).get("files", [])

    for f in shared:
        folders.extend(walk_folders(f["id"], f.get("driveId", "shared")))

    # A folder reachable by two paths would otherwise be scanned twice.
    seen, unique = set(), []
    for fid, label in folders:
        if fid not in seen:
            seen.add(fid)
            unique.append((fid, label))
    return unique


def list_children(folder_id, folders_only=False):
    mime = " and mimeType = 'application/vnd.google-apps.folder'" if folders_only else ""
    params = {
        "q": f"'{q(folder_id)}' in parents and trashed = false{mime}",
        "includeItemsFromAllDrives": True,
        "supportsAllDrives": True,
        "fields": "nextPageToken, files(id,name,mimeType,createdTime,webViewLink)",
        "pageSize": 200,
    }
    files, cursor = [], None
    while True:
        if cursor:
            params["pageToken"] = cursor
        page = gws(["drive", "files", "list"], params)
        files.extend(page.get("files", []))
        cursor = page.get("nextPageToken")
        if not cursor:
            break
    return files


def normalize_title(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# --- Renamed-artifact recovery ---------------------------------------------
# A Gemini notes doc that someone renamed loses the timestamp in its filename.
# Recover it, but only when we can be genuinely confident, because the fallback
# is writing meeting notes onto the wrong page unattended.
#
# NOT used: dates found in the document body. Gemini notes contain no meeting
# date. The only date-like strings are incidental references inside the
# discussion ("budget was scaled on August 12", "campaign launched April 14").
# Tested on a real notes doc, that heuristic returned a date six days off --
# a real date, matching a real page, for a different meeting.
#
# Used instead: Drive createdTime (preserved through a rename; Gemini writes
# within hours of the meeting) confirmed against a single calendar event.

GEMINI_DISCLAIMER = "review gemini's notes"
GEMINI_HEADINGS = {"summary", "decisions", "next steps", "details", "invited"}


def fetch_doc_lines(file_id):
    """Return the document's non-empty text lines, or None if unreadable."""
    try:
        doc = gws(["docs", "documents", "get"], {"documentId": file_id})
    except RuntimeError:
        return None

    def walk(elements):
        out = []
        for e in elements:
            if "paragraph" in e:
                text = "".join(
                    r.get("textRun", {}).get("content", "")
                    for r in e["paragraph"].get("elements", [])
                )
                if text.strip():
                    out.append(text.strip())
            if "table" in e:
                for row in e["table"].get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        out.extend(walk(cell.get("content", [])))
        return out

    return walk(doc.get("body", {}).get("content", []))


def is_gemini_doc(lines):
    """Is this actually a Meet/Gemini notes artifact, or just a human doc?

    This gate is the whole point. The unmatched files in this workspace are
    human-authored prep docs -- an empty "Attendees / Notes / Action items"
    template, and interview scripts full of unanswered questions. Neither is a
    meeting record, and neither should ever be synced.
    """
    if not lines:
        return False
    blob = " ".join(lines).lower()
    if GEMINI_DISCLAIMER in blob:
        return True  # Gemini stamps this on every notes doc it writes
    # Fall back to structure: Gemini's canonical section headings.
    found = {h for h in GEMINI_HEADINGS if any(l.strip().lower() == h for l in lines)}
    return len(found) >= 3


def infer_renamed(f, events):
    """Recover the meeting for a renamed Gemini doc. (meeting_dict, reason)."""
    if f.get("mimeType") != "application/vnd.google-apps.document":
        return None, "not-a-doc"

    lines = fetch_doc_lines(f["id"])
    if lines is None:
        return None, "unreadable"
    if not is_gemini_doc(lines):
        # Human-authored doc that happens to live in a meetings folder.
        return None, "not-a-meeting-artifact"

    created = datetime.fromisoformat(f["createdTime"].replace("Z", "+00:00"))
    # Gemini writes the doc after the meeting ends: event start precedes
    # createdTime by roughly one meeting length plus processing lag.
    window = [
        e for e in events
        if timedelta(minutes=-30) <= (created - e["start"]) <= timedelta(hours=6)
    ]
    if not window:
        return None, "no-calendar-event"

    norm = normalize_title(f["name"])
    titled = [e for e in window if titles_match(norm, e["norm"])]

    if len(titled) == 1:
        event = titled[0]
    elif not titled and len(window) == 1:
        # Renamed beyond recognition, but exactly one meeting could have
        # produced it. Still unambiguous.
        event = window[0]
    else:
        return None, "ambiguous-event"

    if not event["is_self"]:
        return None, "not-organizer"

    return {
        "title": event["summary"],
        "date": event["start"].strftime("%Y-%m-%d"),
        "time": event["start"].strftime("%H:%M"),
        "timezone": "GMT+00:00",
        "location": f.get("_location", "unknown"),
        "artifacts": [{
            "id": f["id"],
            "name": f["name"],
            "title": event["summary"],
            "kind": "Notes by Gemini",
            "url": f.get("webViewLink"),
            "created": f.get("createdTime"),
        }],
        "inferred_from_rename": True,
        "original_filename": f["name"],
        "event_match": "inferred",
        "organizer": event["organizer"],
        "event_id": event["event_id"],
    }, "inferred"


def artifact_utc(meeting_date, meeting_time, tz):
    """Convert a Meet filename timestamp to UTC.

    Filenames carry an explicit offset ("GMT+07:00", "GMT+05:45"), so this is
    exact rather than a guess about whose timezone the name was written in.
    """
    m = re.match(r"^GMT([+-])(\d{2}):(\d{2})$", tz)
    if not m:
        return None
    sign = 1 if m.group(1) == "+" else -1
    offset = timedelta(hours=int(m.group(2)), minutes=int(m.group(3))) * sign
    naive = datetime.fromisoformat(f"{meeting_date}T{meeting_time}:00")
    return naive.replace(tzinfo=timezone(offset)).astimezone(timezone.utc)


def fetch_events(start, end):
    """Pull the authenticated user's calendar events across the scan window.

    One call for the whole window, not one per meeting.
    """
    params = {
        "calendarId": "primary",
        "timeMin": start.isoformat().replace("+00:00", "Z"),
        "timeMax": end.isoformat().replace("+00:00", "Z"),
        "singleEvents": True,
        "orderBy": "startTime",
        "fields": "nextPageToken, items(id,summary,start(dateTime,date),"
                  "organizer(email,self),creator(email,self))",
        "maxResults": 250,
    }
    events, cursor = [], None
    while True:
        if cursor:
            params["pageToken"] = cursor
        page = gws(["calendar", "events", "list"], params)
        events.extend(page.get("items", []))
        cursor = page.get("nextPageToken")
        if not cursor:
            break

    out = []
    for e in events:
        dt = (e.get("start") or {}).get("dateTime")
        if not dt:
            continue  # all-day entries are never Meet meetings
        out.append({
            # Identical for every attendee, unlike a Drive file id, so it is
            # the only key that dedupes a sync across different people.
            "event_id": e.get("id"),
            "summary": e.get("summary", ""),
            "norm": normalize_title(e.get("summary", "")),
            "start": datetime.fromisoformat(dt).astimezone(timezone.utc),
            "organizer": (e.get("organizer") or {}).get("email"),
            # Google sets `self` only when it's you. Absent means someone else.
            # Keying on this rather than a configured email keeps the skill
            # portable to every teammate with no per-user setup.
            "is_self": bool((e.get("organizer") or {}).get("self")),
        })
    return out


def titles_match(a, b):
    if a == b:
        return True
    short, long = sorted([a, b], key=len)
    # Containment alone is too loose ("Ads Review" would swallow anything).
    # Require the shorter title to be most of the longer one.
    return short in long and len(short) >= 0.6 * len(long)


def match_event(meeting, events):
    """Find the calendar event for a meeting. Returns (event, reason)."""
    norm = normalize_title(meeting["title"])
    when = artifact_utc(meeting["date"], meeting["time"], meeting["timezone"])

    if when is None:
        # Meet usually writes an explicit offset ("GMT+07:00") but sometimes an
        # abbreviation ("PST"). Abbreviations are ambiguous -- PST is -08:00 in
        # the US and +08:00 in the Philippines -- so don't invent an offset.
        # Fall back to the calendar date, which is the same under either
        # reading, and demand a unique title match to stay confident.
        day = datetime.fromisoformat(meeting["date"]).date()
        near_day = [
            e for e in events
            if abs((e["start"].date() - day).days) <= 1
            and titles_match(norm, e["norm"])
        ]
        if len(near_day) == 1:
            return near_day[0], "matched-by-date"
        return None, "ambiguous-timezone"
    near = [e for e in events if abs((e["start"] - when).total_seconds()) <= 4 * 3600]
    candidates = [e for e in near if titles_match(norm, e["norm"])]

    if not candidates:
        # Fall back to time alone — Meet occasionally names an artifact from a
        # renamed event. Only trust it when exactly one event is that close.
        tight = [e for e in near if abs((e["start"] - when).total_seconds()) <= 900]
        if len(tight) == 1:
            return tight[0], "matched-by-time"
        return None, "no-calendar-event"

    if len(candidates) > 1:
        organizers = {e["is_self"] for e in candidates}
        if len(organizers) > 1:
            # Two events, disagreeing on whether you organized. Fail closed.
            return None, "ambiguous-event"
        candidates.sort(key=lambda e: abs((e["start"] - when).total_seconds()))

    return candidates[0], "matched"


def parse_artifact(f, location):
    m = ARTIFACT_RE.match(f["name"])
    if not m:
        return None
    kind = m.group("kind")
    return {
        "id": f["id"],
        "name": f["name"],
        "title": m.group("title").strip(),
        # Meeting time from the FILENAME, not Drive createdTime — Gemini writes
        # the doc after the meeting, which can roll past midnight.
        "meeting_date": m.group("date").replace("/", "-"),
        "meeting_time": m.group("time"),
        "timezone": m.group("tz"),
        "kind": kind.split()[0] if kind.startswith("Recording") else kind,
        "location": location,
        "url": f.get("webViewLink"),
        "created": f.get("createdTime"),
    }


# How far back to look beyond `last_run`. See compute_cutoff.
LOOKBACK = timedelta(days=3)


def _aware(dt):
    """Treat a naive timestamp as UTC so it can be compared with Drive times."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def compute_cutoff(since, last_run, use_all, now=None, lookback=LOOKBACK):
    """Earliest Drive createdTime worth scanning.

    `last_run` is a PERFORMANCE bound, not the dedup mechanism -- dedup is the
    `processed` map. Used as a hard floor it silently loses work: an artifact
    created before `last_run` but never processed (a failed run, an interrupted
    run, or a skip reason that no longer applies) gets filtered out on every
    subsequent run and nothing else catches it, because it never entered
    `processed`.

    Subtracting a lookback buffer means those reappear. Re-seeing an already
    processed artifact is free -- `processed` filters it -- so the buffer costs
    a little scanning and removes a silent one-way data loss.
    """
    now = now or datetime.now(timezone.utc)
    if since:
        return _aware(datetime.fromisoformat(since))
    if last_run and not use_all:
        return _aware(datetime.fromisoformat(last_run)) - lookback
    return now - timedelta(days=14)


def load_state():
    if not STATE_PATH.exists():
        return {"last_run": None, "processed": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        # A corrupt state file must not silently re-sync everything.
        print(f"WARNING: state file unreadable ({e}). Treating as empty; the "
              f"marker-block check in ClickUp is the remaining safety net.",
              file=sys.stderr)
        return {"last_run": None, "processed": {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="ISO date; overrides state file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="ignore state entirely")
    ap.add_argument("--include-all-organizers", action="store_true",
                    help="DEBUG ONLY. Skip the organizer filter. Never use for "
                         "an unattended run - it lets several teammates write "
                         "the same page.")
    args = ap.parse_args()

    state = load_state()
    processed = set() if args.all else set(state.get("processed", {}))

    cutoff = compute_cutoff(args.since, state.get("last_run"), args.all)

    try:
        folders = find_folders()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not folders:
        print("ERROR: found no folders to scan. Is gws authenticated?", file=sys.stderr)
        return 1

    meetings, skipped, rename_candidates = {}, [], []
    for folder_id, label in folders:
        try:
            children = list_children(folder_id)
        except RuntimeError as e:
            print(f"ERROR scanning {label}: {e}", file=sys.stderr)
            continue
        for f in children:
            art = parse_artifact(f, label)
            if art is None:
                if f["mimeType"] != "application/vnd.google-apps.folder":
                    if f["id"] not in processed:
                        created = datetime.fromisoformat(
                            f["createdTime"].replace("Z", "+00:00"))
                        if created >= cutoff:
                            f["_location"] = label
                            rename_candidates.append(f)
                    skipped.append({"name": f["name"], "location": label})
                continue
            if art["id"] in processed:
                continue
            created = datetime.fromisoformat(f["createdTime"].replace("Z", "+00:00"))
            if created < cutoff:
                continue
            key = f"{art['title']}|{art['meeting_date']}|{art['meeting_time']}"
            meetings.setdefault(key, {
                "title": art["title"],
                "date": art["meeting_date"],
                "time": art["meeting_time"],
                "timezone": art["timezone"],
                "location": art["location"],
                "artifacts": [],
            })["artifacts"].append(art)

    for m in meetings.values():
        m["artifacts"].sort(key=lambda a: KIND_PRIORITY.get(a["kind"], 9))
        m["primary"] = m["artifacts"][0]
        m["has_gemini_notes"] = any(a["kind"] == "Notes by Gemini" for a in m["artifacts"])

    # Organizer filter. Only the person who organized a meeting syncs it —
    # otherwise every attendee with this skill installed races to write the
    # same ClickUp page. Fails closed: anything we can't positively attribute
    # to you is skipped, never synced "just in case".
    mine, not_mine = [], []
    rename_outcomes = {}
    if meetings:
        window_start = min(
            artifact_utc(m["date"], m["time"], m["timezone"]) or cutoff
            for m in meetings.values()
        ) - timedelta(days=1)
        window_end = max(
            artifact_utc(m["date"], m["time"], m["timezone"]) or cutoff
            for m in meetings.values()
        ) + timedelta(days=1)
        try:
            events = fetch_events(window_start, window_end)
        except RuntimeError as e:
            print(f"ERROR: could not read calendar, so organizer cannot be "
                  f"confirmed. Refusing to sync anything.\n{e}", file=sys.stderr)
            return 1

        # Recover renamed Gemini artifacts. Runs automatically -- a confident
        # recovery needs no permission, and an unconfident one is dropped
        # rather than surfaced as a question.
        for f in rename_candidates:
            recovered, reason = infer_renamed(f, events)
            if recovered:
                key = f"{recovered['title']}|{recovered['date']}|{recovered['time']}"
                if key not in meetings:
                    recovered["has_gemini_notes"] = True
                    recovered["primary"] = recovered["artifacts"][0]
                    meetings[key] = recovered
                    skipped[:] = [x for x in skipped if x["name"] != f["name"]]
            else:
                rename_outcomes.setdefault(reason, []).append(f["name"])

        for m in sorted(meetings.values(), key=lambda m: (m["date"], m["time"], m["title"])):
            if m.get("inferred_from_rename"):
                # Already attributed via the calendar event it was recovered from.
                m["skip_reason"] = None
                mine.append(m)
                continue
            event, reason = match_event(m, events)
            m["event_match"] = reason
            m["organizer"] = event["organizer"] if event else None
            m["event_id"] = event["event_id"] if event else None
            if args.include_all_organizers:
                m["skip_reason"] = None
                mine.append(m)
            elif event and event["is_self"]:
                m["skip_reason"] = None
                mine.append(m)
            else:
                m["skip_reason"] = "not-organizer" if event else reason
                not_mine.append(m)

    result = {
        "scanned_folders": len(folders),
        "cutoff": cutoff.isoformat(),
        "organizer_filter": not args.include_all_organizers,
        "meetings": mine,
        "skipped_meetings": not_mine,
        "unrecognised_files": skipped,
        "rename_recovery": rename_outcomes,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Scanned {len(folders)} folders since {cutoff.date()}")
        if args.include_all_organizers:
            print("WARNING: organizer filter DISABLED (--include-all-organizers)")
        print(f"Found {len(result['meetings'])} meeting(s) you organized\n")
        for m in result["meetings"]:
            kinds = ", ".join(a["kind"] for a in m["artifacts"])
            flag = "" if m["has_gemini_notes"] else "   [no Gemini notes]"
            print(f"  {m['date']} {m['time']}  {m['title']}")
            print(f"             {m['location']} | {kinds}{flag}")

        recovered = [m for m in result["meetings"] if m.get("inferred_from_rename")]
        if recovered:
            print(f"\n  ({len(recovered)} recovered from renamed files)")
        if rename_outcomes:
            print("\nRenamed/unmatched files examined:")
            for reason, names in sorted(rename_outcomes.items()):
                print(f"  {reason}: {len(names)}")
                for n in names[:3]:
                    print(f"    - {n}")
                if len(names) > 3:
                    print(f"    ... and {len(names) - 3} more")

        if not_mine:
            by_reason = {}
            for m in not_mine:
                by_reason.setdefault(m["skip_reason"], []).append(m)
            print(f"\nSkipped {len(not_mine)} meeting(s) you did not organize:")
            for reason, items in sorted(by_reason.items()):
                print(f"  {reason}: {len(items)}")
                for m in items[:3]:
                    who = m["organizer"] or "unknown organizer"
                    print(f"    - {m['date']} {m['title']}  ({who})")
                if len(items) > 3:
                    print(f"    ... and {len(items) - 3} more")
        if skipped:
            print(f"\n{len(skipped)} file(s) did not match the Meet naming pattern:")
            for s in skipped[:10]:
                print(f"  - {s['name']}  ({s['location']})")
            if len(skipped) > 10:
                print(f"  ... and {len(skipped) - 10} more")

    if not args.dry_run and not args.json:
        print("\nState not updated — the skill records meetings as processed only "
              "after each ClickUp write is verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
