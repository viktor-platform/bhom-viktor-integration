[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern("^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")]
    [string]$Version,
    [string]$PublishDirectory = "",
    [string]$OutputDirectory = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($PublishDirectory)) {
    $PublishDirectory = Join-Path $RepositoryRoot "gateway\publish\win-x64"
}
else {
    $PublishDirectory = [System.IO.Path]::GetFullPath($PublishDirectory)
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepositoryRoot "artifacts"
}
else {
    $OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
}

$Gateway = Join-Path $PublishDirectory "BHoMLcaGateway.exe"
if (-not (Test-Path $Gateway)) {
    throw "Published gateway not found at $Gateway. Run scripts\build-gateway.ps1 first."
}

$Version = $Version.TrimStart("v")
$PackageName = "BHoMLcaGateway-$Version-win-x64"
$ArchivePath = Join-Path $OutputDirectory "$PackageName.zip"
$ChecksumPath = "$ArchivePath.sha256"
$StagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    "bhom-lca-release-" + [Guid]::NewGuid().ToString("N")
)
$PackageDirectory = Join-Path $StagingRoot $PackageName
$GatewayDirectory = Join-Path $PackageDirectory "gateway"
$DiagnosticDirectory = Join-Path $StagingRoot "diagnostic"

New-Item -ItemType Directory -Force -Path $GatewayDirectory | Out-Null
New-Item -ItemType Directory -Force -Path $DiagnosticDirectory | Out-Null
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

try {
    Copy-Item -Path (Join-Path $PublishDirectory "*") `
        -Destination $GatewayDirectory `
        -Recurse `
        -Force

    Get-ChildItem -Path $GatewayDirectory -Filter "*.pdb" -Recurse |
        Remove-Item -Force

    Copy-Item (Join-Path $RepositoryRoot "worker\install-gateway.ps1") `
        (Join-Path $PackageDirectory "install.ps1")
    Copy-Item (Join-Path $RepositoryRoot "worker\diagnose.ps1") `
        (Join-Path $PackageDirectory "diagnose.ps1")
    Copy-Item (Join-Path $RepositoryRoot "worker\config.example.yaml") `
        (Join-Path $PackageDirectory "config.example.yaml")
    Copy-Item (Join-Path $RepositoryRoot "worker\INSTALL.md") `
        (Join-Path $PackageDirectory "README.md")

    Push-Location $DiagnosticDirectory
    try {
        & (Join-Path $GatewayDirectory "BHoMLcaGateway.exe") diagnose `
            --events analysis-events.json `
            --runtime-manifest runtime-manifest.json
        if ($LASTEXITCODE -ne 0) {
            throw "The packaged gateway diagnostic command failed."
        }
    }
    finally {
        Pop-Location
    }

    Remove-Item $ArchivePath -Force -ErrorAction SilentlyContinue
    Remove-Item $ChecksumPath -Force -ErrorAction SilentlyContinue
    Compress-Archive -Path $PackageDirectory -DestinationPath $ArchivePath

    $Checksum = (Get-FileHash -Path $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $ChecksumLine = "$Checksum  $([System.IO.Path]::GetFileName($ArchivePath))`n"
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        $ChecksumPath,
        $ChecksumLine,
        $Utf8NoBom
    )
}
finally {
    Remove-Item -Path $StagingRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Release package: $ArchivePath"
Write-Host "SHA-256: $ChecksumPath"
