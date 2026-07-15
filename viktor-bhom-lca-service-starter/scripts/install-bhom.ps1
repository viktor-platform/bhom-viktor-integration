[CmdletBinding()]
param(
    [string]$DestinationPath = (Join-Path $env:TEMP "BHoM_v9.2.beta.0.msi"),
    [switch]$Install,
    [switch]$ForceDownload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$InstallerUrl = "https://bhom.xyz/assets/installers/BHoM_v9.2.beta.0.msi"
$ExpectedSha256 = "6511105da18383d0d2e86460782f927050314a612120fca2437f717a5f17f5ae"
$ExpectedAssemblyVersion = "9.0.0.0"
$InstalledAssembly = "C:\ProgramData\BHoM\Assemblies\BHoM.dll"

function Test-PinnedBHoMInstallation {
    if (-not (Test-Path $InstalledAssembly)) {
        return $false
    }

    $Version = [System.Reflection.AssemblyName]::GetAssemblyName(
        $InstalledAssembly
    ).Version
    return $Version.ToString() -eq $ExpectedAssemblyVersion
}

if ((Test-PinnedBHoMInstallation) -and -not $ForceDownload) {
    Write-Host "BHoM v9.2.beta.0 assemblies are already installed."
    exit 0
}

$DestinationPath = [System.IO.Path]::GetFullPath($DestinationPath)
$DestinationDirectory = Split-Path $DestinationPath -Parent
New-Item -ItemType Directory -Force -Path $DestinationDirectory | Out-Null

if ($ForceDownload -or -not (Test-Path $DestinationPath)) {
    Write-Host "Downloading pinned BHoM installer..."
    Invoke-WebRequest `
        -Uri $InstallerUrl `
        -OutFile $DestinationPath `
        -UseBasicParsing
}

$ActualSha256 = (Get-FileHash $DestinationPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualSha256 -ne $ExpectedSha256) {
    throw "BHoM installer checksum mismatch. Expected $ExpectedSha256, received $ActualSha256."
}
Write-Host "Verified BHoM installer: $DestinationPath"

if (-not $Install) {
    Write-Host "Download complete. Run again with -Install to install it."
    exit 0
}

$Arguments = @(
    "/i",
    ('"' + $DestinationPath + '"'),
    "/passive",
    "/norestart"
)
$Process = Start-Process `
    -FilePath "msiexec.exe" `
    -ArgumentList $Arguments `
    -Verb RunAs `
    -Wait `
    -PassThru
if ($Process.ExitCode -notin @(0, 3010)) {
    throw "BHoM installation failed with exit code $($Process.ExitCode)."
}

if (-not (Test-PinnedBHoMInstallation)) {
    throw "BHoM installed, but BHoM.dll does not report version $ExpectedAssemblyVersion."
}

Write-Host "BHoM v9.2.beta.0 installed successfully."
if ($Process.ExitCode -eq 3010) {
    Write-Warning "Windows reports that a restart is required."
}
