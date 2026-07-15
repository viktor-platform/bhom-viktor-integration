[CmdletBinding()]
param(
    [string]$GatewayPath = "",
    [switch]$KeepJobDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($GatewayPath)) {
    $GatewayPath = Join-Path $RepositoryRoot "gateway\publish\win-x64\BHoMMaterialLookupGateway.exe"
}
if (-not (Test-Path $GatewayPath)) {
    throw "Gateway not found. Run scripts\build-gateway.ps1 first."
}

$JobDirectory = Join-Path ([IO.Path]::GetTempPath()) ("bhom-library-sample-" + [Guid]::NewGuid().ToString("N"))
New-Item $JobDirectory -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $RepositoryRoot "samples\lookup-request.json") $JobDirectory
try {
    Push-Location $JobDirectory
    & $GatewayPath query --request lookup-request.json --output lookup-result.json --events lookup-events.json --runtime-manifest runtime-manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw "Installed BHoM dataset query failed with exit code $LASTEXITCODE."
    }
    $Result = Get-Content .\lookup-result.json -Raw | ConvertFrom-Json
    if ($Result.status -ne "completed") {
        throw "Unexpected lookup status: $($Result.status)"
    }
    if ($Result.searches[0].candidates.Count -eq 0) {
        throw "The installed BHoM dataset query returned no candidates."
    }
    Write-Host "Installed BHoM dataset query passed."
    Write-Host "Library path: $($Result.source.library_path)"
    Write-Host "EPDs searched: $($Result.source.epd_count)"
    Write-Host "Candidates: $($Result.searches[0].candidates.Count)"
    Write-Host "Job directory: $JobDirectory"
}
finally {
    Pop-Location
    if (-not $KeepJobDirectory) {
        Remove-Item $JobDirectory -Recurse -Force -ErrorAction SilentlyContinue
    }
}
