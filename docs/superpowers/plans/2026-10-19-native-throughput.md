# Native SR/NR throughput optimization

The user approved continuing work on the measured native SR/NR bottleneck after selectable depth guides. The target remains 3840x2160 output above 30 source FPS on RTX 5090; record a failing gate honestly when it remains unmet.

## Acceptance criteria

- Profile parent and native child separately before choosing an optimization. Distinguish Python preparation, process/import/feature initialization, per-frame evaluation, array copies and disk writes. Preserve earlier source-fingerprinted measurements.
- Preserve all existing node required schemas/defaults, SR quality flags, NR settings, temporal chronology, still-image warmup, bounded-window behavior, cancellation and error propagation. Append optional controls only with compatible defaults.
- Do not replace bundled NVIDIA DLLs or the installed ComfyUI Torch environment. Prefer a local bridge improvement over new dependencies or a new rendering algorithm.
- Demonstrate numerical equivalence against isolated native outputs, including multi-frame behavior. Synthetic tests must exercise ordering, shapes, guide units and lifecycle; mocks are not image-quality evidence.
- Write and observe failing behavioral regressions before production edits. Retain required existing tests and obtain independent review.
- Add reproducible source-fingerprinted benchmarks with warmups, at least three timed samples, empirical ranges and source FPS. Compare matched workload/environment; do not infer real time from model-only numbers.
- Demonstrate a measured reduction in the profiled bottleneck and report the complete node-pipeline result. Treat 4K/>30 as unmet until its gate passes. Decode/encode are excluded and must be stated separately.

## Profiling and choice

The first unchanged-runner profile of two 1080p frames upscaled to 4K observed SR total 12.897 s / child 11.421 s, NR total 17.245 s / child 11.831 s. NR guide preparation took about 3.896 s. Child output-map flushing took about 1.19 s each. A finer instrumented run observed feature construction at 13.8315 s for SR and 9.7195 s for NR; frame requests totaled 0.8220 s / 1.7384 s. These are individual profiling observations, not future duration estimates or matched benchmark samples.

Alternatives considered: reduce CPU copies/file exchange, combine SR/NR in one runner, retain native initialization in a persistent helper. The measured initialization cost motivated the helper experiment.

Reused SR features failed independent-sequence numerical equivalence (maximum absolute error 0.25048828125). Explicitly disabling frame caches did not resolve it; the cause within native feature state remains unproved. Reject SR feature reuse and restore its original runner/schema.

Final implementation: optional persistent NR-only subprocess with one cached graph. Share NR construction/output code with the isolated runner, disable caching on mutable input/output clips, refresh holders and restart each sequence at frame zero. Preserve still warmup. Release the previous feature before settings/shape replacement. Cancellation, timeout, failure and runtime identity changes discard the helper; idle expiry is 120 seconds. Isolated execution remains the default and SR stays isolated in both modes.

## Execution and evidence

- [x] Inspect current bridge and preserve native baselines outside the repository.
- [x] Separate initialization from per-frame work and select the measured optimization.
- [x] Observe failing lifecycle/refresh/propagation regressions, implement the change and pass focused gates.
- [x] Real native NR comparison: seven A/B/A, still, settings and shape cases, maximum absolute error 0. See [native evidence](../../benchmarks/2026-10-20-native-equivalence.json).
- [x] Full suite: 317 passed, 5 skipped in 199.98 s. Explicit native test: 1 passed in 301.52 s. Independent read-only review: PASS conditional on these gates, both satisfied.
- [x] Browser check: English optional mode, compatible default, selection and unchanged SR schema; screenshot retained outside the repository. No inference queued from browser.
- [x] Matched benchmark: three two-frame samples each. Isolated median 35.080797 s / 0.057011 source FPS; persistent NR 25.787219 s / 0.077558 source FPS. Observed 1.36x throughput. Both strict 4K/>30 gates fail. Source fingerprints match current code.
- [x] Document empirical ranges, cold requests, unpaired sequential short-batch limits, unchanged SR timing variation and remaining native/transfer costs in [worker documentation](../../NATIVE_WORKER.md).

No push, PR or merge is requested. Preserve prior feature work and unrelated local instruction/configuration changes.
