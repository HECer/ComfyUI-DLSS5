# Troubleshooting

## Runtime Status says NOT READY

Run `setup.ps1` again and inspect `runtime/config.json`. Every configured path must exist. Keep the extracted VapourKit directory in the selected location.

## `No module named vapoursynth`

The configured `python` must be VapourKit's VapourSynth-capable interpreter, not regular ComfyUI Python.

## Missing guide-model dependencies

Install `requirements.txt` with the Python executable that launches ComfyUI. Portable installations commonly use `python_embeded\python.exe` beside ComfyUI.

## The first run appears stuck

Depth Anything V2 and RAFT may download weights. Check network access, model caches, console output, and free disk space.

## Out of memory in persistent mode

`Persistent full sequence` preserves one native context, but ComfyUI still holds the full IMAGE batch. Try a shorter clip, lower resolution, `Bounded overlap-add`, a larger page file, and a temporary drive with more free space.

## Periodic brightness or detail changes

Confirm persistent mode, or use bounded mode with overlap. Motion must be current-to-previous, Temporal Depth Stabilizer should be connected, depth should use temporal normalization, and the loader must not duplicate frames unexpectedly.

## Ghosting or depth trails

Lower depth-stabilizer `strength` or `disocclusion_threshold`, inspect RAFT flow, and reset processing at hard scene cuts.

## Output differs from games

This extension estimates depth and motion from pixels. Games provide geometry, jitter, exposure, material buffers, and engine-specific resources.

## Processing never returns

The default native timeout is disabled so long clips are not killed after five minutes. Cancel through ComfyUI first. Verify a process command line before terminating an external bridge manually.

## Bug reports

Provide redacted Runtime Status, console traceback, workflow JSON, expected and actual frame count/resolution/FPS, and runtime hashes. Do not attach proprietary DLLs or private media.
