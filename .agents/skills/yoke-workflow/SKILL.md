---
name: yoke-workflow
description: Use when the user asks Yoke to plan and build a feature, run stories autonomously, continue a Yoke loop, or only interrupt for major decisions.
---

# Yoke Workflow

Provide the same interaction contract in every supported Yoke harness.

1. Read `.yoke/config.yaml`. If it is missing, offer `yoke setup . --host=<current-agent>` and run the setup flow before planning.
2. Plan before starting the loop. Inspect the project, then ask one focused question at a time only where the answer changes product behavior, scope, architecture, security, data ownership, external cost, or an irreversible choice. Include a recommended answer. Resolve routine implementation details yourself.
3. Summarize the agreed design in `.yoke/plan.md`, including goals, non-goals, constraints, and decisions. Use the `authoring-prd` skill to turn it into small stories with testable acceptance criteria. Run `yoke prd check .`.
4. Ask once for approval of the complete plan and story set. Do not begin implementation before that approval.
5. If `loop.enabled` is true, run the stories without routine follow-up questions using the configured runner. Prefer `yoke loop run . --max=5 --isolate`, report status after each batch, and continue until complete or genuinely blocked.
6. Respect `loop.decisionPolicy`:
   - `auto`: choose the most suitable option from the plan, current code, and established conventions. Record the interpretation and continue.
   - `critical`: routine ambiguity is still resolved automatically. If the loop reports a pending critical decision, run `yoke loop decision .`, present its options and recommendation to the user, ask exactly that question, then run `yoke loop answer . --choice=<id> --rationale="<answer>"`. The answer command records the decision and resumes the same story.
7. Never ask whether to run tests, review, commit, or continue to the next approved story. Those are part of the approved workflow.

The user's configured commit identity is authoritative. Do not add an AI co-author unless `commit.allowCoAuthors` explicitly permits it.
