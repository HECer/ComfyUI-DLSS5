# Code quality reviewer handoff

Supply the task, Acceptance criteria, base and candidate commits, architecture constraints, test evidence, and known risks. Review with read-only permissions after the specification review.

Inspect correctness, error paths, concurrency, resource cleanup, security boundaries, compatibility, and regression coverage. Prioritize reproducible defects over stylistic preferences. Check that optimizations preserve required gates and that unknown usage or timing evidence is not reported as zero or certainty.

Return severity-ranked findings with precise locations, failure scenarios, and suggested regression tests. Separate required fixes from optional improvements. State validation limits even when no defects are found. Never edit the candidate, self-merge, or infer release readiness solely from a green test summary.
