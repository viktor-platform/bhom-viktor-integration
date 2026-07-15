[CmdletBinding()]
param(
    [string]$BHoMAssembliesDirectory = "C:\ProgramData\BHoM\Assemblies",
    [string]$GatewayPath = "C:\Services\BHoMRevitGateway\BHoMRevitGateway.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RequiredAssemblies = @(
    "Adapter_oM.dll",
    "BHoM.dll",
    "Revit_Adapter.dll",
    "Revit_Engine.dll",
    "Revit_oM.dll",
    "Serialiser_Engine.dll",
    "Socket_Adapter.dll",
    "Socket_oM.dll"
)
foreach ($Assembly in $RequiredAssemblies) {
    $Path = Join-Path $BHoMAssembliesDirectory $Assembly
    if (-not (Test-Path $Path)) {
        throw "Required BHoM assembly is missing: $Assembly"
    }
    $Version = [System.Reflection.AssemblyName]::GetAssemblyName($Path).Version
    Write-Host "$Assembly $Version"
}

$RevitPath = "C:\Program Files\Autodesk\Revit 2025\Revit.exe"
if (-not (Test-Path $RevitPath)) {
    throw "Revit 2025 was not found at $RevitPath."
}
$AddinManifest = Join-Path $env:APPDATA "Autodesk\Revit\Addins\2025\BHoM_2025.Addin"
if (-not (Test-Path $AddinManifest)) {
    throw "The BHoM Revit 2025 add-in manifest was not found at $AddinManifest."
}

if (Test-Path $GatewayPath) {
    $JobDirectory = Join-Path ([System.IO.Path]::GetTempPath()) (
        "bhom-revit-worker-diagnose-" + [Guid]::NewGuid().ToString("N")
    )
    New-Item -ItemType Directory -Force -Path $JobDirectory | Out-Null
    try {
        Push-Location $JobDirectory
        & $GatewayPath diagnose --events revit-events.json --runtime-manifest runtime-manifest.json
        if ($LASTEXITCODE -ne 0) {
            throw "Revit gateway diagnostic command failed."
        }
        Get-Content .\runtime-manifest.json -Raw
    }
    finally {
        Pop-Location
        Remove-Item -Recurse -Force $JobDirectory -ErrorAction SilentlyContinue
    }
}
else {
    Write-Warning "Gateway is not installed at $GatewayPath. Runtime checks passed."
}

Write-Host "Revit 2025 and the official BHoM add-in are registered."
Write-Host "Live acceptance still requires one open Revit document and an activated Revit Listener."
