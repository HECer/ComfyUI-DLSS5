[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$comfyRoot = (Resolve-Path (Join-Path $repo "..\..")).Path
$candidates = @(
    (Join-Path (Split-Path $comfyRoot -Parent) "python_embeded\python.exe"),
    (Join-Path $comfyRoot "python_embeded\python.exe"),
    (Join-Path $comfyRoot ".venv\Scripts\python.exe")
)
$python = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { $python = $command.Source }
}
if (-not $python) {
    throw "Could not locate ComfyUI Python. Run install_runtime.py with the Python executable that launches ComfyUI."
}

& $python (Join-Path $repo "install_runtime.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
