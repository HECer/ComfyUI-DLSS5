# Testing anti-patterns

- Test observable behavior, not that a mock returned the value you supplied. Assert resulting state and failure behavior as well as calls.
- Mock external boundaries deliberately. If production constructs a second client for an isolated workspace, replace that constructor too; a unit test must not silently invoke a real network backend.
- Do not mock the implementation under test or delete assertions to make a change pass. Keep at least one contract/integration check for important boundaries.
- Demonstrate that the regression test fails for the original defect and passes after the fix. A new green test alone does not establish that it detects the bug.
- Avoid arbitrary sleeps and broad timeout increases. Use readiness events, controlled clocks and bounded cancellation.
- Preserve protected acceptance tests and required gates. Focused tests speed feedback but do not replace release validation.
- Report skipped tests, unavailable platforms and missing credentials separately from passing checks. Never convert absent measurements into measured zero.
