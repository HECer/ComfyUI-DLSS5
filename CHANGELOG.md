# Changelog

## 0.3.1 — 2026-09-04

- Replaced the undocumented Frame Generation worker recommendation with the
  open-source [HECer/DLSSG-Stream-Worker](https://github.com/HECer/DLSSG-Stream-Worker).
- Added a pinned, SHA-256-verified worker download to the runtime installer.
- Kept `nvngx_dlssg.dll` manual and outside the extension package.
- Validated the new worker through the existing RTX 5090 ComfyUI integration test.

## 0.3.0 — 2026-09-04

- Added optional DLSS Frame Generation and capability-status nodes.
- Added a persistent external-worker protocol with timestamps, scene resets, and exact
  output-frame accounting.
- Added fail-fast handling for incomplete interpolation, with an explicit duration-preserving hold fallback.
- Added a 24-to-48 fps ComfyUI workflow using RAFT motion guides.
- Added full-workflow and node-detail screenshots for the Frame Generation path.
- Fixed widget serialization in the Frame Generation workflow for current ComfyUI frontends.
- Kept the native worker and NVIDIA Frame Generation runtime outside the package.

## 0.1.1

- Added Registry and README branding with a square, small-size-readable project icon.

## 0.1.0 documentation update

- Added direct, component-by-component source links and clarified which downloads are automatic, optional, or user-supplied.
- Documented the exact VapourKit nightly used during development.
- Added a Manager-friendly one-click runtime installer with a pinned URL and SHA-256 verification; only `nvngx_dlssnr.dll` remains user-supplied.
- Exposed runtime installation as a ComfyUI output node, so the recommended setup requires no terminal.
- Replaced the previous documentation image with an Alyx comparison as the README hero.
- Added full-size ComfyUI screenshots for the Easy and Advanced workflows, including readable node-detail views.
- Added the official GitHub Actions publishing workflow for Comfy Registry and ComfyUI Manager distribution.

## 0.1.0-alpha

- Initial public alpha package.
- DLSS Super Resolution and experimental neural-rendering nodes.
- Depth Anything V2, backward RAFT motion, and temporal depth stabilization.
- Persistent full-sequence contexts and bounded overlap-add fallback.
- Memory-mapped bridges and chunked guide preparation.
- One-time local runtime setup without NVIDIA DLL redistribution.
