# Changelog

## 0.1.0 documentation update

- Added direct, component-by-component source links and clarified which downloads are automatic, optional, or user-supplied.
- Documented the exact VapourKit nightly used during development.
- Added a Manager-friendly one-click runtime installer with a pinned URL and SHA-256 verification; only `nvngx_dlssnr.dll` remains user-supplied.
- Exposed runtime installation as a ComfyUI output node, so the recommended setup requires no terminal.
- Replaced the previous documentation image with an Alyx comparison as the README hero.
- Added full-size ComfyUI screenshots for the Easy and Advanced workflows, including readable node-detail views.

## 0.1.0-alpha

- Initial public alpha package.
- DLSS Super Resolution and experimental neural-rendering nodes.
- Depth Anything V2, backward RAFT motion, and temporal depth stabilization.
- Persistent full-sequence contexts and bounded overlap-add fallback.
- Memory-mapped bridges and chunked guide preparation.
- One-time local runtime setup without NVIDIA DLL redistribution.
