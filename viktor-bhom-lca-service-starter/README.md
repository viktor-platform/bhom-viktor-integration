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

powershell -ExecutionPolicy Bypass -File scripts\clone-bhom-repositories.ps1 `
  -RootDirectory C:\dev\bhom-lca

powershell -ExecutionPolicy Bypass -File scripts\build-gateway.ps1 `
  -RootDirectory C:\dev\bhom-lca
```

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
