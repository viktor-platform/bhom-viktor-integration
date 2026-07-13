[CmdletBinding()]
param(
    [string]$BHoMAssembliesDirectory = "C:\ProgramData\BHoM\Assemblies",
    [string]$GatewayPath = "C:\Services\BHoMLcaGateway\BHoMLcaGateway.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw ".NET is not installed or is not available on PATH."
}

Write-Host ".NET SDK and runtime information"
dotnet --info
if ($LASTEXITCODE -ne 0) {
    throw "dotnet --info failed."
}

if (-not (Test-Path $BHoMAssembliesDirectory)) {
    throw "BHoM assembly directory not found: $BHoMAssembliesDirectory"
}

$RequiredAssemblies = @(
    "BHoM.dll",
    "BHoM_Engine.dll",
    "LifeCycleAssessment_Engine.dll",
    "LifeCycleAssessment_oM.dll",
    "Matter_Engine.dll",
    "Physical_oM.dll",
    "Quantities_oM.dll",
    "Serialiser_Engine.dll"
)

$Missing = @()
foreach ($Assembly in $RequiredAssemblies) {
    $Path = Join-Path $BHoMAssembliesDirectory $Assembly
    if (Test-Path $Path) {
        $Version = [System.Reflection.AssemblyName]::GetAssemblyName($Path).Version
        Write-Host "$Assembly $Version"
    }
    else {
        $Missing += $Assembly
    }
}

if ($Missing.Count -gt 0) {
    throw "Missing BHoM assemblies: $($Missing -join ', ')"
}

if (Test-Path $GatewayPath) {
    $JobDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("bhom-lca-worker-diagnose-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $JobDirectory | Out-Null
    try {
        Push-Location $JobDirectory
        & $GatewayPath diagnose --events analysis-events.json --runtime-manifest runtime-manifest.json
        if ($LASTEXITCODE -ne 0) {
            throw "Gateway diagnostic command failed."
        }
        Get-Content .\runtime-manifest.json -Raw
    }
    finally {
        Pop-Location
        Remove-Item -Recurse -Force $JobDirectory -ErrorAction SilentlyContinue
    }
}
else {
    Write-Warning "Gateway is not installed at $GatewayPath. Assembly checks passed."
}
