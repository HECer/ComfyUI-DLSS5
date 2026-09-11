---
name: writing-for-agents
description: Create or edit agent-facing instructions such as AGENTS.md, CLAUDE.md, skills, roles, and workflow documents. Use when triggers, completion criteria, context pointers, instruction hierarchy, or duplication affect whether an agent can execute the document reliably.
---

# Writing for agents

Write instructions that produce a repeatable process with observable completion, while preserving
authorization, safety rules, acceptance criteria, and precise domain language.

## Context pointers

A pointer names out-of-context material and states when to load it. A skill description and an
`AGENTS.md` link serve the same routing function.

- Front-load the capability or trigger.
- Name each genuinely different branch once; remove synonymous trigger lists.
- Keep must-have instructions behind a pointer only when its trigger is strong enough to load them.
- Spend always-loaded context on rules needed broadly; disclose branch-specific reference material.

## Information hierarchy

1. Put ordered actions and their completion criteria in the main file.
2. Co-locate definitions, rules, and caveats that an action needs.
3. Move substantial branch-specific reference behind a named link and say when to read it.
4. Keep each durable meaning in one source of truth. Treat scripts, config, and directory structure
   as discoverable sources instead of copying facts that will go stale.

Every step needs a checkable completion criterion. Prefer an exhaustive observable bound such as
"every changed public interface has a passing contract test" over "review the interfaces."

## Editing pass

- Remove duplicated, contradictory, stale, or no-op instructions.
- Replace vague verbs with concrete actions, paths, commands, evidence, and stopping conditions.
- Separate durable project rules from details that belong only to the current task.
- Phrase the desired behavior positively. Keep prohibitions for real guardrails and pair them with
  the action the agent should take.
- Keep examples only when they distinguish correct behavior from a likely mistake.
- Preserve user scope: completing a workflow never grants unrelated external or destructive action.

When the document is a skill, read [SKILL-MECHANICS.md](SKILL-MECHANICS.md).
