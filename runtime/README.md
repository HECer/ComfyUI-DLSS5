# Local runtime directory

The source package includes the two project-specific VapourSynth wrappers:
`vsdlssnr.dll` and `vsdlsssr.dll`, plus the NVIDIA runtimes used by the tested
setup: `nvngx_dlss.dll`, `nvngx_dlssnr.dll`, and
`dlssg/nvngx_dlssg.dll`. Setup uses these files directly; `config.json` and the
downloaded VapourKit/worker files remain machine-local.

For the simplest installation:

1. Queue **DLSS Runtime Setup (One Click)** with `Check location` to display this directory.
2. Select `Install verified VapourKit`, enable its confirmation control, and queue the setup node again. This installs the SR/NR base runtime: bundled wrappers, verified NVIDIA SR/NR runtimes, and VapourKit's Python with NumPy. Existing working NumPy versions and custom configuration are preserved.
3. Restart ComfyUI and check the Runtime Status node.
4. For optional Frame Generation, select `Install verified Frame Generation`, enable confirmation, and queue the setup node. This separately verifies the FG runtime and downloads the pinned worker.

The base installer verifies the SR/NR runtime hashes, downloads the pinned
VapourKit nightly when needed, checks its isolated NumPy dependency, and writes
`config.json`. It does not require or download Frame Generation components.
Downloaded and extracted runtime files remain ignored by Git and the Registry
package.

The five runtime DLLs listed above are intentionally tracked project assets.
Never add other NVIDIA DLLs, patched DLLs, executables, API keys, or
machine-specific `config.json` files without recording their exact provenance
and license.

Bundled runtime hashes (SHA-256):

- `vsdlssnr.dll`: `1dc73894c4ce3294068bea42217c9bc6f610ea006dc351a6f6c1546431213d52`
- `vsdlsssr.dll`: `30f59085370ac3da0b307683333c2310c18c07af0cc2331df5bd01a257be74c1`
- `nvngx_dlss.dll`: `be6e434a94ca32499515eb62ca0e6c274526055d568d0426e4c652dcdfb6ee6e`
- `nvngx_dlssnr.dll`: `8270b350cd82de5ce89806872cdd6b6a9249b80836b91bbeb3573470744cc206`
- `dlssg/nvngx_dlssg.dll`: `c64928fdb7c48a57722ea8eef2662171edc323473adea66c29a206a23f1a2bed`

## Optional DLSS Frame Generation

Frame Generation uses the open-source native worker from
<https://github.com/HECer/DLSSG-Stream-Worker>. Put these two matching files in
`runtime/dlssg/`:

- `dlssg-worker.exe`
- `nvngx_dlssg.dll`

Run `python install_runtime.py --install-frame-generation` or
`./install_runtime.ps1 -InstallFrameGeneration` to download the pinned worker
release and verify its SHA-256 hash. Without that flag, the installer sets up only
the SR/NR base runtime. The matching `nvngx_dlssg.dll` is included above. Source, build
instructions, and the wire protocol are published with the worker repository.
Run **DLSS Frame Generation Runtime Status** before processing a video.
