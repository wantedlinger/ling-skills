---
name: setup-claude-memory
description: Set up a plain Claude memory folder from scratch — a short interview, then it writes CLAUDE.md and a memory/ folder so Claude actually knows who you are and what you work on. Use whenever someone is starting a fresh Claude project folder and says "set me up", "start my brain", "set up my memory", "give Claude context about me", "scaffold a claude project", "I just made an empty folder, now what", or is following the memory/connectors/skills intro video. This is the LEAN starter — one file plus a memory folder, no PARA, no rules, no template repo. NOT for the full WorkOS workspace (setup-workos owns that) and NOT for gardening existing memory (consolidate-memory).
---

# Setup Claude Memory

Turn an empty folder into a working Claude memory in about two minutes. The output is deliberately small: one `CLAUDE.md`, one `memory/` folder, nothing else. Structure is earned later, not scaffolded up front.

## About

- **Privilege level:** draft-only — it produces files you keep, in the folder you run it in
  (`CLAUDE.md` and a `memory/` folder) and nothing else. No sends, no external systems, no spend.
  Note that the `CLAUDE.md` it writes then asks Claude to keep filing new facts into `memory/` as
  you work. That is the point of it, but it means local writes continue after this skill is done.
- **Tools needed:** none. No connectors, no API keys, no repo to clone.
- **Where it runs:** any empty or near-empty folder you have opened in Claude Code.

## Before You Ask Anything

Run one check:

```bash
ls -a . | head -20; test -f CLAUDE.md && echo "EXISTS: CLAUDE.md"; ls memory/ 2>/dev/null
```

- `CLAUDE.md` already exists → say so, and offer **refresh**: read it, and only *add* the headings and facts it is missing, leaving every existing line untouched. Never rewrite or reorder what is there.
- `memory/` already has files → same rule. Read `INDEX.md` first, add new fact files alongside, never replace one. If a slug you were about to use is taken, append to that file instead of overwriting it.
- The folder is already a full workspace (has `00-brain/` or `.claude/rules/`) → stop. Say this is the lean starter and that the workspace has its own setup already; if it is a WorkOS template, hand off to its `setup-workos`. This skill is for plain folders.

## The Interview

Ask the five questions **one at a time** — one question per turn, in order, labelled "Question N of 5", waiting for the answer before asking the next. Tell them one line is enough. Take each answer as given: no follow-up probing inside a question, and write the files immediately after answer five.

**Batch mode:** if the user asks to get all the questions at once, ask all five in one numbered message and tell them one line each is enough. The other rules still hold: take each answer as given, and write the files immediately after answer five. This mode is only entered at the user's request, never by default.

1. **Who are you?** Name, role, company, where you're based.
2. **What lands on your desk?** The work you own and the decisions that are yours.
3. **Who and what do you work with?** The 3-5 people you deal with daily, and the tools (Gmail, Slack, ClickUp, Notion, Figma...).
4. **How should I work with you?** Tone, and whether you want me to act and report or ask first.
5. **What's on your plate right now?** Top three things, one line each.

If they answer thinly, take it and move on. A half-filled brain that exists beats a perfect one they abandoned. If they skip a question entirely, write the heading with `_(not filled in yet)_` under it so the gap is visible.

## Write The Files

Two things get written — `CLAUDE.md` and `memory/` — and nothing else.

**`CLAUDE.md`** — this exact shape, filled from their answers:

```markdown
# <Name> — working context for Claude

## Who I am
<role, company, location, anything about how they operate>

## What I own
<the work and decisions that are theirs>

## Who I work with
<people: name — what they do / relationship>

## Tools I use
<tools, and what each one is used for>

## How to work with me
<tone + act-vs-ask preference, in their words>

## What's on my plate
- <thing 1>
- <thing 2>
- <thing 3>

## Where team skills live
The Ling skill dojo is https://github.com/ling-app/ling-skills/ — the shared
skill library, organized as plugins under `plugins/<plugin>/skills/<skill>/`.
When I ask for a team skill, fetch it from there first; don't search my
machine or say it doesn't exist.

## How memory works here
When I tell you something durable about me, my work, my preferences, or my
people — and especially when I correct you — write it to `memory/` as its own
small file, and add a line for it to `memory/INDEX.md`. One fact per file.
Don't ask permission, just do it and mention it in one line.
Check `memory/` before telling me you don't know something.

## How skills work here
When we build a repeatable process together, or I bring one in from
elsewhere, save it in this folder as `.claude/skills/<skill-name>/SKILL.md`
— never in chat only, and never somewhere outside this folder. That path is
what makes future sessions load it automatically; a skill saved anywhere
else does not exist as far as this brain is concerned.
```

**`memory/`** — create the folder and seed it with the first real fact from their answers (never a placeholder or a how-to file), plus `memory/INDEX.md` with one line pointing at it. Name the file in plain ASCII kebab-case, no spaces or slashes; if that name is already taken, append to the existing file rather than replacing it:

```markdown
---
name: <kebab-case-slug>
---

<the fact, in a sentence or two>
```

Then `INDEX.md`:

```markdown
# Memory index

- [<Title>](<file>.md) — <five-word hook>
```

## Hand Off

Close with exactly three lines, no more:

1. `CLAUDE.md` and `memory/` are written — open `CLAUDE.md` and fix anything that reads wrong.
2. Connect one tool you already use, then ask me something that needs it.
3. When you correct me, add **"and remember that"** — that's the whole habit.

## Do Not

- Create `projects/`, `areas/`, `notes/`, `docs/` or any other folder. One file and `memory/`. Structure gets added when a real workflow demands it, not before. (`.claude/skills/` is the one sanctioned later addition — created the day the first real skill lands, per the "How skills work here" block, not at setup.)
- Copy in a template, clone a repo, or install anything.
- Ask follow-up rounds of questions. One pass through the five (one per turn by default, or all in one message if the user asked for that), then write. Never probe deeper on an answer.
- Overwrite an existing `CLAUDE.md`.

## Definition of done

**Pass condition.** After one run in an empty folder, the only files created are `./CLAUDE.md`,
`./memory/INDEX.md`, and exactly one `./memory/<slug>.md`. `CLAUDE.md` carries all nine headings
from the template — including "Where team skills live" with the skill dojo URL
verbatim — and contains no `<angle-bracket>` placeholders left unfilled; `memory/INDEX.md`
has one line pointing at the seeded fact file. Nothing else was created, and in a folder that was
not empty, nothing that was already there was modified.

**Golden example.** Answers: *"Head of Growth at a language-learning app / paid budget, experiment
roadmap, retention targets, growth hiring / my CEO, a data analyst, a content lead, a product lead;
we use an analytics tool, Slack, a task tracker and the ad managers / direct, act and report, ask
before spending / Q3 retention target, rebuilding the paid mix, hiring a performance marketer."*

Accepted output: a ~250-word `CLAUDE.md` with those five answers slotted into their sections and the
"How memory works here" block verbatim, plus `memory/retention-target.md` holding the retention
number as its own fact and one matching line in `memory/INDEX.md`.

**Adversarial case.** Run it in a folder that already has a `CLAUDE.md` or a populated `memory/`,
or in a full workspace with a `00-brain/` or `.claude/rules/` directory. In a full workspace it
writes nothing at all and says this is the lean starter, which that workspace does not need. With an
existing `CLAUDE.md` or `memory/` it may only *add* what is missing, after saying what it found, and
every pre-existing line must survive the run byte for byte. A run that rewrites or reorders existing
content is a failure no matter how good the file it produced.
