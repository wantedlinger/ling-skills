# Style 2 — composition recipes

Companion to `_style_brief.txt`. **The brief owns HOW it is drawn; these own WHAT is in frame and
where.** Keep them disjoint — if a rule about colour or rendering creeps in here, it belongs in the
brief instead, and two documents arguing is how an image goes wrong.

Not read by the CLI. Pick the template for the word, drop its line into `--graphic` (in a
`jobs.json` for a batch), and append the concrete subject. One line each, on purpose.

| id | template | drop into `--graphic` |
|----|----------|------------------------|
| A1 | Solo Object | one hero object, centred, straight-on or gently three-quarter, soft grey ellipse shadow beneath, nothing else in frame |
| A2 | Object Cluster | two to four related objects staged as a still life, one clearly dominant, the rest overlapping at the base |
| A3 | Character + Prop | a waist-up figure set left or right of centre, one arm extended, holding or gesturing at a single prop — includes the hand-only variant: a cropped forearm entering frame performing the action, no face or body |
| A4 | Character in Scene | a full-body figure with feet on a ground plane, the environment blocked in loosely behind, the pose carrying the meaning |
| A5 | Two-Character Interaction | two figures at equal visual weight, facing each other or side by side, hands or gaze connecting them |
| A6 | Emotion Portrait | a head-and-shoulders crop filling most of the frame against a saturated colour field, the expression doing all the work |
| A7 | Building Facade | architecture straight-on and symmetrical, a pale sky blob behind, a grey ground strip below, signage on the awning naming the place |
| A8 | Photo-Frame Card | two or three offset white-bordered photo cards, each rotated a few degrees, figures inside — the person being named in full colour, everyone else drained to a tint |
| A10 | Symbol First | the mark itself drawn large and centred — pictogram, badge, counter or sign — with little or no scene around it |
| A12 | Comparison Pair | the same object drawn twice side by side, the one that means the word in full colour, its opposite redrawn in flat grey at full opacity |

## Not in this style

- **A9 Isometric Plate** — a tilted 3D tile with visible edge thickness and terrain on top. It is the
  only non-flat perspective in the corpus and the brief above explicitly forbids perspective, so it
  gets its own style number and its own references. Never request it here.
- **A11 Hand Action Crop** — folded into **A3** (2026-08-18 decision); the crop is a framing choice,
  not a different rendering.

## Devices

Multi-select and orthogonal to the table — see the DEVICES paragraph of `_style_brief.txt` for how
each is drawn. Name them in `--graphic` only when the word needs one: grey foil, sparkles, speech or
thought bubble, map pin, motion arrow, symbol chip, steam lines.
