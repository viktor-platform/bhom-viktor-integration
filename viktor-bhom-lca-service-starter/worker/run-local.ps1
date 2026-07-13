[CmdletBinding()]
param(
    [string]$GatewayPath = "",
    [switch]$KeepJobDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($GatewayPath)) {
    $GatewayPath = Join-Path $RepositoryRoot "gateway\publish\win-x64\BHoMLcaGateway.exe"
}
$GatewayPath = [System.IO.Path]::GetFullPath($GatewayPath)

if (-not (Test-Path $GatewayPath)) {
    throw "Gateway not found: $GatewayPath. Run scripts\build-gateway.ps1 first."
}

$JobDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("bhom-lca-sample-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $JobDirectory | Out-Null
Copy-Item (Join-Path $RepositoryRoot "samples\analysis-request.json") $JobDirectory
Copy-Item (Join-Path $RepositoryRoot "samples\takeoff.bhom.json") $JobDirectory
Copy-Item (Join-Path $RepositoryRoot "samples\template-materials.bhom.json") $JobDirectory

try {
    Push-Location $JobDirectory
    & $GatewayPath run `
        --request analysis-request.json `
        --output analysis-result.json `
        --raw-output bhom-results.json `
        --events analysis-events.json `
        --runtime-manifest runtime-manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw "Gateway sample execution failed with exit code $LASTEXITCODE."
    }

    $Result = Get-Content .\analysis-result.json -Raw | ConvertFrom-Json
    $ExpectedTotal = 19365.0
    $ExpectedIntensity = 38.73
    $Tolerance = 0.000001

    if ([Math]::Abs([double]$Result.summary.total_kgco2e - $ExpectedTotal) -gt $Tolerance) {
        throw "Unexpected total_kgco2e: $($Result.summary.total_kgco2e)"
    }
    if ([Math]::Abs([double]$Result.summary.carbon_intensity_kgco2e_m2 - $ExpectedIntensity) -gt $Tolerance) {
        throw "Unexpected carbon intensity: $($Result.summary.carbon_intensity_kgco2e_m2)"
    }

    Write-Host "Sample passed."
    Write-Host "total_kgco2e = $($Result.summary.total_kgco2e)"
    Write-Host "total_tco2e = $($Result.summary.total_tco2e)"
    Write-Host "carbon_intensity_kgco2e_m2 = $($Result.summary.carbon_intensity_kgco2e_m2)"
    Write-Host "Job directory: $JobDirectory"
}
finally {
    Pop-Location
    if (-not $KeepJobDirectory) {
        Remove-Item -Recurse -Force $JobDirectory -ErrorAction SilentlyContinue
    }
}
