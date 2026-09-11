# Example workflows

Complete the [installation and base runtime check](../README.md#first-run-install-check-make-an-image) first. Base SR/NR setup is repeatable and preserves custom configuration; optional Frame Generation has a separate install action. All video examples require Video Helper Suite for loading. Workflows 02, 03 and 06 include an encoder; 04 and 05 end in Preview Image, so connect a video encoder yourself and set the source FPS before exporting.

## 00 — Easy one-node 2x

Import [00_easy_one_node_2x.json](00_easy_one_node_2x.json), select your own image in Load Image, and queue the default settings. Inspect the 2x preview and the Save Image result under ComfyUI's output directory with prefix `DLSS5/easy-2x`.

Easy uses Depth Anything V2 Small (DA-V2) for every scenario, with first-use weight downloads. A still uses zero motion; video presets use optical flow or RAFT and temporal depth stabilization. VDA is a separate model in workflow 04, not an automatic Easy substitution. Easy preflights only the selected SR/NR stages before guide work. Scale and quality are inactive for Neural rendering only; look and effect strength are inactive for Upscale only.

Long video uses up to 24 frames per native window; Fast preview uses up to 10, for all operations. Only native windows are bounded: the complete ComfyUI IMAGE input and output remain in memory. Easy's report shows the resolved scenario, active settings, dimensions, frame counts and advisory storage estimate. Follow ComfyUI progress and console output; cancel through ComfyUI. SR/NR children are stopped before cleanup. Optional VDA/FlashDepth progress and cancellation occur at stage boundaries. See [memory and cancellation details](../README.md#progress-cancellation-and-storage-advice).

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

Select `Install verified Frame Generation` in Runtime Setup and enable confirmation to install the separate optional worker, as documented in
[`runtime/README.md`](../runtime/README.md). Base installation does not download it. Run **DLSS Frame Generation Runtime Status** first. Hard scene cuts
reset DLSS-G history and hold the preceding source frame to preserve duration.
Missing runtime output fails the workflow by default; use the hold fallback only when
you deliberately prefer constant duration over smooth interpolation.

All workflows contain explanatory node titles, group labels, and machine-readable notes in `extra.release_notes` or `notes`.
