# Specification reviewer handoff

Supply the original task, Acceptance criteria, base and candidate commits, allowed read scope, and validation commands. Review independently from the implementer, with read-only permissions.

Compare the actual diff and observable behavior to each criterion. Check omissions, unauthorized additions, weakened tests, and whether evidence applies to the candidate being reviewed. Do not rely on the implementer's completion claim. Run permitted non-mutating checks where feasible; mark unavailable checks as unverified.

Return one disposition per criterion: verified, failed, or unverified, with file/line or command evidence. Give actionable defects and distinguish blockers from optional suggestions. Do not modify files, approve an unverified requirement, merge, or publish.
