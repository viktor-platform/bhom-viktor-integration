# VIKTOR BHoM LCA analysis

![Thumbnail](assets/thumbnail.png)

A VIKTOR application that sends BHoM material takeoffs to a Windows Generic
Worker and returns normalized life-cycle assessment results.

## Repository layout

```text
app/                 Deployable VIKTOR Python package and JSON schemas
assets/              VIKTOR app assets
samples/             Fixed inputs and expected normalized result used by tests
gateway/             C# BHoM command-line gateway
scripts/             Windows gateway build and BHoM source setup
tests/               Python contract, visualization and worker-boundary tests
worker/              Generic Worker configuration, installation and diagnostics
```

The VIKTOR entry point is `app/__init__.py`, which exports `Controller` from
`app/app.py`.

## Prerequisites

- BHoM v9
- .NET 8 SDK and Windows Desktop Runtime
- PowerShell 5.1 or newer
- Python 3.13
- VIKTOR CLI and a configured Generic Worker

## Build the gateway

```powershell
git clone <repo-url> C:\dev\bhom-lca\viktor-bhom-lca-service
cd C:\dev\bhom-lca\viktor-bhom-lca-service

powershell -ExecutionPolicy Bypass -File scripts\install-bhom.ps1 -Install

powershell -ExecutionPolicy Bypass -File scripts\build-gateway.ps1 `
  -RootDirectory C:\dev\bhom-lca
```

The installer URL and SHA-256 are pinned to `BHoM_v9.2.beta.0.msi`. The build
verifies the installed BHoM assembly version and lets MSBuild publish only the
gateway's resolved BHoM/LCA dependency closure. It does not clone an independent
LCA source branch or copy every DLL from the BHoM installation.

Install the published gateway from an Administrator PowerShell session:

```powershell
powershell -ExecutionPolicy Bypass -File worker\install-gateway.ps1
```

Merge `worker/config.example.yaml` into the Generic Worker configuration and
restart the worker. The executable key must remain `bhom_lca`.

## Verify the gateway

```powershell
powershell -ExecutionPolicy Bypass -File worker\diagnose.ps1
powershell -ExecutionPolicy Bypass -File worker\run-local.ps1
```

The local sample check expects `total_kgco2e = 19365`.

## Create a GitHub Release package

After the gateway build and diagnostics pass, create the administrator ZIP:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package-release.ps1 `
  -Version 1.0.0
```

This creates two ignored files under `artifacts/`:

```text
BHoMLcaGateway-1.0.0-win-x64.zip
BHoMLcaGateway-1.0.0-win-x64.zip.sha256
```

Create tag `v1.0.0` in the GitHub **Releases** interface and upload both files
as release assets. The ZIP contains the dependency-closed gateway directory,
pinned BHoM installer helper, gateway installer, diagnostic command, worker
configuration example and administrator README.
Do not upload `BHoMLcaGateway.exe` by itself.

Keep the release private or marked as a prerelease until redistribution rights
for the included BHoM and third-party assemblies have been confirmed.

## Install from a GitHub Release

The Windows Generic Worker administrator:

1. Downloads the ZIP and checksum from the repository's **Releases** page.
2. Extracts the complete ZIP.
3. Runs `.\install-bhom.ps1 -Install` if pinned BHoM is not installed.
4. Opens PowerShell as Administrator in the extracted directory.
5. Runs `powershell -ExecutionPolicy Bypass -File .\install.ps1`.
6. Merges `config.example.yaml` into the Generic Worker configuration.
7. Restarts the Generic Worker and runs `.\diagnose.ps1`.

After this one-time worker setup, VIKTOR web-app users do not download the ZIP
or run the executable. They only upload their inputs and view the results in
VIKTOR.

## Run the VIKTOR app

```powershell
viktor-cli install
viktor-cli clean-start
```

Upload:

- `samples/takeoff.bhom.json` as the BHoM material takeoff.
- `samples/template-materials.bhom.json` as the template-material array.

The other two sample files are also intentional:
`analysis-request.json` drives the gateway smoke test and
`normalized-result.sample.json` is the expected contract and visualization
fixture.

## Development checks

Run from this directory:

```powershell
uvx ruff format .
uvx ruff check .
uvx ty check --python venv\Scripts\python.exe
venv\Scripts\python.exe -m pytest
viktor-cli test
dotnet run --project gateway\tests\BHoMLcaGateway.PortableTests
```

The portable C# harness does not execute BHoM's `EnvironmentalResults`.
Typed BHoM deserialization and the actual calculation require the Windows
assemblies and should be accepted with `worker/run-local.ps1`.
