# Yoke Harness — Agent Baseline

You are operating in a project retrofitted by Yoke. Follow these always:

- **Quality first:** Test-driven development is the default. No production code without a failing test first. See skill `tdd`.
- **Stop-the-Line:** Do not start implementation until Definition of Done / Acceptance Criteria are written. See `policy/gates.md`.
- **Role separation:** The agent that implements does not self-review, self-merge, or self-audit security. See `policy/roles.md`.
- **Context efficiency:** Prefer the wired tools (rtk for command output, the code-graph for symbol lookup) over reading whole files. See `tools/`.

This file is the portable baseline. Agent-specific instructions are generated alongside it (CLAUDE.md, GEMINI.md).

## Skill routing & precedence

When several skills could match the same task, resolve deterministically:

1. **Methodology before role.** Skills that decide *how* to work (`brainstorming`, `writing-plans`,
   `tdd`, `subagent-driven-development`, `systematic-debugging`, …) take precedence and set the
   process. Role skills (`review`, `ship`, `health`, `retro`, …) add a perspective on top.
2. **One canonical entrypoint per concern** — pick the most specific:
   - Set up or update Yoke → `yoke-retrofit`
   - Yoke-owned planning + autonomous story execution → `yoke-workflow`
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

<!-- yoke:preserve:start -->
## Approved DLSS work
Read .yoke/plan.md. User approved this backlog for autonomous implementation, tests and local commits. No push or publish. Keep all runtime binaries and established workflow contracts unchanged. Use active Yoke code intelligence; explicitly handle partial backend coverage. Before and after documentation edits use C:/Users/HEC_e/.codex/skills/audit-provenance/scripts/audit_provenance.py read-only; never remove provenance.
<!-- yoke:preserve:end -->

## Yoke supervisor execution contract
This worker is one implementation stage of an already approved Yoke loop. Do not start any subagents, review agents, nested Yoke loops, or delegation, even when a methodology skill normally suggests it. The outer Yoke supervisor performs the independent read-only review after your tests. This satisfies role separation. Finish the assigned implementation and tests, then return; do not commit. Do not restart planning or ask for approval. The coordinator owns routing/configuration.

