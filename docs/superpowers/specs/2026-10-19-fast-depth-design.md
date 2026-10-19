# Selectable fast depth guides

The target is 3840x2160 output at more than 30 processed source frames per second on an RTX 5090. This is a measured end-to-end throughput target, including guide generation and native SR/NR; frame generation does not count as faster processing. For 2x SR the reference input is 1920x1080. Native 4K input with NR alone is a separate case. Neither target is established by upstream model timings.

The user approved continuing with optional YOLO26 Nano/Small depth, selectable DA-V2 precision/resolution, English help and unchanged legacy defaults. A new Depth Guide node exposes DA-V2 Small/Base/Large, YOLO26 Nano/Small and VDA Small through one selector. Easy gains optional overrides; its omitted controls retain its exact prior model and motion settings. Existing DA-V2 gains optional inference controls without changing required fields.

## Acceptance criteria

1. Preserve all existing node IDs, required input order, dropdown values/defaults and outputs. Append new optional controls with legacy defaults; register the new node separately.
2. Explain each model in English: purpose, speed/detail tradeoff, temporal behavior, first-use downloads and optional dependencies. Expose the actual selection in execution reports and a model-information output. Never silently fall back to another model.
3. DA-V2 supports native preprocessing or explicit input size and FP32/FP16 autocast. Omitted options reproduce legacy calls. CPU requests for FP16 use FP32 and report this. Model caching remains shared with existing DA-V2.
4. Optional YOLO uses official Nano/Small checkpoints, bounded batches, lazy dependency loading, cancellation and progress. Missing or old Ultralytics fails before checkpoint download with actionable setup guidance. Dependencies and Torch are never installed or upgraded during execution.
5. Convert YOLO metric depth into the existing near-bright inverse-depth guide convention before robust normalization. Preserve shape, chronology, float32 range [0,1] and output device; reject invalid/nonfinite model output. A local TensorRT engine is optional and must be explicitly selected, exist and run on CUDA.
6. Easy offers explicit depth and motion overrides. Temporal stabilization remains enabled for video. Existing numerical presets, native bridge settings and DLLs remain unchanged.
7. Commit a benchmark CLI that measures warmups and repeated synchronized runs, reports sample count/range, source and output sizes, selected controls, stage timings and end-to-end source FPS, and fails the >30 FPS gate when measured results miss it. Downloads and cold setup are reported separately. No available CUDA/native runtime means unverified, not a passing gate.
8. Run behavioral tests, saved-workflow/schema compatibility checks, the full existing suite, feasible real-model/native checks and an independent read-only review. Report remaining throughput and quality limitations explicitly.

## Alternatives considered

- Optimized DA-V2 alone is the least disruptive route and retains established guides, but does not add a materially smaller architecture.
- YOLO26 Nano/Small is the preferred speed experiment. Official TensorRT FP16 model-only timings on T4 are 2.73/3.82 ms at 768, versus 20.99 ms for DA-V2 Small at 770. These are not local or end-to-end results. Ultralytics uses AGPL-3.0; deployments must review its published license terms.
- VDA Small remains the temporal option. oVDA is a future integration candidate (42 FPS on A100 in its paper). FlashDepth is already external and reports about 24 FPS at 2044x1148 on A100; its current adapter also encodes/decodes temporary video. Neither establishes 4K/30 here.

## Sources checked on 2026-10-19

- https://docs.ultralytics.com/tasks/depth
- https://github.com/ultralytics/ultralytics/blob/main/LICENSE
- https://github.com/DepthAnything/Video-Depth-Anything
- https://github.com/Eyeline-Labs/FlashDepth
- https://github.com/FriedFeid/OnlineVideoDepthAnything
- https://arxiv.org/abs/2510.09182

## Limits

This change exposes and measures guide choices. If native initialization, NPY I/O, CPU motion or stabilization dominates, a persistent GPU pipeline requires a separately measured follow-up. No resolution, precision or model change can be called visually equivalent without representative video comparison, including scene cuts, disocclusions, thin geometry and fast motion.
