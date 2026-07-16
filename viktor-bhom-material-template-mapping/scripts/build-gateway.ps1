[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [string]$RuntimeIdentifier = "win-x64",
    [string]$InstalledBHoMRoot = "C:\ProgramData\BHoM",
    [string]$ExpectedBHoMAssemblyVersion = "9.0.0.0"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$AssembliesDirectory = Join-Path $InstalledBHoMRoot "Assemblies"
$DatasetsDirectory = Join-Path $InstalledBHoMRoot "Datasets\LifeCycleAssessment"
$RequiredAssemblies = @(
    "BHoM.dll",
    "BHoM_Engine.dll",
    "Data_Engine.dll",
    "Data_oM.dll",
    "Library_Engine.dll",
    "LifeCycleAssessment_oM.dll",
    "Serialiser_Engine.dll",
    "Versioning_Engine.dll",
    "Versioning_oM.dll"
)

foreach ($Name in $RequiredAssemblies) {
    $Path = Join-Path $AssembliesDirectory $Name
    if (-not (Test-Path $Path)) {
        throw "Required BHoM assembly is missing: $Name"
    }
    $Version = [Reflection.AssemblyName]::GetAssemblyName($Path).Version.ToString()
    if ($Version -ne $ExpectedBHoMAssemblyVersion) {
        throw "$Name has version $Version; expected $ExpectedBHoMAssemblyVersion."
    }
}
if (-not (Test-Path $DatasetsDirectory)) {
    throw "BHoM LifeCycleAssessment datasets are missing: $DatasetsDirectory"
}
$DatasetFiles = @(Get-ChildItem $DatasetsDirectory -Recurse -Filter "*.json")
if ($DatasetFiles.Count -eq 0) {
    throw "No BHoM LifeCycleAssessment dataset JSON files were found."
}

$Project = Join-Path $RepositoryRoot "gateway\src\BHoMMaterialLookupGateway\BHoMMaterialLookupGateway.csproj"
$PublishDirectory = Join-Path $RepositoryRoot "gateway\publish\$RuntimeIdentifier"
Remove-Item $PublishDirectory -Recurse -Force -ErrorAction SilentlyContinue

dotnet publish $Project --configuration $Configuration --runtime $RuntimeIdentifier --self-contained false --output $PublishDirectory --property:BHoMAssembliesDir="$AssembliesDirectory"
if ($LASTEXITCODE -ne 0) {
    throw "The material lookup gateway publish failed."
}

$RuntimeConfig = Join-Path $PublishDirectory "BHoMMaterialLookupGateway.runtimeconfig.json"
@'
{
  "runtimeOptions": {
    "tfm": "net8.0",
    "frameworks": [
      { "name": "Microsoft.WindowsDesktop.App", "version": "8.0.0" },
      { "name": "Microsoft.NETCore.App", "version": "8.0.0" }
    ],
    "configProperties": {
      "System.Globalization.Invariant": false
    }
  }
}
'@ | Set-Content $RuntimeConfig -Encoding UTF8

$Gateway = Join-Path $PublishDirectory "BHoMMaterialLookupGateway.exe"
$Temp = Join-Path ([IO.Path]::GetTempPath()) ("bhom-library-diagnose-" + [Guid]::NewGuid().ToString("N"))
New-Item $Temp -ItemType Directory -Force | Out-Null
try {
    Push-Location $Temp
    & $Gateway diagnose --events lookup-events.json --runtime-manifest runtime-manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw "The published gateway diagnostic failed."
    }
}
finally {
    Pop-Location
    Remove-Item $Temp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Material lookup gateway published to $PublishDirectory"
Write-Host "BHoM assembly version: $ExpectedBHoMAssemblyVersion"
Write-Host "Installed LCA dataset files: $($DatasetFiles.Count)"
