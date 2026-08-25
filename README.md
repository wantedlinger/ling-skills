# Ling skills dojo

The shared home for Ling's skills. A skill is a repeatable process written down so a person or an
agent runs it the same way twice. Build one, publish it here, let anyone fork it.

The point is not the folder. The point is that improvements compound: when someone forks a skill and
makes it better, everyone gets the better version instead of it dying on one laptop.

## Install it (once, about 30 seconds)

Public repo, so no GitHub account and no access request. **Just tell Claude Code:**

> Install the plugin marketplace at https://github.com/ling-app/ling-skills and then install the
> getting-started plugin from it.

Then restart Claude Code, and the skill is loaded.

**If it refuses**, you are in a permission mode that cannot approve the install. This is the one
failure people actually hit: in a non-interactive or auto mode Claude reports it cannot run the
step and hands the commands back. Switch to a mode that asks permission, or run them yourself:

```
claude plugin marketplace add https://github.com/ling-app/ling-skills
claude plugin install getting-started@ling-skills --scope user
```

`--scope user` installs it everywhere rather than in one folder.

Inside an interactive Claude Code session the slash-command equivalents work too
(`/plugin marketplace add https://github.com/ling-app/ling-skills`). They are not available in the Claude desktop app,
which answers `/plugin isn't available in this environment`.

Later, to pick up everyone else's improvements:

```
claude plugin marketplace update ling-skills
```

Skills from a plugin are namespaced, so the one above runs as `/getting-started:setup-claude-memory`.

## What's in it

| Plugin | Skill | Privilege | What it does |
|---|---|---|---|
| `getting-started` | `setup-claude-memory` | draft-only | Turns an empty folder into a working Claude memory. Five questions, then it writes your `CLAUDE.md` and seeds a `memory/` folder. Start here if you are new. |
| `feedback-tools` | `user-feedback-categorizer` | read-only | Turns a pile of reviews, survey answers or churn reasons into a ranked table of themes with owners and a top 3 to act on. |
| `creative` | `generate-word-art` | can-send | Generates Ling-branded word art sticker PNGs: a word in the Ling title lettering, optionally with a mascot or Word-Icon graphic, on a transparent background. Needs an OpenAI API key; about $0.01 per image. |

The library grows from the workshop, not from me pre-filling it.

## Add yours

The easy way: open Claude Code in the workspace where your skill lives and paste

```
Publish my <skill name> skill to the ling-skills marketplace: clone
https://github.com/ling-app/ling-skills and follow the "Publishing checklist
(for Claude)" in CONTRIBUTING.md.
```

Claude does the copying, the portability cleanup, the safety check and the PR; you confirm what it
wrote and get one approval.

Doing it by hand instead: read [CONTRIBUTING.md](CONTRIBUTING.md). The short version:

1. Build it in your own workspace and actually use it.
2. `python3 scripts/safety-check.py <your-skill-folder>` and fix what it flags.
3. Make it portable (no `../` paths, no absolute paths, no hardcoded IDs, no personal names).
4. Give it a definition of done. **No eval, no merge.**
5. Open a PR. One approval, then it is everyone's.

## Is anyone using it?

```bash
scripts/adoption.sh "6 weeks ago"
```

Contributors, most-touched skills, and skills nobody has touched. That last list is the useful one:
a library that only grows is a library nobody prunes. The kill test is who asked for this, does it
connect to value within two steps, and has anyone acted on its output in three weeks.

## Rules of the house

- **Portable or it does not ship.** Plugins are copied to a cache on install, so a skill that reaches outside its own folder breaks for everyone but its author.
- **No eval, no merge.** A skill without a definition of done is a prompt, and prompts are disposable.
- **Every skill declares a privilege level.** read-only, draft-only, or can-send. Anything that sends, publishes or spends needs a named owner and a second reviewer.
- **Nothing private in here.** No customer data, no credentials, no `_private` content. This repo is shared by construction; assume everyone at Ling reads it.
- **Fork freely.** Forking is the mechanism, not a defection. `CONTRIBUTING.md` explains how to keep a fork and still take upstream updates.
