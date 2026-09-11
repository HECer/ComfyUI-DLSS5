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
$configPath = Join-Path $runtimeDir "config.json"

$customNodes = Join-Path $comfy "custom_nodes"
$repoParent = Split-Path $repo -Parent
$createJunction = $false
if ([IO.Path]::GetFileName($repoParent) -ieq "custom_nodes") {
    $installPath = $repo
} else {
    $installPath = Join-Path $customNodes "ComfyUI-DLSS5"
    if (Test-Path -LiteralPath $installPath) {
        $existing = Get-Item -LiteralPath $installPath -Force
        $target = @($existing.Target)[0]
        if (-not $target -or -not [IO.Path]::IsPathRooted($target)) {
            $target = Join-Path (Split-Path $installPath -Parent) $target
        }
        if (
            $existing.LinkType -ne "Junction" -or
            [IO.Path]::GetFullPath($target) -ine [IO.Path]::GetFullPath($repo)
        ) {
            throw "$installPath already exists and does not target $repo. Remove or rename it, then run setup again."
        }
    } else {
        $createJunction = $true
    }
}

$existingConfig = [ordered]@{}
if (Test-Path -LiteralPath $configPath -PathType Leaf) {
    try {
        $configJson = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8
        $parsedConfig = ConvertFrom-Json -InputObject $configJson
    } catch {
        throw "Invalid runtime configuration at ${configPath}: $($_.Exception.Message)"
    }
    if (
        -not $configJson.TrimStart().StartsWith("{") -or
        $null -eq $parsedConfig -or
        $parsedConfig.GetType().FullName -ne "System.Management.Automation.PSCustomObject"
    ) {
        throw "Invalid runtime configuration at ${configPath}: expected a JSON object"
    }
    foreach ($property in $parsedConfig.PSObject.Properties) {
        $existingConfig[$property.Name] = $property.Value
    }
}

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
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $global:LASTEXITCODE = -1
            & $candidate.FullName -c "import vapoursynth, numpy" 1>$null 2>$null
            $probeExitCode = $global:LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($probeExitCode -eq 0) { return $candidate.FullName }
    }
    throw "Could not find a Python interpreter with VapourSynth and NumPy below $Root. Repair the selected interpreter in this external VapourKit environment: verify VapourSynth and run its python.exe -m pip install numpy==2.5.2 for missing NumPy, then retry setup. Alternatively, run install_runtime.ps1 to install and configure the automatic runtime; it does not repair the external environment selected by -VapourKitPath."
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
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
Copy-If-Different $nrRuntime (Join-Path $runtimeDir "nvngx_dlssnr.dll")
Copy-If-Different $srRuntime (Join-Path $runtimeDir "nvngx_dlss.dll")

if (-not $TempDirectory -and $existingConfig.Contains("temp_dir")) {
    $TempDirectory = [string] $existingConfig["temp_dir"]
}
if (-not $TempDirectory) {
    $TempDirectory = Join-Path ([IO.Path]::GetTempPath()) "comfyui-dlss5"
}
New-Item -ItemType Directory -Force -Path $TempDirectory | Out-Null

$config = $existingConfig
$config["python"] = $vsPython
$config["nr_plugin"] = Join-Path $runtimeDir "vsdlssnr.dll"
$config["nr_runtime"] = Join-Path $runtimeDir "nvngx_dlssnr.dll"
$config["sr_plugin"] = Join-Path $runtimeDir "vsdlsssr.dll"
$config["sr_runtime"] = Join-Path $runtimeDir "nvngx_dlss.dll"
$config["temp_dir"] = (Resolve-Path -LiteralPath $TempDirectory).Path
if (-not $config.Contains("timeout_seconds")) {
    $config["timeout_seconds"] = 0
}

$configWriteId = [Guid]::NewGuid().ToString("N")
$temporaryConfig = "$configPath.$configWriteId.tmp"
$backupConfig = "$configPath.$configWriteId.bak"
$junctionCreated = $false
try {
    $json = $config | ConvertTo-Json -Depth 100
    [IO.File]::WriteAllText($temporaryConfig, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    New-Item -ItemType Directory -Force -Path $customNodes | Out-Null
    if ($createJunction) {
        New-Item -ItemType Junction -Path $installPath -Target $repo | Out-Null
        $junctionCreated = $true
    }
    if (Test-Path -LiteralPath $configPath -PathType Leaf) {
        [IO.File]::Replace($temporaryConfig, $configPath, $backupConfig)
    } else {
        [IO.File]::Move($temporaryConfig, $configPath)
    }
} catch {
    if ($junctionCreated) {
        [IO.Directory]::Delete($installPath)
    }
    throw
} finally {
    if (Test-Path -LiteralPath $temporaryConfig -PathType Leaf) {
        Remove-Item -LiteralPath $temporaryConfig -Force
    }
}
if (Test-Path -LiteralPath $backupConfig -PathType Leaf) {
    Remove-Item -LiteralPath $backupConfig -Force
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Extension: $installPath"
Write-Host "Runtime config: $(Join-Path $runtimeDir 'config.json')"
Write-Host "Temporary files: $TempDirectory"
Write-Host "Python dependencies are managed by ComfyUI Manager/Registry; manual clones must install requirements.txt once."
Write-Host "Restart ComfyUI, then run the 'DLSS 5 Runtime Status' node."
