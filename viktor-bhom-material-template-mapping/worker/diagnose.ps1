[CmdletBinding()]
param(
    [string]$GatewayPath = "C:\Services\BHoMMaterialLookupGateway\BHoMMaterialLookupGateway.exe",
    [string]$DatasetRoot = "C:\ProgramData\BHoM\Datasets\LifeCycleAssessment"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not (Test-Path $GatewayPath)) {
    throw "Gateway not found: $GatewayPath"
}
if (-not (Test-Path $DatasetRoot)) {
    throw "BHoM LifeCycleAssessment datasets not found: $DatasetRoot"
}
$DatasetFiles = @(Get-ChildItem $DatasetRoot -Recurse -Filter "*.json")
if ($DatasetFiles.Count -eq 0) {
    throw "No installed BHoM LCA dataset files were found."
}

$Temp = Join-Path ([IO.Path]::GetTempPath()) ("bhom-library-diagnose-" + [Guid]::NewGuid().ToString("N"))
New-Item $Temp -ItemType Directory -Force | Out-Null
try {
    Push-Location $Temp
    & $GatewayPath diagnose --events lookup-events.json --runtime-manifest runtime-manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw "Gateway diagnostic failed with exit code $LASTEXITCODE."
    }
    Write-Host "Installed BHoM LCA dataset files: $($DatasetFiles.Count)"
    Get-Content .\runtime-manifest.json
}
finally {
    Pop-Location
    Remove-Item $Temp -Recurse -Force -ErrorAction SilentlyContinue
}
