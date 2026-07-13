# VIKTOR BHoM LCA Service Starter

This repository contains the starter implementation for an independent VIKTOR life-cycle assessment service:

```text
VIKTOR app
    → VIKTOR Generic Worker
    → BHoMLcaGateway.exe
    → BHoM LifeCycleAssessment Toolkit
    → normalized JSON
    → Plotly and tables
```

The service accepts BHoM `GeneralMaterialTakeoff` JSON and template BHoM `Material` JSON. Revit is not required by this repository. A future Revit application can create the same takeoff files and call this app through the VIKTOR API.

## Included

- VIKTOR controller, parameters, worker client and Plotly views
- C# gateway source
- BHoM JSON sample files
- service JSON schemas
- BHoM schema validator
- source-clone script
- gateway build and install scripts
- worker configuration
- local sample runner
- Python tests
- implementation SOW
- package validation record
- operations and cross-app guides

## Development directory

Use:

```text
C:\dev\bhom-lca\
├── viktor-bhom-lca-service\
└── external\
    ├── LifeCycleAssessment_Toolkit\
    ├── BHoM_JSONSchema\
    ├── BHoM\
    └── BHoM_Engine\
```

Extract this starter package and initialize its repository:

```powershell
New-Item -ItemType Directory -Force C:\dev\bhom-lca | Out-Null
Expand-Archive `
  -Path .\viktor-bhom-lca-service-starter.zip `
  -DestinationPath C:\dev\bhom-lca `
  -Force
Rename-Item `
  C:\dev\bhom-lca\viktor-bhom-lca-service-starter `
  C:\dev\bhom-lca\viktor-bhom-lca-service
Set-Location C:\dev\bhom-lca\viktor-bhom-lca-service
powershell -ExecutionPolicy Bypass `
  -File .\scripts\initialize-service-repository.ps1
```

Obtain the external sources:

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\scripts\clone-bhom-repositories.ps1 `
  -RootDirectory C:\dev\bhom-lca
```

The script records exact commits in:

```text
C:\dev\bhom-lca\external-revisions.json
```

## Required software

### Development computer

- Windows 10 or Windows 11
- Git
- PowerShell 5.1 or PowerShell 7
- Python supported by the selected VIKTOR SDK
- VIKTOR CLI
- .NET 8 SDK
- a compatible BHoM installation
- LifeCycleAssessment Toolkit assemblies

### Worker computer

- Windows
- VIKTOR Generic Worker
- .NET 8 Runtime for the framework-dependent published gateway
- the published gateway package
- no Revit installation is required

## First setup

### 1. Create a Python environment

```powershell
Set-Location C:\dev\bhom-lca\viktor-bhom-lca-service
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Use a Python version accepted by the VIKTOR SDK installed in your organization.

### 2. Validate the service contracts

```powershell
python -m pytest
viktor-cli test
```

`pytest` runs the full contract, arithmetic, visualization and worker-mock suite.
`viktor-cli test` runs the `unittest`-based `GenericAnalysis` boundary tests through
the supported VIKTOR CLI test path.

### Portable .NET gateway checks

On Linux or Windows with the .NET 8 SDK, run:

```text
dotnet run --project gateway/tests/BHoMLcaGateway.PortableTests
```

This dependency-free harness checks command parsing, module selection, job-path
isolation, JSON I/O, event documents and runtime manifests. It does not replace
the Windows acceptance test: typed BHoM deserialization and `EnvironmentalResults`
still require the pinned BHoM assemblies and Windows worker runtime.

### 3. Validate sample BHoM JSON

```powershell
python .\scripts\validate_bhom_json.py `
  --schema-root C:\dev\bhom-lca\external\BHoM_JSONSchema `
  --takeoff .\samples\takeoff.bhom.json `
  --materials .\samples\template-materials.bhom.json
```

### 4. Confirm the local BHoM runtime

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\worker\diagnose.ps1
```

### 5. Build and publish the gateway

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\scripts\build-gateway.ps1 `
  -RootDirectory C:\dev\bhom-lca `
  -Configuration Release `
  -RuntimeIdentifier win-x64
```

### 6. Run the sample directly

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\worker\run-local.ps1
```

Expected result:

```text
total_kgco2e = 19365
total_tco2e = 19.365
carbon_intensity_kgco2e_m2 = 38.73
```

### 7. Start the VIKTOR app locally

```powershell
viktor-cli start
```

Local views require a mocked worker or a connected development worker. Pure contract and chart logic can be tested with `pytest`.

### 8. Install the gateway on the worker

Run PowerShell as Administrator:

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\worker\install-gateway.ps1 `
  -SourceDirectory .\gateway\publish\win-x64 `
  -TargetDirectory C:\Services\BHoMLcaGateway
```

Copy `worker\config.example.yaml` into the VIKTOR Generic Worker configuration and merge the `bhom_lca` executable entry. Restart the Generic Worker after changing its configuration.

## Input files

### `analysis-request.json`

Service settings, project information, metrics, modules and BHoM file names.

### `takeoff.bhom.json`

One serialized:

```text
BH.oM.Physical.Materials.GeneralMaterialTakeoff
```

### `template-materials.bhom.json`

A JSON array of serialized:

```text
BH.oM.Physical.Materials.Material
```

Each material can contain an:

```text
BH.oM.LifeCycleAssessment.MaterialFragments.EnvironmentalProductDeclaration
```

## Output files

- `analysis-result.json` — stable service result contract
- `bhom-results.json` — raw BHoM result array
- `analysis-events.json` — gateway events
- `runtime-manifest.json` — assembly versions and hashes

## Initial calculation

The gateway calls:

```csharp
takeoff.EnvironmentalResults(
    templateMaterials: templates,
    prioritiseTemplate: request.PrioritiseTemplateMaterials,
    metricFilter: metrics,
    evaluationConfig: null
);
```

The first profile supports `ClimateChangeTotal` and nonoverlapping module selections.

## Project documents

- [Statement of Work](SOW.md)
- [Operations](docs/OPERATIONS.md)
- [Calling from another VIKTOR app](docs/VIKTOR_APP_INTEGRATION.md)
- [BHoM contract notes](docs/BHOM_CONTRACTS.md)
- [Third-party references](docs/THIRD_PARTY_REFERENCES.md)

## External references

- https://github.com/BHoM/LifeCycleAssessment_Toolkit
- https://github.com/BHoM/BHoM_JSONSchema
- https://github.com/BHoM/BHoM
- https://github.com/BHoM/BHoM_Engine
- https://docs.viktor.ai/docs/create-apps/software-integrations/generic/
- https://docs.viktor.ai/docs/api/sdk/running-entity-computation/
- https://docs.viktor.ai/docs/create-apps/results-and-visualizations/plots-charts-graphs/

## Data notice

The sample environmental factors are synthetic acceptance-test values. Replace them with verified, project-approved EPD data before any real assessment or report.
