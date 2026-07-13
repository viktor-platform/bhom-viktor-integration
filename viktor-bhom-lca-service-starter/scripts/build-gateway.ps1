[CmdletBinding()]
param(
    [string]$RootDirectory = "C:\dev\bhom-lca",
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [string]$RuntimeIdentifier = "win-x64",
    [string]$InstalledBHoMAssemblies = "C:\ProgramData\BHoM\Assemblies",
    [switch]$SkipToolkitBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw ".NET SDK is not installed or is not available on PATH."
}

$RootDirectory = [System.IO.Path]::GetFullPath($RootDirectory)
$ServiceDirectory = Join-Path $RootDirectory "viktor-bhom-lca-service"
if (-not (Test-Path $ServiceDirectory)) {
    $Candidate = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    if (Test-Path (Join-Path $Candidate "gateway\BHoMLcaGateway.sln")) {
        $ServiceDirectory = $Candidate
    }
    else {
        throw "Could not find the service repository under $RootDirectory."
    }
}

if (-not (Test-Path $InstalledBHoMAssemblies)) {
    throw "BHoM assemblies were not found at $InstalledBHoMAssemblies. Install a compatible BHoM release first."
}

$RequiredInstalledAssemblies = @(
    "BHoM.dll",
    "BHoM_Engine.dll",
    "LifeCycleAssessment_oM.dll",
    "Physical_oM.dll",
    "Serialiser_Engine.dll"
)
foreach ($Name in $RequiredInstalledAssemblies) {
    if (-not (Test-Path (Join-Path $InstalledBHoMAssemblies $Name))) {
        throw "Required BHoM assembly is missing: $Name"
    }
}

$RuntimeDirectory = Join-Path $ServiceDirectory "gateway\runtime"
$PublishDirectory = Join-Path $ServiceDirectory "gateway\publish\$RuntimeIdentifier"
Remove-Item -Recurse -Force $RuntimeDirectory -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $PublishDirectory -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $RuntimeDirectory | Out-Null
New-Item -ItemType Directory -Force -Path $PublishDirectory | Out-Null

Copy-Item -Path (Join-Path $InstalledBHoMAssemblies "*.dll") -Destination $RuntimeDirectory -Force

if (-not $SkipToolkitBuild) {
    $EngineProject = Join-Path $RootDirectory "external\LifeCycleAssessment_Toolkit\LifeCycleAssessment_Engine\LifeCycleAssessment_Engine.csproj"
    if (-not (Test-Path $EngineProject)) {
        throw "The LCA toolkit source was not found at $EngineProject. Run clone-bhom-repositories.ps1 or use -SkipToolkitBuild."
    }

    dotnet build $EngineProject `
        --configuration $Configuration `
        --property:OutputPath="$RuntimeDirectory\" `
        --property:AppendTargetFrameworkToOutputPath=false `
        --property:AppendRuntimeIdentifierToOutputPath=false
    if ($LASTEXITCODE -ne 0) {
        throw "The LifeCycleAssessment Engine build failed."
    }
}

$RequiredRuntimeAssemblies = @(
    "BHoM.dll",
    "LifeCycleAssessment_Engine.dll",
    "LifeCycleAssessment_oM.dll",
    "Physical_oM.dll",
    "Serialiser_Engine.dll"
)
foreach ($Name in $RequiredRuntimeAssemblies) {
    if (-not (Test-Path (Join-Path $RuntimeDirectory $Name))) {
        throw "Gateway runtime assembly is missing: $Name"
    }
}

$GatewayProject = Join-Path $ServiceDirectory "gateway\src\BHoMLcaGateway\BHoMLcaGateway.csproj"
dotnet publish $GatewayProject `
    --configuration $Configuration `
    --runtime $RuntimeIdentifier `
    --self-contained false `
    --output $PublishDirectory `
    --property:BHoMAssembliesDir="$RuntimeDirectory"
if ($LASTEXITCODE -ne 0) {
    throw "The gateway publish failed."
}

Copy-Item -Path (Join-Path $RuntimeDirectory "*.dll") -Destination $PublishDirectory -Force

$DataSetSource = Join-Path $RootDirectory "external\LifeCycleAssessment_Toolkit\DataSets"
if (Test-Path $DataSetSource) {
    Copy-Item -Path $DataSetSource -Destination (Join-Path $PublishDirectory "DataSets") -Recurse -Force
}

$RevisionManifest = Join-Path $RootDirectory "external-revisions.json"
if (Test-Path $RevisionManifest) {
    Copy-Item $RevisionManifest (Join-Path $PublishDirectory "external-revisions.json") -Force
}

$Gateway = Join-Path $PublishDirectory "BHoMLcaGateway.exe"
if (-not (Test-Path $Gateway)) {
    throw "The gateway executable was not created at $Gateway."
}

$DiagnosticDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("bhom-lca-diagnose-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $DiagnosticDirectory | Out-Null
try {
    Push-Location $DiagnosticDirectory
    & $Gateway diagnose --events analysis-events.json --runtime-manifest runtime-manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw "The published gateway diagnostic command failed."
    }
    if (-not (Test-Path "runtime-manifest.json")) {
        throw "The gateway diagnostic command did not create runtime-manifest.json."
    }
}
finally {
    Pop-Location
    Remove-Item -Recurse -Force $DiagnosticDirectory -ErrorAction SilentlyContinue
}

Write-Host "Gateway published to $PublishDirectory"
