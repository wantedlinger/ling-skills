---
name: meeting-notes-sync
description: "Sync completed Google Meet meetings into their ClickUp meeting-notes page — append the decisions and any action items not already recorded there, as checkboxes with each owner named. Reads Gemini notes (and transcripts when present) from personal My Drive and every Shared Drive, matches each meeting to its ClickUp notes page, and flags meetings that have notes in Drive but no ClickUp page. Use when someone says 'sync my meeting notes', 'update ClickUp from my meetings', 'did yesterday's meetings get written up', 'process new meeting notes', or when the daily scheduled run fires. Only syncs meetings you personally organized, so several teammates can run it without racing to write the same page. Never creates ClickUp pages and never writes to a page a human didn't already place."
---

# Meeting Notes Sync

A meeting happens. Gemini writes notes to Drive. Someone creates a ClickUp page for it — or doesn't. This skill closes the gap: it finds meetings whose notes never made it into ClickUp, and for the ones that have a page, it appends the decisions and any action items nobody wrote down, each with its owner named.

It does **not** notify anyone. ClickUp's API cannot create a working mention in a doc, so owners are plain text and the daily digest is the handoff.

**Read `state/registry.md` before matching anything.** It maps each recurring meeting series to its ClickUp destination, and it is personal to whoever installed this — build it with the install audit, never by guessing a destination from a title. The format and matching rules live in [`references/meeting-registry.md`](references/meeting-registry.md); the rows do not.

## About

**Privilege level: `can-send`.** This skill writes to ClickUp unattended on a schedule. It appends to existing documents that other people read.

What bounds that:

- It only appends. `replace` mode is banned, so it cannot alter or delete anything already on a page.
- It never creates pages. It writes only where a human already made a page, inheriting that person's access decision.
- It only touches meetings the operator personally organized, verified against their calendar.
- It refuses to write on any ambiguity: no matching page, two matching pages, or an unverified registry row all produce a report instead of a write.
- A sensitive-topic meeting whose page sits in a team-wide space is refused, not written.

**Required tools:** ClickUp MCP connector; a Google Workspace CLI (`gws`) with Drive, Docs and Calendar access; Python 3.9+. A Slack connector is optional and only used for the digest.

**Owner:** Jarir Mallah.

## Definition of done

A run is correct when all of the following hold. Each is checkable by reading the page and the digest afterwards.

**Pass condition**

1. Every meeting written to was organized by the operator (`organizer.self == true` on the calendar event).
2. Every page written to already existed and was matched to exactly one candidate.
3. Every write used `content_edit_mode: "append"`. Re-reading the page shows all pre-existing content byte-identical.
4. Nothing was written that the page already covered.
5. Every meeting written is recorded in `state/processed.json`, and a second run in the same window writes nothing.
6. Every skipped or refused meeting appears in the digest with a reason.

**Golden example**

A weekly meeting the operator organizes. Gemini produced 13 action items and 5 decisions; the notetaker had already written up most of it.

Expected output: the skill appends one block containing **4 action items and 2 decisions** — the ones not already on the page — each action item carrying an owner name. Six action items are dropped as duplicates, one as already marked done, three decisions as already recorded. The pre-existing page content is unchanged. The digest lists the four items with their owners.

The measure of success is how much it declined to write. A run that appended all 18 items would be a failure, not a thorough job.

**Adversarial case**

A meeting page containing a bookmark widget and a PDF attachment nested inside a list item.

Expected behaviour: the append succeeds and both survive untouched. If any future change makes the skill use `replace` on such a page, ClickUp's markdown importer escapes the bookmark into literal text and ejects the attachment from its list item — unrecoverably, since writing the original markdown back reproduces the corruption. This was observed on a live page, which is why `replace` is banned rather than merely discouraged.

A second adversarial case: a meeting whose title matches the private-topic list, whose ClickUp page sits in a team-wide space. Expected behaviour is a refusal plus a digest line, never a write.

