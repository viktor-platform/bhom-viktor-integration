[CmdletBinding()]
param(
    [string]$RemoteUrl = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepositoryRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or is not available on PATH."
}

if (-not (Test-Path (Join-Path $RepositoryRoot ".git"))) {
    git init
    if ($LASTEXITCODE -ne 0) {
        throw "git init failed."
    }
}

$ExistingUserName = git config user.name
$ExistingUserEmail = git config user.email
if ([string]::IsNullOrWhiteSpace($ExistingUserName) -or [string]::IsNullOrWhiteSpace($ExistingUserEmail)) {
    throw "Configure git user.name and user.email before creating the initial commit."
}

git add .
if ($LASTEXITCODE -ne 0) {
    throw "git add failed."
}

$HasCommit = $true
git rev-parse --verify HEAD *> $null
if ($LASTEXITCODE -ne 0) {
    $HasCommit = $false
}

if (-not $HasCommit) {
    git commit -m "Initial VIKTOR BHoM LCA service"
    if ($LASTEXITCODE -ne 0) {
        throw "Initial git commit failed."
    }
}

if (-not [string]::IsNullOrWhiteSpace($RemoteUrl)) {
    $ExistingRemote = git remote get-url origin 2>$null
    if ($LASTEXITCODE -eq 0) {
        git remote set-url origin $RemoteUrl
    }
    else {
        git remote add origin $RemoteUrl
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Could not configure the origin remote."
    }
}

Write-Host "Repository initialized at $RepositoryRoot"
if (-not [string]::IsNullOrWhiteSpace($RemoteUrl)) {
    Write-Host "Origin: $RemoteUrl"
}
