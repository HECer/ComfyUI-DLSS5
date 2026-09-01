[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $ComfyUIPath,
    [Parameter(Mandatory = $true)] [string] $VapourKitPath,
    [Parameter(Mandatory = $true)] [string] $NeuralRuntimeDll,
    [string] $TempDirectory = ""
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$comfy = (Resolve-Path -LiteralPath $ComfyUIPath).Path
$vapourKit = (Resolve-Path -LiteralPath $VapourKitPath).Path
$nrRuntime = (Resolve-Path -LiteralPath $NeuralRuntimeDll).Path

if ([IO.Path]::GetFileName($nrRuntime) -ne "nvngx_dlssnr.dll") {
    throw "NeuralRuntimeDll must point to nvngx_dlssnr.dll."
}

function Find-One([string] $Root, [string] $Name) {
    $matches = @(Get-ChildItem -LiteralPath $Root -Filter $Name -File -Recurse -ErrorAction SilentlyContinue)
    if ($matches.Count -eq 0) { throw "Could not find $Name below $Root" }
    if ($matches.Count -gt 1) { Write-Warning "Multiple $Name files found; using $($matches[0].FullName)" }
    return $matches[0].FullName
}

function Find-VapourPython([string] $Root) {
    $candidates = @(Get-ChildItem -LiteralPath $Root -Filter "python.exe" -File -Recurse -ErrorAction SilentlyContinue)
    foreach ($candidate in $candidates) {
        & $candidate.FullName -c "import vapoursynth" 2>$null
        if ($LASTEXITCODE -eq 0) { return $candidate.FullName }
    }
    throw "Could not find a Python interpreter with VapourSynth below $Root"
}

$vsPython = Find-VapourPython $vapourKit
$nrPlugin = Find-One $vapourKit "vsdlssnr.dll"
$srPlugin = Find-One $vapourKit "vsdlsssr.dll"
$srRuntime = Find-One $vapourKit "nvngx_dlss.dll"

$runtimeDir = Join-Path $repo "runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
Copy-Item -LiteralPath $nrRuntime -Destination (Join-Path $runtimeDir "nvngx_dlssnr.dll") -Force
Copy-Item -LiteralPath $nrPlugin -Destination (Join-Path $runtimeDir "vsdlssnr.dll") -Force
Copy-Item -LiteralPath $srPlugin -Destination (Join-Path $runtimeDir "vsdlsssr.dll") -Force
Copy-Item -LiteralPath $srRuntime -Destination (Join-Path $runtimeDir "nvngx_dlss.dll") -Force

if (-not $TempDirectory) {
    $TempDirectory = Join-Path ([IO.Path]::GetTempPath()) "comfyui-dlss5"
}
New-Item -ItemType Directory -Force -Path $TempDirectory | Out-Null

$config = [ordered]@{
    python = $vsPython
    nr_plugin = (Join-Path $runtimeDir "vsdlssnr.dll")
    nr_runtime = (Join-Path $runtimeDir "nvngx_dlssnr.dll")
    sr_plugin = (Join-Path $runtimeDir "vsdlsssr.dll")
    sr_runtime = (Join-Path $runtimeDir "nvngx_dlss.dll")
    temp_dir = (Resolve-Path -LiteralPath $TempDirectory).Path
    timeout_seconds = 0
}
$config | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir "config.json") -Encoding utf8

$customNodes = Join-Path $comfy "custom_nodes"
New-Item -ItemType Directory -Force -Path $customNodes | Out-Null
$repoParent = Split-Path $repo -Parent
if ([IO.Path]::GetFileName($repoParent) -ieq "custom_nodes") {
    $installPath = $repo
} else {
    $installPath = Join-Path $customNodes "ComfyUI-DLSS5"
    if (Test-Path -LiteralPath $installPath) {
        throw "$installPath already exists. Remove or rename it, then run setup again."
    }
    New-Item -ItemType Junction -Path $installPath -Target $repo | Out-Null
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Extension: $installPath"
Write-Host "Runtime config: $(Join-Path $runtimeDir 'config.json')"
Write-Host "Temporary files: $TempDirectory"
Write-Host "Python dependencies are managed by ComfyUI Manager/Registry; manual clones must install requirements.txt once."
Write-Host "Restart ComfyUI, then run the 'DLSS 5 Runtime Status' node."
