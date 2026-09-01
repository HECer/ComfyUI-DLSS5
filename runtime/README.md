# Local runtime directory

This directory is intentionally empty in source control and Registry packages.
`setup.ps1` writes a local `config.json` and copies the runtime files selected by the user.

Never commit NVIDIA DLLs, patched DLLs, executables, API keys, or machine-specific `config.json` files.
