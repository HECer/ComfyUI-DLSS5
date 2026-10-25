# Implementer handoff

Supply the task, repository/worktree path, base commit, allowed write scope, relevant interfaces, and Acceptance criteria with their required checks. Include only relevant context and previous failure evidence.

Implement only the assigned task. Preserve unrelated changes. Reproduce defects with a failing test before fixing them; do not weaken protected tests or acceptance checks. Run focused checks during iteration and all required gates before handoff. Do not spawn nested workers, publish, merge, or expand permissions. Commit only if the controller explicitly delegates that responsibility.

Return: outcome, changed files, exact checks and exit results, remaining risks, blockers, and artifact paths. Report incomplete work as incomplete. If blocked by a product decision or missing credentials, retain the work and explain what is needed; do not repeat the same failing action indefinitely.
