# DLSS usability and reliability implementation

The user approved all seven recommendations from the read-only 0.4.0 / 9d1c34b review and explicitly requested a real Yoke loop with routing and code intelligence. This is plan approval; do not ask again. Implement locally, test and commit through Yoke; no push, publication or deployment.

Keep every existing node ID, required input name/order, existing dropdown value/order, output order, default and native rendering setting compatible. New optional fields may be appended with safe defaults. No runtime DLL changes, no dependency upgrades, no replacement of ComfyUI's Torch environment. Preserve originals and existing custom configuration. Do not remove AI disclosure/provenance.

Scope: repeatable BOM-compatible configuration and setup; optional Frame Generation installation; truthful staged runtime diagnostics and early preflight; descriptions/tooltips/categories and meaningful operation hints; bounded Easy single-stage processing and truthful reports; progress, native cancellation and advisory memory estimates; concise first-run documentation and integration regression coverage.

Do not silently replace DA-V2 with VDA, change numerical presets, introduce scene-cut resets into SR/NR, or redesign model cache ownership. Those require separate image-quality experiments. Preserve persistent-mode numerical behavior. Test bounded single-stage processing with deterministic identity/frame-index fakes for chronology, overlap and exact length, plus native GPU checks when available. A passing mock is not proof of image quality.

Use .yoke/prd.yaml as acceptance authority. Tests must be meaningful behavioral regressions and must not download models or modify installed runtimes. Existing tests remain intact except legitimate contract updates such as richer status wording. Add new tests in tests/test_usability.py, using the criterion ID in test names so each targeted gate runs real tests. No empty suites or marker-only assertions. For UI/doc changes, prioritize semantic node-schema compatibility and executable workflow checks over string-only tests. Capture before/after node schemas in a fixture for compatibility.

Environment: Windows PowerShell, rtk required. The default Python already provides Torch/pytest. Runtime DLLs are tracked with Git LFS. The Yoke package version is 1.15.0; its bundled Canon version is 1.14.0. The original fingerprint refuses files above 64 MiB. The isolated .yoke/tooling/yoke copy contains the scoped compatibility changes documented in .yoke/compatibility/README.md and the reproducible yoke-1.15.patch. Global installation and runtime DLLs are untouched. Use node .yoke/tooling/yoke/dist/cli.js for the supervised loop. No guard is bypassed.

Code intelligence: active Yoke facade, Graphify is installed; Graft/Serena are not on PATH. Request code_context and inspect provenance/warnings. Use bounded AST/rg fallback for unavailable semantic backends and never claim complete references. Graphify code-only extraction is local, with no API calls.

Review all stories independently in Yoke. Run full tests at each gate. At completion inspect saved workflows, PowerShell parse checks and feasible GPU/UI smoke tests. Record exact limitations in final handoff.
