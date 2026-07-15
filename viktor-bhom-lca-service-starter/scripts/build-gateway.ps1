[CmdletBinding()]
param(
    [string]$RootDirectory = "C:\dev\bhom-lca",
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [string]$RuntimeIdentifier = "win-x64",
    [string]$InstalledBHoMRoot = "C:\ProgramData\BHoM",
    [string]$ExpectedBHoMAssemblyVersion = "9.0.0.0"
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

$AssembliesDirectory = Join-Path $InstalledBHoMRoot "Assemblies"
if (-not (Test-Path $AssembliesDirectory)) {
    throw "BHoM assemblies were not found at $AssembliesDirectory. Run scripts\install-bhom.ps1 -Install first."
}

$RequiredAssemblies = @(
    "BHoM.dll",
    "BHoM_Engine.dll",
    "Dimensional_oM.dll",
    "LifeCycleAssessment_Engine.dll",
    "LifeCycleAssessment_oM.dll",
    "Matter_Engine.dll",
    "Physical_oM.dll",
    "Quantities_oM.dll",
    "Serialiser_Engine.dll"
)
foreach ($Name in $RequiredAssemblies) {
    $Path = Join-Path $AssembliesDirectory $Name
    if (-not (Test-Path $Path)) {
        throw "Required BHoM assembly is missing: $Name"
    }

    $Version = [System.Reflection.AssemblyName]::GetAssemblyName($Path).Version
    if ($Version.ToString() -ne $ExpectedBHoMAssemblyVersion) {
        throw "$Name has version $Version; expected $ExpectedBHoMAssemblyVersion from BHoM v9.2.beta.0."
    }
}

$PublishDirectory = Join-Path $ServiceDirectory "gateway\publish\$RuntimeIdentifier"
Remove-Item -Recurse -Force $PublishDirectory -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $PublishDirectory | Out-Null

$GatewayProject = Join-Path $ServiceDirectory "gateway\src\BHoMLcaGateway\BHoMLcaGateway.csproj"
dotnet publish $GatewayProject `
    --configuration $Configuration `
    --runtime $RuntimeIdentifier `
    --self-contained false `
    --output $PublishDirectory `
    --property:BHoMAssembliesDir="$AssembliesDirectory"
if ($LASTEXITCODE -ne 0) {
    throw "The gateway publish failed."
}

$DataSetSource = Join-Path $InstalledBHoMRoot "Datasets\LifeCycleAssessment"
if (-not (Test-Path $DataSetSource)) {
    throw "The installed BHoM LCA datasets were not found at $DataSetSource."
}
$DataSetDestination = Join-Path $PublishDirectory "DataSets\LifeCycleAssessment"
New-Item -ItemType Directory -Force -Path $DataSetDestination | Out-Null
Copy-Item -Path (Join-Path $DataSetSource "*") `
    -Destination $DataSetDestination `
    -Recurse `
    -Force

$Gateway = Join-Path $PublishDirectory "BHoMLcaGateway.exe"
if (-not (Test-Path $Gateway)) {
    throw "The gateway executable was not created at $Gateway."
}

# BHoM loads System.Drawing.Common and requires the Windows Desktop runtime.
$RuntimeConfig = Join-Path $PublishDirectory "BHoMLcaGateway.runtimeconfig.json"
@'
{
  "runtimeOptions": {
    "tfm": "net8.0",
    "frameworks": [
      { "name": "Microsoft.WindowsDesktop.App", "version": "8.0.0" },
      { "name": "Microsoft.NETCore.App",         "version": "8.0.0" }
    ],
    "configProperties": {
      "System.Globalization.Invariant": false,
      "System.Reflection.Metadata.MetadataUpdater.IsSupported": false,
      "System.Runtime.Serialization.EnableUnsafeBinaryFormatterSerialization": false,
      "CSWINRT_USE_WINDOWS_UI_XAML_PROJECTIONS": false
    }
  }
}
'@ | Set-Content $RuntimeConfig -Encoding UTF8

$DiagnosticDirectory = Join-Path ([System.IO.Path]::GetTempPath()) (
    "bhom-lca-diagnose-" + [Guid]::NewGuid().ToString("N")
)
New-Item -ItemType Directory -Force -Path $DiagnosticDirectory | Out-Null
try {
    Push-Location $DiagnosticDirectory
    & $Gateway diagnose --events analysis-events.json --runtime-manifest runtime-manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw "The published gateway diagnostic command failed."
    }
}
finally {
    Pop-Location
    Remove-Item -Recurse -Force $DiagnosticDirectory -ErrorAction SilentlyContinue
}

$PublishedDllCount = (Get-ChildItem $PublishDirectory -Filter "*.dll").Count
Write-Host "Gateway published to $PublishDirectory"
Write-Host "Published managed DLLs: $PublishedDllCount"
Write-Host "Pinned BHoM distribution: v9.2.beta.0 ($ExpectedBHoMAssemblyVersion)"
