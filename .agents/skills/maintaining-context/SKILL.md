---
name: maintaining-context
description: Use at the start of any substantial task and whenever you make a non-obvious decision or learn a reusable fact — keeps .agents/context/ (PROJECT, DECISIONS, KNOWLEDGE) the durable source of truth so fresh-context work never drifts.
---

# Maintaining Project Context

The project keeps durable, cross-session context in `.agents/context/`. These files preserve
its goals, decisions, and reusable facts between sessions.

## Before substantial work

1. Read `.agents/context/PROJECT.md` — the north star (goal, constraints, **non-goals**, success criteria). Align your work to it. If the task contradicts a non-goal, stop and flag it.
2. Skim `.agents/context/KNOWLEDGE.md` for gotchas that affect what you are about to do.

## While working

- When you make a **non-obvious decision** (a trade-off, an architectural choice, a rejected alternative), append it to `.agents/context/DECISIONS.md`:

  ```
  ## <YYYY-MM-DD> — <area-or-story>: <short title>
  What you chose and why, in one or two lines.
  ```

  Use this heading for interactive decisions and completed work so entries share one shape.

- When you learn a **reusable fact or gotcha** (a non-obvious build step, an API quirk, a convention), append a bullet to `.agents/context/KNOWLEDGE.md`.

## Rules

- Never rewrite history in `DECISIONS.md` — only append.
- Keep `PROJECT.md` curated and short; read it before substantial work.
- Record the reason for each decision and any reusable learning alongside it.
