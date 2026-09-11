---
name: performance
description: Use when a task has efficiency requirements or touches a hot path — make performance a measured requirement (benchmarks as tests, budgets as gates), keep interfaces clean and optimizations local, and version the WHY so future agents don't "clean up" fast code back to slow.
---

# Performance (measured, not vibed)

"Efficient" is a requirement, not a code style. Untested performance claims rot exactly like
untested behavior claims. This skill makes efficiency mechanical — the same move Yoke makes
for everything else.

## The decision ladder

1. **Default: clean + minimal.** For ~90% of code, the `minimal-code` rules ARE the
   performance strategy — less code, fewer layers, no speculative abstraction. Do not
   micro-optimize code that no measurement flagged (premature optimization).
2. **Performance requirement? Make it an acceptance criterion.** A number, not an adjective:
   - Good: "imports 1M rows in < 2s", "p95 request latency < 50ms in the bench test",
     "no allocation inside the render loop (verified by the bench assertion)"
   - Bad: "should be fast", "optimize the importer"
3. **Whole-project budget? Use the perf gate.** Set `perf.command` in `.yoke/config.yaml`
   (a benchmark script; exit 0 = within budget). The loop runs it after verify — a story
   that breaks the budget is blocked, no matter how clean its diff is.

## Writing efficient code that agents can maintain

- **Clean at the boundaries, aggressive in the leaves.** Interfaces, data flow, and names
  stay simple and obvious. Optimization lives inside a few clearly-bounded leaf functions
  whose contracts are pinned by tests. An ugly-fast function is maintainable; an
  ugly-fast architecture is not.
- **Profile before optimizing.** Find the actual hot 5% (a profiler, a timing harness, the
  bench script) — never optimize from intuition. Record the measurement in the PR/commit.
- **Benchmarks are tests. Commit them.** An optimization without a committed benchmark is
  one refactor away from silently disappearing. The bench script doubles as `perf.command`.
- **Version the WHY.** Every non-obvious optimization gets a one-line comment
  (`perf: avoids N+1 — see bench/import.mjs`) and, if it shaped a design, a line in
  `context/DECISIONS.md`. The most common AI maintenance accident is a later agent
  "simplifying" fast code back to slow because nothing said why it was shaped that way.
- **Know the classics before reaching for cleverness:** right data structure (map vs list
  scan), batching over per-item round trips (N+1), streaming over buffering, avoiding
  repeated work in loops, caching only with a measured hit rate and an invalidation story.

## Red flags

- Optimizing without a measurement or a budget → stop, measure first.
- A "refactor" or "cleanup" story touching code with `perf:` comments → re-run the bench
  before AND after; keep the numbers in the story outcome.
- Hand-rolled cleverness where the stdlib is already O(right) → `minimal-code` wins.
