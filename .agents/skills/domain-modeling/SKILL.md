---
name: domain-modeling
description: Build or sharpen a project's domain language and durable decisions. Use when terminology is fuzzy or contradictory, relationships need scenario testing, the code disagrees with the stated model, or a glossary or ADR-class decision must be updated; do not trigger merely to read existing context.
---

# Domain modeling

Build the model actively: challenge terms, test relationships with concrete scenarios, compare the
stated behavior with code, and record a term when it becomes settled.

Yoke stores durable context under `.yoke/context/`:

- `GLOSSARY.md` is the canonical language for a single domain context.
- `CONTEXT-MAP.md` is optional and maps multiple domain contexts plus their relationships.
- `DECISIONS.md` records durable outcomes and ADR-class trade-offs.

Read the existing files before proposing vocabulary. Merely consuming their terms is a normal
context habit, not a reason to run this skill.

## Workflow

1. Identify overloaded, vague, conflicting, or missing terms in the request and current glossary.
2. Propose one canonical term and name avoidable aliases. Ask when the distinction changes behavior.
3. Stress-test relationships with specific scenarios, especially partial, repeated, failed, and
   cross-context cases.
4. Compare the model with public interfaces, persistence shapes, and relevant tests. Surface a
   contradiction instead of silently choosing one side.
5. When a term is settled, update `GLOSSARY.md` immediately using
   [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md). Preserve unrelated entries.
6. Update `CONTEXT-MAP.md` only when the repository contains more than one genuine domain context.
7. Record an ADR-class decision only when all three thresholds in
   [ADR-FORMAT.md](ADR-FORMAT.md) pass.

Glossary definitions describe the domain, not its implementation. General programming concepts do
not belong there.
