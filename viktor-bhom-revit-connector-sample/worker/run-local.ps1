[CmdletBinding()]
param(
    [string]$GatewayPath = "",
    [switch]$KeepJobDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($GatewayPath)) {
    $GatewayPath = Join-Path $RepositoryRoot "gateway\publish\win-x64\BHoMRevitGateway.exe"
}
$GatewayPath = [System.IO.Path]::GetFullPath($GatewayPath)
if (-not (Test-Path $GatewayPath)) {
    throw "Gateway not found: $GatewayPath. Run scripts\build-gateway.ps1 first."
}

$JobDirectory = Join-Path ([System.IO.Path]::GetTempPath()) (
    "bhom-revit-sample-" + [Guid]::NewGuid().ToString("N")
)
New-Item -ItemType Directory -Force -Path $JobDirectory | Out-Null
Copy-Item (Join-Path $RepositoryRoot "samples\revit-pull-request.json") $JobDirectory

try {
    Push-Location $JobDirectory
    & $GatewayPath pull `
        --request revit-pull-request.json `
        --metadata revit-metadata.json `
        --elements revit-elements.bhom.json `
        --takeoff takeoff.bhom.json `
        --events revit-events.json `
        --runtime-manifest runtime-manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw "Live Revit sample failed with exit code $LASTEXITCODE."
    }

    $Metadata = Get-Content .\revit-metadata.json -Raw | ConvertFrom-Json
    $Takeoff = Get-Content .\takeoff.bhom.json -Raw | ConvertFrom-Json
    Write-Host "Live Revit pull passed."
    Write-Host "Elements: $($Metadata.elements.Count)"
    Write-Host "Takeoff items: $($Takeoff.MaterialTakeoffItems.Count)"
    Write-Host "Job directory: $JobDirectory"
}
finally {
    Pop-Location
    if (-not $KeepJobDirectory) {
        Remove-Item -Recurse -Force $JobDirectory -ErrorAction SilentlyContinue
    }
}
