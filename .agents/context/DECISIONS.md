# Decisions

> Append-only ledger. Agents add entries for non-obvious decisions made during work.
> Newest at the bottom.

## 2026-09-11 — DLSS-1: Repeatable setup and configuration preservation
route=codex-frontier (gate failure escalated by project rule); codex implemented DLSS-1

## 2026-09-11 — DLSS-2: Separate optional Frame Generation installation
Supervisor verified the retained DLSS-2 implementation after the explicit checkpoint; no new implementation model call was made.

## 2026-09-11 — DLSS-3: Node descriptions and backward-compatible navigation
route=codex-standard (explicit project routing rule); codex implemented DLSS-3

## 2026-09-11 — DLSS-4: Truthful runtime diagnostics and early preflight
route=codex-frontier (explicit project routing rule); codex implemented DLSS-4

## 2026-09-11 — DLSS-5: Honor bounded mode for all Easy operations
route=codex-frontier (explicit project routing rule); codex implemented DLSS-5

## 2026-09-11 — DLSS-6: Progress, responsive cancellation and advisory memory estimates
route=codex-frontier (explicit project routing rule); codex implemented DLSS-6

## 2026-09-11 — DLSS-7: Concise first-run guide and integrated regression evidence
route=codex-frontier (explicit project routing rule); codex implemented DLSS-7

## 2026-10-19 — Fast depth: Explicit model choices preserve legacy defaults
Add a unified depth guide with optional YOLO26 Nano/Small and optional Easy depth/motion overrides. Keep omitted Easy and DA-V2 controls numerically unchanged. The user targets 4K output above 30 source FPS on RTX 5090; distinguish guide throughput, complete node processing and complete video-file processing.

## 2026-10-19 — Fast depth: Bound preprocessing and intermediate GPU memory
YOLO preprocessing first resizes on the inference device to limit CPU work; normalize scalar depth in bounded batches and accumulate raw maps on CPU. Preserve full-size outputs and frame-relative motion units. Disable Ultralytics automatic package installation before imports and in cached dependency checkers; optional execution must never replace the host's dependencies.

## 2026-10-25 — release: 0.5.0 Experimental Preview
The user authorized deployment after the preview limitations were disclosed. Use the existing three-part pyproject version convention, tag GitHub v0.5.0 as a pre-release, and publish Registry version 0.5.0 with explicit experimental/failed-4K30 wording. Preserve all runtime/model numerical defaults. Resolve/verify LFS before publishing directly through the tested Comfy CLI, because the composite action performs another checkout without LFS.
