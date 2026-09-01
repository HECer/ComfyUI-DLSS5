# Local runtime directory

This directory is intentionally empty in source control and Registry packages.
`setup.ps1` writes a local `config.json` and copies the runtime files selected by the user.

For the simplest installation:

1. Queue **DLSS Runtime Setup (One Click)** with `Check location` to display this directory.
2. Put your authorized `nvngx_dlssnr.dll` in this directory.
3. Select `Install verified VapourKit`, enable its confirmation control, and queue the setup node again.
4. Restart ComfyUI and check the Runtime Status node.

The one-click installer downloads only the pinned VapourKit nightly, verifies its SHA-256, and writes `config.json`. Downloaded and extracted runtime files remain ignored by Git and the Registry package.

Never commit NVIDIA DLLs, patched DLLs, executables, API keys, or machine-specific `config.json` files.
