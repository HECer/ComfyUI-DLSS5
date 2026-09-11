# Troubleshooting

## Base runtime diagnostics report FAIL, MISSING or LFS POINTER

Re-queue **DLSS 5 Runtime Status** after a repair to refresh its display. `PRESENT` only confirms a file exists. Separate probes execute Python, import VapourSynth and NumPy, and load SR/NR plugins. `Inference: UNTESTED` is expected even when preflight passes: no GPU image has been rendered. Easy runs these checks for only its selected SR/NR stages before loading guide models.

Inspect `runtime/config.json` and any `DLSS5_` environment overrides. Every configured path must exist. The setup expects the bundled wrappers and NVIDIA runtimes: `runtime/vsdlssnr.dll`, `runtime/vsdlsssr.dll`, `runtime/nvngx_dlss.dll`, and `runtime/nvngx_dlssnr.dll`. It keeps the extracted VapourKit directory in the selected location. A plugin-load failure can indicate a wrapper, VapourSynth ABI or dependent-DLL problem; a passing load still does not prove inference works with your GPU/driver.

If an older clone reports that `vsdlsssr.dll` is missing below VapourKit, update the extension first. The SR wrapper is bundled by this project; it is not a VapourKit file.

If a bundled NVIDIA runtime is missing, update/re-extract the repository package. You can deliberately override the SR or NR runtime with `-SRRuntimeDll` or `-NeuralRuntimeDll`.

If `runtime/nvngx_dlssnr.dll` is only a small text pointer, install Git LFS (`git lfs install`) and run `git lfs pull` from the repository root, then run setup again.

## Re-running setup or fixing configuration

Repeat setup with the same paths. It preserves custom settings and an existing correct junction; a conflicting directory is reported without replacing it. UTF-8 JSON with or without a BOM is supported. Invalid JSON or a value other than an object fails with the config path; preserve the original and correct it before retrying. Automatic setup preserves a working NumPy version and installs missing NumPy only in its isolated VapourKit interpreter.

## Optional Frame Generation says NOT READY

Base SR/NR installation does not require or download the FG worker. Select `Install verified Frame Generation` in **DLSS Runtime Setup (One Click)**, enable `confirm_download` and queue it separately. Then run **DLSS Frame Generation Runtime Status**. See [runtime setup](../runtime/README.md) for the worker/runtime pair and [runtime sources](RUNTIME_SOURCES.md) for requirements. The FG status output is separate from base SR/NR diagnostics.

## `No module named vapoursynth`

The configured `python` must be VapourKit's VapourSynth-capable interpreter, not regular ComfyUI Python.

For `No module named numpy`, run the selected bridge interpreter with `-m pip install numpy==2.5.2`, then re-check status. The automatic `Install verified VapourKit` action configures its own isolated runtime; it does not repair an external VapourKit interpreter. Do not replace ComfyUI's Torch environment.

## Missing guide-model dependencies

Install `requirements.txt` with the Python executable that launches ComfyUI. Portable installations commonly use `python_embeded\python.exe` beside ComfyUI.

## The first run appears stuck

Easy downloads Depth Anything V2 Small (DA-V2) on first use and RAFT weights for video quality presets. Check network access, model caches, console output, and free disk space. Easy continues to use DA-V2 for video; VDA is the separate Video Depth Anything model in [workflow 04](../workflows/04_video_vda_small_temporal_2x.json), with its own first-use source/weights downloads.

ComfyUI progress advances through guide work and native SR/NR frames/windows. Downloads and individual model calls may take time between updates. VDA and FlashDepth provide stage-boundary progress, not per-frame progress inside their model calls.

## Out of memory in persistent mode

`Persistent full sequence` preserves one native context per selected stage. Try a shorter clip, lower resolution, `Bounded overlap-add`, a larger page file, and a temporary drive with more free space. Bounded mode limits each native window to `chunk_size + history_overlap` frames; the complete ComfyUI IMAGE input and output still reside in memory. Easy's Long video and Fast preview presets apply bounded windows to all operations, with maximum windows of 24 and 10 frames respectively.

Easy's `Storage advice` is an advisory estimate of float32 array and peak temporary payloads, printed before guides and included in its report. It excludes additional working copies, model weights and file/log overhead, and is not a full VRAM prediction. A disk warning does not reduce your selected settings. Full-batch guides and ComfyUI input/output can still exhaust RAM in bounded mode.

## Periodic brightness or detail changes

Confirm persistent mode, or use bounded mode with overlap. Motion must be current-to-previous, Temporal Depth Stabilizer should be connected, depth should use temporal normalization, and the loader must not duplicate frames unexpectedly.

## Ghosting or depth trails

Lower depth-stabilizer `strength` or `disocclusion_threshold`, inspect RAFT flow, and reset processing at hard scene cuts.

## Output differs from games

This extension estimates depth and motion from pixels. Games provide geometry, jitter, exposure, material buffers, and engine-specific resources.

## Processing never returns

The default SR/NR native timeout is disabled so long clips are not killed after five minutes. Cancel through ComfyUI first: the bridge polls for interruption, terminates the SR/NR child (kills it if needed), waits for it, then cleans temporary files. Guide loops check between work units; optional VDA/FlashDepth check at stage boundaries and may need to finish the active model call. Verify a process command line before terminating an external bridge manually.

## Bug reports

Provide redacted Runtime Status, console traceback, workflow JSON, expected and actual frame count/resolution/FPS, and runtime hashes. Do not attach proprietary DLLs or private media.