## Ground rules

| Rule | Why |
|---|---|
| **Only sync meetings you organized.** Confirmed against your calendar, never assumed. | Several teammates run this. Without the filter, every attendee races to write the same ClickUp page. The organizer is the one unambiguous owner. |
| **Never create a ClickUp page.** If the series doc exists but today's page doesn't, report it and stop. | The person who creates a page also chooses who can see it. Creating pages means guessing at access — that's how a comp discussion ends up in a team-wide space. |
| **Never overwrite human text.** Append-only; `replace` mode is banned. | People take notes live during the meeting. Theirs wins. Append is merged server-side, so their page is never re-parsed. |
| **Ambiguous match = flag, don't write.** Zero candidate pages, or two, means stop. | This runs unattended. An unattended wrong write is worse than an unattended no-write. |
| **Inherit the page's privacy.** The page's location is the access decision, already made by a human. | Operator instruction. The skill respects that choice rather than re-litigating it. One safety net remains — see the [private-topic guard](#3-apply-the-private-topic-guard). |
| **The digest is private.** Local file, plus a Slack DM to yourself. Never a channel. | The digest lists meeting titles. "Performance review – <name>, no notes page" in `#general` is the leak the rest of this design avoids. |
| **Process each meeting once.** Two-layer idempotency: state file + the visible `Source:` link in the appended block. | Re-running must be a no-op, even after the state file is lost. |

## Source of truth: Gemini notes, not transcripts

Audited 2026-08-20: Ling has Gemini note-taking on and Meet transcription **off**. Across the personal `Meet Recordings` folder and the Shared Drive meeting folders, effectively every artifact is `— Notes by Gemini`. Transcripts are near-absent.

So: **Gemini notes are the primary source.** They arrive already structured (`Summary` / `Decisions` / `Next steps` / `Details`) and `Next steps` already carries owner attribution. A transcript, when one exists, is optional enrichment only — never required, never fetched when Gemini notes are present. Parsing details in [`references/gemini-notes.md`](references/gemini-notes.md).

This also keeps the run cheap. Do not pull full transcripts by default.

## Workflow

### 1. Find new meeting artifacts

```bash
python .claude/skills/meeting-notes-sync/scripts/scan_sources.py
```

Reads only. Scans **three** places, recursing into subfolders:

| Location | Notes |
|---|---|
| `My Drive › Meet Recordings` | The original Meet output folder. Frozen on this account after 2026-07-31, but still holds history. |
| `My Drive › Google Meet` | Where Google now writes Meet artifacts — the switchover happened ~2026-07-29. |
| Shared Drive › `Meeting Notes & Recordings` | Where a team drive keeps them, if you use a skill that files recordings there. |

**Google moved the personal folder, and restructured it.** The newer folder groups artifacts into a subfolder per meeting — `<Title> (recurring)/` for a series, `<Title> - <timestamp>/` for a one-off — rather than the old flat dump. A non-recursive listing of that root returns only folders and **zero files**, so scanning it the old way finds nothing at all while appearing to succeed. Hence `walk_folders`.

Scan all three permanently rather than switching. The rollout overlaps — files kept landing in the old folder for days after the new one appeared — teammates flip over on different dates, and a recording-filing task may move things between locations on its own schedule. Deduplication is keyed on Drive file ID, so a file that moves between runs is still recognised as already-processed.

`--since <ISO>` overrides the state file. `--dry-run` prints without touching state.

It also **recovers renamed artifacts automatically**. A Gemini doc someone renamed loses its filename timestamp; the scanner identifies it by document structure and recovers the meeting from Drive `createdTime` plus a unique calendar event. This needs no confirmation — a confident recovery is just a match, and an unconfident one is dropped rather than raised as a question.

Two things it deliberately does not do, both covered in [`references/gemini-notes.md`](references/gemini-notes.md#renamed-files):

- **It never reads a date out of the document body.** Gemini notes carry no meeting date. The only dates in the text are incidental references inside the discussion, and picking one up lands you on a real page for a different meeting.
- **It never assumes an unmatched file is a meeting.** Most aren't — they're human prep docs living in the same folder: empty note templates, interview scripts, agendas. Recovery gates on document structure, so those are rejected rather than synced as if they were notes.

### 2. Filter to meetings you organized

The scanner does this automatically — it's documented here because it decides what the rest of the run even sees.

For each meeting it looks up the matching event on your primary calendar and keeps the meeting only when **`organizer.self` is true**. Google sets that flag only for the authenticated user, so the filter needs no configured email and works unchanged for every teammate.

**Why this exists:** this skill is installed per-person. A sprint meeting has eight attendees; without the filter, all eight sync the same meeting into the same ClickUp page. The organizer is the single unambiguous owner, so they do it and nobody else does.

Note that **`creator` and `organizer` differ** in real data: an assistant or teammate often creates the invite for someone else's meeting. Key on `organizer`.

#### Do not substitute a Drive-based signal

Two obvious-looking alternatives were tested against live data and both are wrong:

| Signal | Why it fails |
|---|---|
| *"The artifact is in my Drive"* | Meet puts copies in the Drive of people who neither organized **nor attended** the meeting. |
| *"I own the artifact file"* | Those same copies come back `owners[0].me == true`, most with `shared: false` — sole ownership of notes for a meeting you had nothing to do with. |

Both were checked against live data. Drive location and file ownership look authoritative and are both noise. **The calendar `organizer` field is the only trustworthy signal**, which is why the filter uses it and nothing else.

The filter **fails closed**. Anything that can't be positively attributed to you is skipped:

| Skip reason | Meaning |
|---|---|
| `not-organizer` | Matched an event; someone else organized it. |
| `no-calendar-event` | No event on your calendar. Usually someone else's meeting whose artifact landed in a Shared Drive you can read. |
| `ambiguous-event` | Two candidate events disagreeing on who organized. Never guess. |
| `unparseable-timestamp` | Filename timestamp didn't parse. |

If the calendar read itself fails, **abort the whole run** rather than syncing unfiltered.

**The coverage gap this creates, stated plainly:** if a meeting's organizer doesn't have this skill installed, that meeting is never synced *and* never flagged — it drops silently for everyone. Attendees see nothing, because it isn't theirs to report. The only fix is rollout: get the skill to the people who organize recurring meetings. Expect a handful of people to own most of the recurring series.

`--include-all-organizers` disables the filter. It is a debugging flag. Never use it in a scheduled run.

### 3. Apply the private-topic guard

The guard's keyword list ships with this skill, at [`references/private-topics.md`](references/private-topics.md). Nothing else needs installing.

**If that file is missing, abort the entire run** and report that the private-topic guard is unavailable. Do not proceed with the guard disabled, do not improvise a keyword list from memory, and do not skip ahead to writing. A guard that silently no-ops is worse than no skill at all — it writes a compensation discussion into a team-wide space while reporting success.

Run each meeting title through the list. A hit does **not** mean skip. It means: this meeting may only be written to a page in a **private** ClickUp space.

- Guard hit, matched page in a private space → proceed normally.
- Guard hit, matched page in a team-wide space → **refuse the write**, flag loudly in the digest. Someone put a sensitive meeting's page somewhere broad. A human decides that, not this skill.
- No guard hit → proceed normally.

Space privacy is read from ClickUp, never assumed — see [`references/clickup-docs.md`](references/clickup-docs.md#checking-space-privacy).

### 4. Match the meeting to its ClickUp page

Two steps, in order. Full method and worked examples in [`references/meeting-registry.md`](references/meeting-registry.md).

**a. Title → series.** Match against the rows in `state/registry.md`. No confident match → `unmatched-series`, flag, stop. Only ✅ verified rows may be written to; ⚠️ provisional and ⛔ blocked rows report only.

**b. Series → page.** Within the series' parent doc/page, find candidate pages whose **`date_created` falls within ±3 days of the meeting date**.

Match on `date_created`, **not** on parsing the date out of the page title. Page titles across this workspace use `MM.DD.YYYY`, `DD.MM.YY`, `DD/MM`, `M/D`, `YYYY.MM.DD`, and bare month names — the `ASO Sprint Meeting Notes` doc alone switched from `DD/MM` to `M/D` mid-series, which makes `12/12` undecidable. `date_created` is returned by the API and is unambiguous. Use the title only to *confirm* a candidate, never to select one.

| Candidates | Action |
|---|---|
| exactly 1 | write |
| 0 | `no-clickup-page` → flag, do not create |
| 2+ | `ambiguous` → flag, do not write |

### 5. Resolve owner names

Action-item owners arrive as display names (`[Full Name] Task: detail`). ClickUp mentions need numeric IDs.

**Resolve by email via the calendar event, never by display name alone.** This workspace contains at least one person holding two accounts under the same display name, so a name lookup picks between them arbitrarily and tags the wrong one silently. Ordered resolution rules and the rest of the traps are in [`references/roster.md`](references/roster.md).

Owners who resolve to no ClickUp member are usually external (agency, partner). Write their item with their **plain name, unmentioned**, and list them in the digest. Never guess at a nearby member.

### 6. Subtract what the page already says

**If the page is already correct, there is nothing to do.** This skill improves meeting notes; it does not restate them. A run that writes nothing because the notetaker did their job is a success, not a miss.

Before composing anything, read the target page and drop every item already covered:

- **Action items.** Compare each Gemini `Next steps` entry against the page's existing checkboxes *and* its agenda/IDS sections — items often live outside the Action Items heading. Match on the substance of the task, not on wording; Gemini rephrases. Already present in any form → drop it silently, not into the digest.
- **Decisions.** Same test. A decision the page already records, in any section, is not new.
- **Completed items.** If the page marks the task done, the item is dropped — Gemini regularly re-reports work that finished during the meeting.

Measured on a well-maintained page during testing: of thirteen Gemini action items, **six duplicated existing items, one was already marked DONE, and three carried owners contradicting the page.** Four were genuinely new. Appending all thirteen would have left the page with two owners for the same task. Expect this ratio wherever someone takes notes properly.

If nothing survives this step, **write nothing and record the meeting as processed.** Do not append a block containing only a provenance line.

### 7. Decide whether you can name an owner

Gemini's `[Person Name]` prefix is a **suggestion, not a fact**, and it is wrong often enough to matter.

From that same test: the meeting had **six** attendees and Gemini's `Next steps` named only **two** of them. Four people who owned work on that page appear nowhere in its attributions. It credits whoever was speaking, not whoever owns the task — and the meeting's own organizer confirmed four of thirteen owners were simply wrong, including one assigned to him that belonged to someone else.

So tag an owner **only** when both hold:

1. The name resolves to exactly one current ClickUp member who was a calendar attendee ([`roster.md`](references/roster.md)).
2. No existing item on the page assigns the same task to somebody else.

Otherwise write `Owner unconfirmed - ` and list it under `Unverified owners` in the digest. An unconfirmed item costs someone ten seconds to claim; a confidently wrong name sends the work to the wrong person and quietly contradicts the page's own record.

A correction from someone who attended the meeting overrides all of this. If a human tells you who owns an item, use that name — that is the corroboration the rule is trying to approximate.

Where Gemini's owner contradicts the page, **the page wins.** A human wrote it, during or after the meeting, with context the model lacked.

### 8. Write — append one block, never replace

Use `content_edit_mode: "append"`. It merges server-side, so the existing page is never re-parsed and cannot be damaged. Block shape and rules: [`references/clickup-docs.md`](references/clickup-docs.md#where-new-content-goes).

**`content_edit_mode: "replace"` is banned.** It round-trips the whole page through ClickUp's markdown importer and destroys bookmark widgets, un-nests attachments, and flattens checkbox state — including content the write never touched, and not recoverably. This is not theoretical; it happened once.

**Never put an HTML comment anywhere in the content.** It renders as visible literal text and poisons its whole line, degrading any mention on that line to raw markdown. The visible `Source:` link is the idempotency marker instead.

**Write plain names, never `@mention` markup.** Through the API it produces a dead link: right name, looks like a tag, clicks nowhere, notifies nobody. That is worse than a plain name, because readers assume the person was told. `- [ ]` checkboxes do work, so the block still reads like the rest of the page.

Because nothing on the page notifies anyone, **the digest is the real handoff** - it must list who owns what.

Because append has no API undo, **a bad block is deleted by a human in the ClickUp UI** — never attempt to clean it up with `replace`. Get it right the first time and keep it one contiguous, obviously-deletable chunk.

Stop on the first write failure, report it verbatim, do not retry past two attempts.

### 9. Verify, record, report

Re-read each written page and confirm the appended block is present **before** recording the meeting as processed. Then write state and emit the digest.

Digest sections, in order:

- **Synced** — meeting, page link, and **each action item with its owner**. The page notifies nobody, so this is the actual handoff, not a summary.
- **No ClickUp page** — notes in Drive, no page found. The main thing the operator acts on.
- **Ambiguous** — two candidate pages; name both.
- **Unmatched series** — not in the registry. A repeat offender here is the signal to add a row.
- **Privacy refusals** — guard hit, page in a team-wide space. Always list explicitly.
- **Unmapped owners** — action items whose owner has no ClickUp account.
- **Nothing to add** — a bare count of meetings whose page already covered everything.
  This is the success case, not a failure; it means the notetakers are doing their job.
- **Unverified owners** — action items written unassigned because Gemini's owner
  couldn't be corroborated, or contradicted the page. The one list worth scanning
  daily: these are real tasks with no name on them.
- **Skipped (not organizer)** — a bare count, not a list. Itemising other people's
  meetings every day is noise, but the count tells you whether the filter is
  behaving.
- **Errors** — verbatim.

## The daily run

Installed as a scheduled task at **10:00 local** — see [`INSTALL.md`](INSTALL.md).

10:00 is chosen, not arbitrary: it sits after any daily task that moves recordings into shared drives, so artifacts have settled, and it avoids colliding with other morning automations. Gemini notes also land minutes-to-hours after a meeting ends, so an earlier run just finds nothing.

**On event-driven triggering:** the correct signal exists — Google's Workspace Events API can subscribe to Meet artifact-ready events and push to Cloud Pub/Sub — but it needs a Pub/Sub topic, a subscriber, per-user OAuth, and channel renewal. Not worth it to save a few hours. Calendar "meeting ended" fires too early (notes aren't written yet), and Apps Script has no Drive folder-watch trigger, only time-driven ones, so that route is polling with extra steps. Because this skill is idempotent and cheap, **frequency is a free dial** — run it twice daily if latency matters. That's the better lever than a webhook.

## Building the registry (install, and whenever coverage looks wrong)

```bash
python .claude/skills/meeting-notes-sync/scripts/audit_calendar.py --days 120 --json
```

Returns every recurring series the person **organizes**, with cadence, occurrence dates, attendee emails, and the Drive artifacts found for each. It excludes 1:1s, personal holds, and one-offs, reporting them as counts without titles.

For each returned series, do the ClickUp half the script cannot:

1. **Search** for candidate docs and pages by the series name (`clickup_search`, `asset_types: ["doc"]`).
2. **Enumerate** each candidate's child pages (`clickup_list_document_pages`) and read their `date_created`.
3. **Align** those dates against the series' `artifact_dates`. Three or more matching occurrences inside the −10/+3 window → ✅ verified.
4. **Draft** the row into `state/registry.md`, keyed on `series_name` rather than `title` — a trigger containing a month name only ever matches once. Follow the row format in [`references/meeting-registry.md`](references/meeting-registry.md).
5. **Ask** only about what won't reconcile: two candidate docs, no candidate at all, or dates that don't line up.

Resolve nothing by guessing. Two candidates is a question for the owning team, not a coin toss — writing to the wrong doc splits that meeting's history permanently, and nothing in the data distinguishes them.

Series with **no Drive artifacts** get no row. Nothing will ever sync for them regardless of what the registry says, and a row that never fires is noise that later reads as coverage.

## State: what dedups, and what merely bounds

Two different jobs, and conflating them loses work silently.

| Field | Job |
|---|---|
| `processed` | **Dedup.** Keyed on Drive file id. This is the only thing that decides a meeting is done. |
| `last_run` | **Performance bound only.** Narrows how far back to scan. Never treat it as dedup. |

`compute_cutoff` subtracts a **3-day lookback** from `last_run`. Without it, `last_run` acts as a hard floor on Drive `createdTime`, and an artifact created before it but never processed — a failed run, an interrupted run, a skip reason that no longer applies — is filtered out on every subsequent run. It never entered `processed`, so nothing catches it: no error, no digest line, no retry. Silent one-way loss.

Re-seeing an already-processed artifact costs nothing, because `processed` filters it. So the buffer is close to free and removes the failure mode.

This is the one piece of logic with its own tests, for that reason:

```bash
python .claude/skills/meeting-notes-sync/scripts/test_cutoff.py
```

Run them after touching anything in `compute_cutoff`.

## Notes for whoever maintains this

### Established by testing, not reasoning — do not re-litigate

Each of these was got wrong at least once by assuming rather than checking. The wrong answer looked reasonable every time.

| Rule | What happens if you ignore it |
|---|---|
| `append` only, never `replace` | `replace` round-trips the page through ClickUp's markdown importer and destroys bookmark widgets, ejects attachments from list items, un-escapes checkboxes. Unrecoverable via API. |
| No `@mentions` — plain names | Every syntax produces a dead link: right name, looks like a tag, clicks nowhere, notifies nobody. Worse than plain text, because readers assume the person was told. |
| No HTML comments | They render as visible literal text and poison their whole line. |
| A rendered page looking right is not proof | Mentions rendered perfectly while being dead links. Only the person confirming they were notified proves a mention works. |
| Client-side checks don't cover server-side transforms | A diff assertion proving every original line survived in the *payload* passed while ClickUp corrupted the page on save. Verify by reading back, never by checking your own buffer. |

The general lesson, which cost three page restores: **check the tool schema and test on a real page before asserting how an API behaves.** The claim "there is no append primitive" was false, took thirty seconds to disprove, and caused all of the damage above.


- **The registry is the skill.** Everything else is plumbing. When the digest reports the same `unmatched-series` three weeks running, add a row. That's the maintenance loop, and it's the only one that matters.
- **Rows are personal, and stay in `state/`.** They describe one person's meetings and their teams' doc layout. Never move rows into `references/`, and never ship a populated registry — the next installer's meetings are different, and a stale row pointing at someone else's doc is exactly the failure mode the whole design guards against.
- **Series structures drift.** Teams reorganise their docs (the Ads series moved from flat pages to `Meeting Notes - <year>` parents). When a series that used to match starts reporting `no-clickup-page` every week, re-audit its registry row before assuming people stopped taking notes.
- **Don't add a create-page path.** It will be tempting the first time someone asks why their meeting wasn't written up. The answer is that a human creating the page *is* the access-control decision, and this skill has no basis for making it.
- **If transcription ever gets enabled workspace-wide**, revisit the source-of-truth section — but keep Gemini notes primary. They're cheaper and already structured.
