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

## Optional DLSS Frame Generation

Frame Generation uses an external native worker. Put these two matching files in
`runtime/dlssg/`:

- `dlssg-worker.exe`
- `nvngx_dlssg.dll`

The extension does not download or distribute either file. The worker protocol is
compatible with the public Python client in
<https://github.com/Merserk/dlss5-visual-enhancer>. Its native worker source is not
part of that repository, so verify the binary and confirm your right to use it.
The reference project's downloads are listed at
<https://github.com/Merserk/dlss5-visual-enhancer/releases>.
Run **DLSS Frame Generation Runtime Status** before processing a video.
