# Local runtime directory

This directory is intentionally empty in source control and Registry packages.
`setup.ps1` writes a local `config.json` and copies the runtime files selected by the user.

For the simplest installation:

1. Queue **DLSS Runtime Setup (One Click)** with `Check location` to display this directory.
2. Put your authorized `nvngx_dlssnr.dll` in this directory.
3. Select `Install verified VapourKit`, enable its confirmation control, and queue the setup node again.
4. Restart ComfyUI and check the Runtime Status node.

The one-click installer downloads the pinned VapourKit nightly and the open-source
DLSS-G worker, verifies both SHA-256 hashes, and writes `config.json`. Downloaded
and extracted runtime files remain ignored by Git and the Registry package.

Never commit NVIDIA DLLs, patched DLLs, executables, API keys, or machine-specific `config.json` files.

## Optional DLSS Frame Generation

Frame Generation uses the open-source native worker from
<https://github.com/HECer/DLSSG-Stream-Worker>. Put these two matching files in
`runtime/dlssg/`:

- `dlssg-worker.exe`
- `nvngx_dlssg.dll`

`install_runtime.py` downloads the pinned worker release and verifies its SHA-256
hash. The extension does not download or distribute `nvngx_dlssg.dll`; copy that
file manually from software you legally obtained. Source, build instructions, and
the wire protocol are published with the worker repository.
Run **DLSS Frame Generation Runtime Status** before processing a video.
