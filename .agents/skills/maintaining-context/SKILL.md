---
name: maintaining-context
description: Use at the start of any substantial task and whenever you make a non-obvious decision or learn a reusable fact — keeps .yoke/context/ (PROJECT, DECISIONS, KNOWLEDGE) the durable source of truth so fresh-context work never drifts.
---

# Maintaining Project Context

Yoke keeps durable, cross-session context in `.yoke/context/`. These files are the
project's memory — they survive between sessions and loop iterations, so an agent
starting with a fresh context window is never blind.

## Before substantial work

1. Read `.yoke/context/PROJECT.md` — the north star (goal, constraints, **non-goals**, success criteria). Align your work to it. If the task contradicts a non-goal, stop and flag it.
2. Skim `.yoke/context/KNOWLEDGE.md` for gotchas that affect what you are about to do.

## While working

- When you make a **non-obvious decision** (a trade-off, an architectural choice, a rejected alternative), append it to `.yoke/context/DECISIONS.md`:

  ```
  ## <YYYY-MM-DD> — <area-or-story>: <short title>
  What you chose and why, in one or two lines.
  ```

  (This mirrors the heading the loop writes for completed stories, so loop-authored and hand-authored entries share one shape.)

- When you learn a **reusable fact or gotcha** (a non-obvious build step, an API quirk, a convention), append a bullet to `.yoke/context/KNOWLEDGE.md`.

## Rules

- Never rewrite history in `DECISIONS.md` — only append.
- Keep `PROJECT.md` curated and short; it is read into every loop prompt.
- Inside the autonomous loop, the loop appends a decision per completed story for you — you still add the *why* and any learnings.
