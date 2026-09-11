# Troubleshooting

## Runtime Status says NOT READY

Run `setup.ps1` again and inspect `runtime/config.json`. Every configured path must exist. The setup expects the bundled wrappers and NVIDIA runtimes: `runtime/vsdlssnr.dll`, `runtime/vsdlsssr.dll`, `runtime/nvngx_dlss.dll`, and `runtime/nvngx_dlssnr.dll`. It keeps the extracted VapourKit directory in the selected location.

If an older clone reports that `vsdlsssr.dll` is missing below VapourKit, update the extension first. The SR wrapper is bundled by this project; it is not a VapourKit file.

If a bundled NVIDIA runtime is missing, update/re-extract the repository package. You can deliberately override the SR or NR runtime with `-SRRuntimeDll` or `-NeuralRuntimeDll`.

If `runtime/nvngx_dlssnr.dll` is only a small text pointer, install Git LFS (`git lfs install`) and run `git lfs pull` from the repository root, then run setup again.

## `No module named vapoursynth`

The configured `python` must be VapourKit's VapourSynth-capable interpreter, not regular ComfyUI Python.

## Missing guide-model dependencies

Install `requirements.txt` with the Python executable that launches ComfyUI. Portable installations commonly use `python_embeded\python.exe` beside ComfyUI.

## The first run appears stuck

Depth Anything V2 and RAFT may download weights. Check network access, model caches, console output, and free disk space.

## Out of memory in persistent mode

`Persistent full sequence` preserves one native context per selected stage. Try a shorter clip, lower resolution, `Bounded overlap-add`, a larger page file, and a temporary drive with more free space. Bounded mode limits each native window to `chunk_size + history_overlap` frames; the complete ComfyUI IMAGE input and output still reside in memory. Easy's Long video and Fast preview presets apply bounded windows to all operations, with maximum windows of 24 and 10 frames respectively.

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
