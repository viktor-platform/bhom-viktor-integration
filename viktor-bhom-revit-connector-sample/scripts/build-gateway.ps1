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

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw ".NET SDK is not installed or is not available on PATH."
}

$ServiceDirectory = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$GatewayProject = Join-Path $ServiceDirectory "gateway\src\BHoMRevitGateway\BHoMRevitGateway.csproj"
if (-not (Test-Path $GatewayProject)) {
    throw "Could not find the Revit gateway project at $GatewayProject."
}

$AssembliesDirectory = Join-Path $InstalledBHoMRoot "Assemblies"
if (-not (Test-Path $AssembliesDirectory)) {
    throw "BHoM assemblies were not found at $AssembliesDirectory."
}

$RequiredAssemblies = @(
    "Adapter_Engine.dll",
    "Adapter_oM.dll",
    "Base_Engine.dll",
    "BHoM.dll",
    "BHoM_Adapter.dll",
    "BHoM_Engine.dll",
    "Data_oM.dll",
    "Physical_oM.dll",
    "Revit_Adapter.dll",
    "Revit_Engine.dll",
    "Revit_oM.dll",
    "Serialiser_Engine.dll",
    "Socket_Adapter.dll",
    "Socket_oM.dll"
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

dotnet publish $GatewayProject `
    --configuration $Configuration `
    --runtime $RuntimeIdentifier `
    --self-contained false `
    --output $PublishDirectory `
    --property:BHoMAssembliesDir="$AssembliesDirectory"
if ($LASTEXITCODE -ne 0) {
    throw "The Revit gateway publish failed."
}

$Gateway = Join-Path $PublishDirectory "BHoMRevitGateway.exe"
if (-not (Test-Path $Gateway)) {
    throw "The gateway executable was not created at $Gateway."
}

$DiagnosticDirectory = Join-Path ([System.IO.Path]::GetTempPath()) (
    "bhom-revit-diagnose-" + [Guid]::NewGuid().ToString("N")
)
New-Item -ItemType Directory -Force -Path $DiagnosticDirectory | Out-Null
try {
    Push-Location $DiagnosticDirectory
    & $Gateway diagnose --events revit-events.json --runtime-manifest runtime-manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw "The published Revit gateway diagnostic command failed."
    }
}
finally {
    Pop-Location
    Remove-Item -Recurse -Force $DiagnosticDirectory -ErrorAction SilentlyContinue
}

$PublishedDllCount = (Get-ChildItem $PublishDirectory -Filter "*.dll").Count
Write-Host "Revit gateway published to $PublishDirectory"
Write-Host "Published managed DLLs: $PublishedDllCount"
Write-Host "Pinned BHoM distribution: v9.2.beta.0 ($ExpectedBHoMAssemblyVersion)"
