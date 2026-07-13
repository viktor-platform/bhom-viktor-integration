[CmdletBinding()]
param(
    [string]$RootDirectory = "C:\dev\bhom-lca",
    [string]$Branch = "develop",
    [switch]$SkipCore
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or is not available on PATH."
}

$RootDirectory = [System.IO.Path]::GetFullPath($RootDirectory)
$ExternalDirectory = Join-Path $RootDirectory "external"
New-Item -ItemType Directory -Force -Path $ExternalDirectory | Out-Null

$Repositories = @(
    [ordered]@{
        Name = "LifeCycleAssessment_Toolkit"
        Url = "https://github.com/BHoM/LifeCycleAssessment_Toolkit.git"
    },
    [ordered]@{
        Name = "BHoM_JSONSchema"
        Url = "https://github.com/BHoM/BHoM_JSONSchema.git"
    }
)

if (-not $SkipCore) {
    $Repositories += @(
        [ordered]@{
            Name = "BHoM"
            Url = "https://github.com/BHoM/BHoM.git"
        },
        [ordered]@{
            Name = "BHoM_Engine"
            Url = "https://github.com/BHoM/BHoM_Engine.git"
        }
    )
}

$RevisionItems = @()
foreach ($Repository in $Repositories) {
    $Destination = Join-Path $ExternalDirectory $Repository.Name

    if (Test-Path $Destination) {
        if (-not (Test-Path (Join-Path $Destination ".git"))) {
            throw "$Destination exists but is not a Git repository."
        }

        $Changes = git -C $Destination status --porcelain
        if ($LASTEXITCODE -ne 0) {
            throw "Could not read Git status for $($Repository.Name)."
        }
        if ($Changes) {
            throw "$($Repository.Name) contains uncommitted changes. Commit or remove them before updating."
        }

        git -C $Destination fetch --prune origin
        if ($LASTEXITCODE -ne 0) {
            throw "git fetch failed for $($Repository.Name)."
        }

        git -C $Destination checkout $Branch
        if ($LASTEXITCODE -ne 0) {
            throw "Could not check out branch '$Branch' for $($Repository.Name)."
        }

        git -C $Destination pull --ff-only origin $Branch
        if ($LASTEXITCODE -ne 0) {
            throw "git pull --ff-only failed for $($Repository.Name)."
        }
    }
    else {
        git clone --branch $Branch --single-branch $Repository.Url $Destination
        if ($LASTEXITCODE -ne 0) {
            throw "git clone failed for $($Repository.Name)."
        }
    }

    $Commit = (git -C $Destination rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read the commit for $($Repository.Name)."
    }

    $Remote = (git -C $Destination remote get-url origin).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read the origin URL for $($Repository.Name)."
    }

    $RevisionItems += [ordered]@{
        name = $Repository.Name
        url = $Remote
        branch = $Branch
        commit = $Commit
        path = $Destination
    }

    Write-Host "$($Repository.Name): $Commit"
}

$Manifest = [ordered]@{
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    root_directory = $RootDirectory
    repositories = $RevisionItems
}

$ManifestPath = Join-Path $RootDirectory "external-revisions.json"
$Manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $ManifestPath -Encoding UTF8
Write-Host "Revision manifest: $ManifestPath"
