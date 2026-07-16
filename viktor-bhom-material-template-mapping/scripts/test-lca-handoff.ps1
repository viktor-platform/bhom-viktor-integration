[CmdletBinding()]
param(
    [string]$LcaGatewayPath = "",
    [switch]$KeepJobDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($LcaGatewayPath)) {
    $LcaGatewayPath = Join-Path $RepositoryRoot "viktor-bhom-lca-service-starter\gateway\publish\win-x64\BHoMLcaGateway.exe"
}
if (-not (Test-Path $LcaGatewayPath)) {
    throw "LCA gateway not found: $LcaGatewayPath"
}

$JobDirectory = Join-Path ([IO.Path]::GetTempPath()) ("bhom-material-lca-" + [Guid]::NewGuid().ToString("N"))
New-Item $JobDirectory -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $AppRoot "samples\analysis-request.json") $JobDirectory
Copy-Item (Join-Path $AppRoot "samples\takeoff.bhom.json") $JobDirectory
Copy-Item (Join-Path $AppRoot "samples\template-materials.bhom.json") $JobDirectory
try {
    Push-Location $JobDirectory
    & $LcaGatewayPath run --request analysis-request.json --output analysis-result.json --raw-output bhom-results.json --events analysis-events.json --runtime-manifest runtime-manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw "LCA gateway integration test failed with exit code $LASTEXITCODE."
    }
    $Result = Get-Content .\analysis-result.json -Raw | ConvertFrom-Json
    if ($Result.status -ne "completed") {
        throw "Unexpected LCA status: $($Result.status)"
    }
    if ($Result.summary.unmatched_material_count -ne 0) {
        throw "The LCA gateway did not match every template material."
    }
    Write-Host "Material lookup to LCA gateway integration passed."
    Write-Host "Matched materials: $($Result.summary.record_count)"
    Write-Host "Total climate impact: $($Result.summary.total_kgco2e) kgCO2e"
    Write-Host "Job directory: $JobDirectory"
}
finally {
    Pop-Location
    if (-not $KeepJobDirectory) {
        Remove-Item $JobDirectory -Recurse -Force -ErrorAction SilentlyContinue
    }
}
