# Example workflows

## 00 — Easy one-node 2x

The recommended first run. Connect an image to the Easy node, select a scenario, and run. The node automatically builds depth and motion guides; the other workflows expose those stages for inspection and customization.

## 01 — Still image, guided 2x

Core ComfyUI plus this extension. Demonstrates estimated depth, a zero-motion still guide, DLSS Super Resolution, and neural rendering.

## 02 — Persistent video, guided 2x

Requires [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite). Uses Depth Anything V2 Small, RAFT Large, temporal depth stabilization, one persistent SR context, and one persistent NR context.

Set the video encoder FPS to the source FPS. The included value is 24 fps only as an example.

## 03 — Bounded overlap-add video, guided 2x

An independently importable variant of workflow 02 for longer sequences. It limits the native runtime working set with overlapping windows and blends their output. Raise `history_overlap` if a periodic boundary remains visible.

## 04 — Video Depth Anything Small, temporal 2x

Recommended video workflow. It replaces framewise depth plus post-stabilization with the official Apache-2.0 VDA-S temporal model. The first run downloads pinned source and official weights. RAFT still supplies current-to-previous motion vectors.

## 05 — FlashDepth high-resolution, temporal 2x

Optional expert workflow for high-resolution footage. FlashDepth runs in an isolated Torch 2.4 environment so it cannot alter ComfyUI's CUDA stack. Complete [`docs/FLASHDEPTH.md`](../docs/FLASHDEPTH.md) before queueing it.

## 06 — DLSS Frame Generation 2x

Loads a video as an image batch, calculates current-to-previous RAFT motion, and inserts
one DLSS-G frame between consecutive source frames. Set both the DLSS-G node and encoder
to the correct source and output rates. The included example uses 24 to 48 fps.

This workflow requires the optional external files documented in
[`runtime/README.md`](../runtime/README.md). Test the status node first. Hard scene cuts
reset DLSS-G history and hold the preceding source frame to preserve duration.
Missing runtime output fails the workflow by default; use the hold fallback only when
you deliberately prefer constant duration over smooth interpolation.

All workflows contain explanatory node titles, group labels, and machine-readable notes in `extra.release_notes` or `notes`.
