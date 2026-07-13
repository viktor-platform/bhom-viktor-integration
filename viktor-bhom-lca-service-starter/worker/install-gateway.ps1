[CmdletBinding()]
param(
    [string]$SourceDirectory = "",
    [string]$TargetDirectory = "C:\Services\BHoMLcaGateway"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an Administrator PowerShell session."
}

if ([string]::IsNullOrWhiteSpace($SourceDirectory)) {
    $SourceDirectory = (Resolve-Path (Join-Path $PSScriptRoot "..\gateway\publish\win-x64")).Path
}
else {
    $SourceDirectory = [System.IO.Path]::GetFullPath($SourceDirectory)
}
$TargetDirectory = [System.IO.Path]::GetFullPath($TargetDirectory)

$SourceExecutable = Join-Path $SourceDirectory "BHoMLcaGateway.exe"
if (-not (Test-Path $SourceExecutable)) {
    throw "Published gateway not found: $SourceExecutable"
}

if (Test-Path $TargetDirectory) {
    $Timestamp = [DateTimeOffset]::Now.ToString("yyyyMMdd-HHmmss")
    $BackupDirectory = "$TargetDirectory.backup-$Timestamp"
    Move-Item -Path $TargetDirectory -Destination $BackupDirectory
    Write-Host "Previous installation moved to $BackupDirectory"
}

New-Item -ItemType Directory -Force -Path $TargetDirectory | Out-Null
Copy-Item -Path (Join-Path $SourceDirectory "*") -Destination $TargetDirectory -Recurse -Force

$InstalledGateway = Join-Path $TargetDirectory "BHoMLcaGateway.exe"
$DiagnosticDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("bhom-lca-install-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $DiagnosticDirectory | Out-Null
try {
    Push-Location $DiagnosticDirectory
    & $InstalledGateway diagnose --events analysis-events.json --runtime-manifest runtime-manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw "Installed gateway diagnostic command failed."
    }
    $Manifest = Get-Content .\runtime-manifest.json -Raw | ConvertFrom-Json
    Write-Host "Gateway version: $($Manifest.gateway_version)"
    Write-Host "Managed assemblies: $($Manifest.assemblies.Count)"
}
finally {
    Pop-Location
    Remove-Item -Recurse -Force $DiagnosticDirectory -ErrorAction SilentlyContinue
}

Write-Host "Gateway installed at $TargetDirectory"
Write-Host "Merge worker\config.example.yaml into the Generic Worker configuration and restart the worker service."
