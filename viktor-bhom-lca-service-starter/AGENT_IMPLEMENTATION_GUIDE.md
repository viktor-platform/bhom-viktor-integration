# Implementation agent guide

## Objective

Deliver the independent VIKTOR BHoM LCA service described in `SOW.md`. Revit integration is not part of this repository. The service must run the BHoM `EnvironmentalResults` method through a Windows Generic Worker and return stable JSON for Plotly.

## Read first

1. `SOW.md`
2. `README.md`
3. `docs/BHOM_CONTRACTS.md`
4. `docs/OPERATIONS.md`
5. `docs/VIKTOR_APP_INTEGRATION.md`
6. `contracts/*.json`
7. `samples/*.json`

## Required source placement

```text
C:\dev\bhom-lca\
├── viktor-bhom-lca-service\
├── external-revisions.json
└── external\
    ├── LifeCycleAssessment_Toolkit\
    ├── BHoM_JSONSchema\
    ├── BHoM\
    └── BHoM_Engine\
```

Run:

```powershell
Set-Location C:\dev\bhom-lca\viktor-bhom-lca-service
powershell -ExecutionPolicy Bypass -File .\scripts\clone-bhom-repositories.ps1 -RootDirectory C:\dev\bhom-lca
```

Do not copy source repositories into the VIKTOR app package. The worker uses compiled, version-compatible assemblies.

## Build order

### 1. Contract tests

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest
```

### 2. BHoM schema validation

```powershell
python .\scripts\validate_bhom_json.py `
  --schema-root C:\dev\bhom-lca\external\BHoM_JSONSchema `
  --takeoff .\samples\takeoff.bhom.json `
  --materials .\samples\template-materials.bhom.json
```

### 3. Gateway build

Install a compatible BHoM release and LCA Toolkit so `C:\ProgramData\BHoM\Assemblies` contains the required object model and engine DLLs. Then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-gateway.ps1 `
  -RootDirectory C:\dev\bhom-lca `
  -Configuration Release `
  -RuntimeIdentifier win-x64
```

### 4. Fixed sample

```powershell
powershell -ExecutionPolicy Bypass -File .\worker\run-local.ps1
```

The result must be exactly within floating-point tolerance:

```text
total_kgco2e = 19365
total_tco2e = 19.365
carbon_intensity_kgco2e_m2 = 38.73
```

### 5. Worker installation

```powershell
powershell -ExecutionPolicy Bypass -File .\worker\install-gateway.ps1 `
  -SourceDirectory .\gateway\publish\win-x64 `
  -TargetDirectory C:\Services\BHoMLcaGateway
```

Merge `worker\config.example.yaml` into the Generic Worker configuration and restart the worker.

### 6. VIKTOR test

Start the VIKTOR app, load the two BHoM sample files, run the summary and chart views, and download all four worker artifacts.

## Coding boundaries

- Do not invoke arbitrary BHoM methods by reflection.
- Do not accept executable or DLL paths from VIKTOR parameters.
- Keep `analysis_profile` fixed to `general_environmental_results` in release 1.
- Keep the first metric fixed to `ClimateChangeTotal`.
- Reject `A1toA3` combined with A1, A2 or A3.
- Keep Plotly code in Python.
- Keep BHoM deserialization and calculations in C#.
- Preserve `analysis-result.json` property names.
- Preserve `_t` on all BHoM inputs.
- Return nonzero process exit codes on failures.
- Write events and runtime manifests even when calculation input is invalid, when command parsing permits it.

## Work packages

### Package A: repository and contracts

- Run source-clone script.
- Record exact commits.
- Validate all sample JSON.
- Add contract-change tests before modifying schemas.

### Package B: C# gateway

- Confirm serializer method signatures against the pinned BHoM Engine commit.
- Confirm `EnvironmentalResults` signature against the pinned LCA toolkit commit.
- Build against one BHoM runtime set.
- Run `diagnose` and the fixed sample.

### Package C: VIKTOR application

- Confirm VIKTOR SDK compatibility with Python 3.13.
- Configure Generic Worker executable key `bhom_lca`.
- Verify file uploads and inline JSON modes.
- Verify summary, chart, table and artifact downloads.

### Package D: deployed service call

- Deploy the LCA app to a separate workspace.
- Use `templates/calling_app_client.py` from a producer app.
- Confirm the actual entity-computation response type.
- Add file-reference input in a later contract revision if Revit payload size requires it.

## Required evidence for handover

- `external-revisions.json`
- successful `pytest` output
- BHoM schema validation output
- gateway build output
- fixed sample output
- deployed worker diagnostic output
- screenshots of VIKTOR summary, chart and table
- downloaded worker artifacts
- production EPD data-source approval record

## Change control

When any BHoM commit, assembly, calculation method, service contract or normalization rule changes:

1. update the revision or runtime manifest;
2. update tests;
3. run the fixed sample;
4. increment `CACHE_VERSION`;
5. publish a new gateway package;
6. deploy through the documented rollback-capable process.
