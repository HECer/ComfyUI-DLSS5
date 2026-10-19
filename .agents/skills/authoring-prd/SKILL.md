---
name: authoring-prd
description: Use when turning a product idea or change into a continuous backlog with small stories and executable behavioral evidence.
---

# Authoring a PRD

Turn agreed product scope into small, independently verifiable stories. Follow an existing
project backlog format when one is established.

## Story rules

1. One independently reviewable outcome per story. Prefer several small stories over a few epics.
2. Each story leaves the project buildable and testable.
3. Acceptance describes observable behavior, not implementation. Give each of 2–5 criteria a
   stable ID, behavioral text, and one or more real verification commands.
4. Use dense priorities starting at 1; order by dependency and then risk.
5. Greenfield work includes a runnable project skeleton and its first behavioral checks.
6. Express performance goals with numbers and executable benchmarks, not words such as “fast”.
7. Record hard prerequisites and shared-file collision areas when they affect sequencing.
8. Assess risk, uncertainty, scope, and testability with a short reason and concrete checks.
   These are planning judgments, not invented success probabilities.

## Suggested format

```yaml
stories:
  - id: STORY-1
    title: scaffold a TypeScript CLI with a runnable test suite
    priority: 1
    acceptance:
      - id: cli-help-runs
        text: the CLI help command exits 0 and prints usage
        verify: [npm run test:cli-help-runs]
    status: proposed
```

Every story has 2–5 structured criteria. Each verification entry names a real project command that
proves that criterion. Do not mark a story complete until its acceptance evidence is available.
