# Selectable fast depth implementation plan

**Goal:** Expose useful depth-model alternatives with English explanations and measure progress toward 4K output above 30 source FPS.

**Architecture:** Keep native processing and legacy guide defaults. Add a small optional YOLO adapter in `depth_backend.py`, a unified guide node and optional Easy/DA-V2 controls in `nodes.py`. Use existing DA-V2 cache and VDA adapter. Expose reports as text without replacing image outputs.

**Tech stack:** Python, Torch, Transformers, optional Ultralytics/TensorRT, existing ComfyUI node schema, pytest.

## Execution

- [x] Add `tests/test_fast_depth.py` behavioral coverage for model routing, old defaults, YOLO metric-to-inverse depth conversion, invalid results, cancellation, cache and optional dependency failures. Run `python -m pytest tests/test_fast_depth.py -q`; confirm missing-feature failures before production edits.
- [x] Implement `depth_backend.py` with lazy, bounded YOLO inference and explicit local-engine support. Extend DA-V2 with optional `input_size=0` and `precision="FP32"`; leave its legacy call unchanged when options are omitted. Add `DLSS5DepthGuide` and append Easy overrides. Re-run focused tests to green.
- [x] Extend schema compatibility assertions to permit only named new optional inputs and the new node while retaining every baseline required field, output, ID and old dropdown. Add English `docs/FAST_DEPTH.md` and update README routing. Keep unit tests offline.
- [x] Add `tools/benchmark_fast_depth.py`: selectable source image or synthetic input, synchronized warmup/repeats, per-stage and end-to-end timing, JSON output and `--minimum-fps 30` strict gate. Verify CLI and timing/gate behavior with tests.
- [x] Run the full suite with the available test environment. Locate a CUDA environment; run real-model depth and native checks where possible, recording environment, input size, sample count, range and failures. Do not replace ComfyUI Torch or install packages into it.
- [x] Request an independent read-only reviewer for the exact diff and evidence; fix important findings with regression tests. Record any unavailable GPU/UI verification and whether the measured 4K/30 gate passed.

No push, PR or merge is part of this request. Existing unrelated worktree changes remain untouched.
