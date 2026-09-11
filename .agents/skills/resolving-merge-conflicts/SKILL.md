---
name: resolving-merge-conflicts
description: Resolve an in-progress Git merge or rebase conflict by tracing both sides to commits and available issue or spec evidence, preserving compatible intent, and running project checks. Use only when a merge or rebase is currently conflicted.
---

# Resolving merge conflicts

1. Inspect the current merge or rebase state, history, and every conflicted file.
2. Trace both sides to their commits and available pull request, issue, specification, and test
   evidence. Identify what each change was trying to preserve.
3. Resolve each hunk. Preserve both intents when compatible. When they conflict, follow the current
   operation's stated goal and report the trade-off. Do not invent unrelated behavior.
4. Discover and run the project's scoped checks, then the broader checks justified by the merge.
5. Stage resolved files and continue the current operation until Git reports it complete.

Keep all process actions scoped to the current repository and recorded operation. Never abort a
merge or rebase unless the user explicitly requests that destructive reversal. Stop for direction
when the evidence cannot distinguish two materially different product behaviors.
