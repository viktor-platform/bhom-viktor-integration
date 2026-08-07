[CmdletBinding()]
param(
    [string]$SourceDirectory = "",
    [string]$TargetDirectory = "C:\Services\BHoMMaterialLookupGateway"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($SourceDirectory)) {
    $SourceDirectory = Join-Path $RepositoryRoot "gateway\publish\win-x64"
}
$Gateway = Join-Path $SourceDirectory "BHoMMaterialLookupGateway.exe"
if (-not (Test-Path $Gateway)) {
    throw "Gateway not found. Run scripts\build-gateway.ps1 first."
}
New-Item $TargetDirectory -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $SourceDirectory "*") $TargetDirectory -Recurse -Force
Write-Host "Installed BHoM material lookup gateway to $TargetDirectory"
Write-Host "No API token is required; the gateway reads BHoM's installed LCA datasets."
Write-Host "Merge worker\config.example.yaml into the Generic Worker configuration."
