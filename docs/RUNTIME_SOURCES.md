# Runtime sources and legal notes

This extension contains no NVIDIA runtime DLLs. Its setup script expects files that you obtained separately and are authorized to use.

## VapourKit

- Project: <https://github.com/Kim2091/vapourkit>
- Nightly builds: <https://github.com/Kim2091/vapourkit-nightly/releases>
- License: GPL-3.0 for the VapourKit project; bundled third-party components may use other licenses.

The tested environment used a VapourKit nightly containing `vsdlsssr.dll`, `vsdlssnr.dll`, a VapourSynth-capable Python runtime, and `nvngx_dlss.dll`. Nightlies are pre-releases and may change without compatibility guarantees.

## NVIDIA DLSS

- Official SDK repository: <https://github.com/NVIDIA/DLSS>
- NVIDIA developer page: <https://developer.nvidia.com/rtx/dlss>

Read NVIDIA's license files before copying, modifying, or redistributing any SDK or runtime component.

## Neural-rendering runtime

`nvngx_dlssnr.dll` is not distributed here. This project does not endorse download mirrors, leaked game files, DRM bypass tools, or redistribution of proprietary binaries. The bridge requests the VapourKit wrapper's caller-check compatibility option; it does not modify the proprietary DLL. You are responsible for confirming that this mode and your runtime source are permitted by the applicable licenses and terms.

The setup script accepts a local path because users may possess the runtime under different legitimate terms. You are responsible for determining whether your source and use are authorized.

## Models

- Depth Anything V2: <https://huggingface.co/depth-anything>
- TorchVision RAFT: <https://pytorch.org/vision/stable/models/raft.html>

Review each model card, dataset statement, and license. Caching a model locally does not grant redistribution rights.

## Compatibility reports

Include GPU, driver, Windows, ComfyUI, PyTorch/CUDA, input dimensions, processing mode, and SHA-256 hashes for all four runtime DLLs. Never upload proprietary DLLs to an issue.
