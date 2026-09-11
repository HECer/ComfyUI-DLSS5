---
name: authoring-prd
description: Use when turning a product idea or change into a loop-ready continuous backlog with small stories and executable behavioral evidence.
---

# Authoring a PRD

The Yoke loop is only as good as its stories. Keep the backlog continuous: new requests become
new stories; they do not require a release object.

## Story rules

1. One iteration per story. Prefer 5–12 small stories over a few epics.
2. Each story leaves the project buildable and testable.
3. Acceptance describes observable behavior, never implementation. Give each of 2–5 criteria
   a stable `id`, behavioral `text`, and `verify` list with one or more real commands proving
   that exact outcome.
4. Use dense priorities from 1; order by dependency, then risk.
5. Greenfield `STORY-1` creates the skeleton, runnable suite, and `verify.command`.
6. Express performance with numbers and executable benchmarks, not words such as “fast”.
7. Resolve planning questions before unattended execution. `yoke prd check` rejects unresolved
   placeholders; critical irreversible choices use the structured decision channel.
8. Use `needs` only for hard prerequisites, `area` for collision domains, and `agent` only as
   a supported harness affinity hint.
9. Keep planning on the start model. Add an `assessment` to each story: `taskClass`
   (`mechanical`, `implementation`, `debugging`, `architecture`), `difficulty`, `uncertainty`,
   `risk`, `scope`, `testability` (each `low`, `medium`, `high`), a concise `reason`, and
   an actionable `approach` including checks. High testability means executable checks
   reliably detect mistakes. Small security-sensitive changes can still be high-risk.
   These are planning judgments, never invented success probabilities; Yoke selects the
   execution model from configured profiles and independent outcomes.

## Format (`.yoke/prd.yaml`)

```yaml
- id: STORY-1
  title: scaffold a TypeScript CLI with vitest
  priority: 1
  acceptance:
    - id: cli-help-runs
      text: the CLI help command exits 0 and prints usage
      verify: [npm run test:cli-help-runs]
    - id: test-runner-starts
      text: the project test runner starts and reports at least one passing test
      verify: [npm run test:test-runner-starts]
  passes: false
- id: STORY-2
  title: add the sum command
  priority: 2
  needs: [STORY-1]
  area: cli
  agent: codex
  acceptance:
    - id: sum-valid
      text: cli sum 1 2 prints 3
      verify: [npm run test:sum-valid]
    - id: sum-invalid
      text: non-numeric input exits 1 with an error message
      verify: [npm run test:sum-invalid]
  passes: false
```

Every story has 2–5 structured criteria. Each `verify` entry is one approved test command whose
normalized text contains its criterion ID; never use shell operators or a broad unrelated suite.
`passes` is owned by the loop and always starts false. Validate with `yoke prd check`.
