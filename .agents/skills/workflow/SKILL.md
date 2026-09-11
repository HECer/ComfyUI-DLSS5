---
name: workflow
description: Use at the start of any non-trivial task — the default order of operations for shipping quality work, from idea to deploy.
---

# Workflow — the default order of operations

For any non-trivial change, move through these phases in order (skip only what genuinely does not apply):

When `.yoke/config.yaml` exists and the user wants Yoke to own planning plus autonomous
execution, use `yoke-workflow` as the entrypoint. It adds the approved-plan → PRD → loop
handoff and the configured critical-decision behavior to the phases below.

1. **Brainstorm** the idea into a clear design — see `brainstorming`.
2. **Plan** a concrete, testable implementation — see `writing-plans`.
3. **Understand the code** — map the blast radius with the code-graph before changing anything.
4. **Implement test-first** — RED → GREEN → REFACTOR, smallest steps — see `tdd` and `minimal-code`.
5. **Verify** — run the real tests and exercise the change; never trust "it should work" — see `verification-before-completion`.
6. **Review** — get an independent review of the diff before landing — see `review` / `requesting-code-review`.
7. **Ship** — bump version, update changelog and docs, open the PR — see `ship` / `document-release`.

Stop-the-Line applies throughout: no implementation before acceptance criteria exist. Always prefer the least code that solves the task (`minimal-code`).
