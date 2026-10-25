# Agent Baseline

Use these project rules as the default:

- **Quality first:** Test-driven development is the default. No production code without a failing test first. See skill `tdd`.
- **Stop-the-Line:** Do not start implementation until Definition of Done / Acceptance Criteria are written. See `policy/gates.md`.
- **Role separation:** The agent that implements does not self-review, self-merge, or self-audit security. See `policy/roles.md`.
- **Context efficiency:** Prefer the wired tools (rtk for command output, the code-graph for symbol lookup) over reading whole files. See `tools/`.

This file is the portable baseline. Agent-specific instructions are generated alongside it (CLAUDE.md, GEMINI.md).

## Host capabilities and execution budgets

- Use only tools and skills actually installed in the host. Legacy `superpowers:` references in adapted skills refer to the corresponding local skill; `test-driven-development` maps to `tdd`. Do not install another plugin just to resolve a namespace.
- Run focused checks for quick feedback, but never skip required acceptance, protected, integration, or release gates. Cache evidence only when code, configuration, and environment still match.
- Distinguish observed durations from future estimates. Report the sample count, empirical range, and unknown waiting time; a timeout is a budget, not a promised completion time. Do not reduce reasoning or test scope merely to meet an estimate.

## Skill routing & precedence

When several skills could match the same task, resolve deterministically:

1. **Methodology before role.** Skills that decide *how* to work (`brainstorming`, `writing-plans`,
   `tdd`, `subagent-driven-development`, `systematic-debugging`, …) take precedence and set the
   process. Role skills (`review`, `ship`, `health`, `retro`, …) add a perspective on top.
2. **One canonical entrypoint per concern** — pick the most specific:
   - Plan-time architecture review → `plan-eng-review`
   - Plan-time product / scope review → `plan-ceo-review`
   - **Pre-merge code review → `review`** (the single canonical one)
   - Requesting a review (dispatch a reviewer) → `requesting-code-review`
   - Handling review feedback → `receiving-code-review`
   - Overall order of operations (idea → deploy) → `workflow`
3. **Don't double-run.** These skills declare their own triggers aggressively; when more than one
   matches, the precedence above and the most-specific entrypoint decide. Do not run two skills
   that serve the same concern on the same task.

@RTK.md
## Approved DLSS work
