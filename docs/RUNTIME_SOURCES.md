# Runtime sources and legal notes

This extension contains no NVIDIA runtime DLLs. Its setup script expects files that you obtained separately and are authorized to use.

## VapourKit

- Project: <https://github.com/Kim2091/vapourkit>
- Nightly builds: <https://github.com/Kim2091/vapourkit-nightly/releases>
- Tested nightly: <https://github.com/Kim2091/vapourkit-nightly/releases/tag/nightly-2026-08-31>
- Community/support Discord: <https://discord.gg/uYKMn2hGwB>
- License: GPL-3.0 for the VapourKit project; bundled third-party components may use other licenses.

The tested environment used a VapourKit nightly containing `vsdlsssr.dll`, `vsdlssnr.dll`, a VapourSynth-capable Python runtime, and `nvngx_dlss.dll`. Nightlies are pre-releases and may change without compatibility guarantees.

The Discord invite is linked by the VapourKit project. Treat it as a community and support channel. A file attached by an individual member is not automatically an official release, integrity guarantee, or grant of redistribution rights.

## NVIDIA DLSS

- Official SDK repository: <https://github.com/NVIDIA/DLSS>
- NVIDIA developer page: <https://developer.nvidia.com/rtx/dlss>

Read NVIDIA's license files before copying, modifying, or redistributing any SDK or runtime component.

## Neural-rendering runtime

`nvngx_dlssnr.dll` is not distributed here. This project does not endorse download mirrors, leaked game files, DRM bypass tools, or redistribution of proprietary binaries. The bridge requests the VapourKit wrapper's caller-check compatibility option; it does not modify the proprietary DLL. You are responsible for confirming that this mode and your runtime source are permitted by the applicable licenses and terms.

The setup script accepts a local path because users may possess the runtime under different legitimate terms. You are responsible for determining whether your source and use are authorized.

At the time of this release, we did not identify a generally available official NVIDIA download specifically for `nvngx_dlssnr.dll`. A Reddit post, mod guide, DLL database, game-mod archive, or matching filename is not an integrity or license guarantee. This project therefore does not provide a download link for that proprietary file.

## Models

- Depth Anything V2: <https://huggingface.co/depth-anything>
- TorchVision RAFT: <https://pytorch.org/vision/stable/models/raft.html>

These weights are fetched automatically on first use. For offline systems, download them through the respective Hugging Face/PyTorch mechanisms on a connected machine and transfer the caches in accordance with their licenses.

## Optional DLSS Frame Generation backend

The Frame Generation nodes use a separately installed `dlssg-worker.exe` and
`nvngx_dlssg.dll` in `runtime/dlssg/`. The binary protocol follows the public Python
client in [Merserk/dlss5-visual-enhancer](https://github.com/Merserk/dlss5-visual-enhancer),
which is MIT-licensed. Its release documentation identifies the worker as a project-built
binary, but the native worker source is not present in that repository. This extension
therefore does not download, copy, or redistribute the worker.

- Reference client and releases: <https://github.com/Merserk/dlss5-visual-enhancer/releases>
- Official NVIDIA Streamline DLSS-G integration guide: <https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDLSS_G.md>

Obtain NVIDIA components from an official SDK, driver, or licensed application source.
Keep the worker and its matching runtime together, record their SHA-256 hashes, and run
the capability-status node before processing media. The upstream integration targets
Windows 11, Direct3D 12, a supported RTX 40- or 50-series GPU, and a compatible driver;
it also recommends Hardware-accelerated GPU scheduling.

## Optional video workflow dependency

- ComfyUI-VideoHelperSuite: <https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite>

It supplies the video loader and encoder nodes used by workflows 02 and 03. It is not needed for still-image workflows or when another node pack supplies compatible IMAGE batches and video output.

## Not required

ReShade (<https://reshade.me/>), game injectors, DLSS override tools, Nexus mods, and game-specific mod guides are not required by this ComfyUI extension and are not recommended as runtime sources.

Review each model card, dataset statement, and license. Caching a model locally does not grant redistribution rights.

## Compatibility reports

Include GPU, driver, Windows, ComfyUI, PyTorch/CUDA, input dimensions, processing mode, and SHA-256 hashes for all four runtime DLLs. Never upload proprietary DLLs to an issue.
