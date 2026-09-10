[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $ComfyUIPath,
    [Parameter(Mandatory = $true)] [string] $VapourKitPath,
    [string] $NeuralRuntimeDll = "",
    [string] $SRRuntimeDll = "",
    [string] $TempDirectory = ""
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$comfy = (Resolve-Path -LiteralPath $ComfyUIPath).Path
$vapourKit = (Resolve-Path -LiteralPath $VapourKitPath).Path
$runtimeDir = Join-Path $repo "runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

if ($NeuralRuntimeDll) {
    $nrRuntime = (Resolve-Path -LiteralPath $NeuralRuntimeDll).Path
} else {
    $nrRuntime = Join-Path $runtimeDir "nvngx_dlssnr.dll"
    if (-not (Test-Path -LiteralPath $nrRuntime -PathType Leaf)) {
        throw "Could not find bundled nvngx_dlssnr.dll. Supply -NeuralRuntimeDll with an authorized compatible runtime."
    }
    $nrRuntime = (Resolve-Path -LiteralPath $nrRuntime).Path
}

if ([IO.Path]::GetFileName($nrRuntime) -ne "nvngx_dlssnr.dll") {
    throw "NeuralRuntimeDll must point to nvngx_dlssnr.dll."
}

function Find-One([string] $Root, [string] $Name) {
    $matches = @(Get-ChildItem -LiteralPath $Root -Filter $Name -File -Recurse -ErrorAction SilentlyContinue)
    if ($matches.Count -eq 0) { throw "Could not find $Name below $Root" }
    if ($matches.Count -gt 1) { Write-Warning "Multiple $Name files found; using $($matches[0].FullName)" }
    return $matches[0].FullName
}

function Find-Bundled-Plugin([string] $Name) {
    $path = Join-Path $repo (Join-Path "runtime" $Name)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Bundled $Name is missing from the extension package: $path"
    }
    return (Resolve-Path -LiteralPath $path).Path
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
$nrPlugin = Find-Bundled-Plugin "vsdlssnr.dll"
$srPlugin = Find-Bundled-Plugin "vsdlsssr.dll"
if ($SRRuntimeDll) {
    $srRuntime = (Resolve-Path -LiteralPath $SRRuntimeDll).Path
} else {
    $bundledSrRuntime = Join-Path $runtimeDir "nvngx_dlss.dll"
    if (Test-Path -LiteralPath $bundledSrRuntime -PathType Leaf) {
        $srRuntime = (Resolve-Path -LiteralPath $bundledSrRuntime).Path
    } else {
        try {
            $srRuntime = Find-One $vapourKit "nvngx_dlss.dll"
        } catch {
            throw "Could not find bundled nvngx_dlss.dll. Supply -SRRuntimeDll with a compatible authorized NVIDIA DLSS SR runtime."
        }
    }
}
if ([IO.Path]::GetFileName($srRuntime) -ine "nvngx_dlss.dll") {
    throw "SRRuntimeDll must point to nvngx_dlss.dll."
}

function Copy-If-Different([string] $Source, [string] $Destination) {
    if ([IO.Path]::GetFullPath($Source) -ne [IO.Path]::GetFullPath($Destination)) {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
    }
}
Copy-If-Different $nrRuntime (Join-Path $runtimeDir "nvngx_dlssnr.dll")
Copy-If-Different $srRuntime (Join-Path $runtimeDir "nvngx_dlss.dll")

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
    dlssg_runtime = (Join-Path $runtimeDir "dlssg\nvngx_dlssg.dll")
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
