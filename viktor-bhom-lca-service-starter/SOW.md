# Statement of Work: VIKTOR BHoM Life-Cycle Assessment Service

**Status:** Approved implementation scope<br>
**Service:** Independent VIKTOR application for BHoM life-cycle assessment<br>
**Initial release:** Climate Change Total, modules A1, A2 and A3<br>
**Primary runtime:** Windows VIKTOR Generic Worker and a C# gateway<br>
**Future producer:** A separate VIKTOR application that obtains material takeoffs from Revit 2025

## 1. Purpose

Create an independent VIKTOR application that receives BHoM material-takeoff JSON, sends the calculation to a Windows Generic Worker, runs selected methods from the BHoM LifeCycleAssessment Toolkit, returns normalized results, and presents configurable Plotly charts and result tables.

The service is designed as a calculation boundary. It does not connect to Revit in this scope. A later Revit application will produce the same input contract and call the service through the VIKTOR API.

## 2. Source repositories and implementation references

The implementation agent shall use these sources:

| Purpose | Reference |
|---|---|
| BHoM LCA methods and object model | https://github.com/BHoM/LifeCycleAssessment_Toolkit |
| BHoM JSON schemas | https://github.com/BHoM/BHoM_JSONSchema |
| BHoM core object model | https://github.com/BHoM/BHoM |
| BHoM engines, including the JSON serializer | https://github.com/BHoM/BHoM_Engine |
| VIKTOR Generic Worker | https://docs.viktor.ai/docs/create-apps/software-integrations/generic/ |
| VIKTOR entity computation | https://docs.viktor.ai/docs/api/sdk/running-entity-computation/ |
| VIKTOR Plotly views | https://docs.viktor.ai/docs/create-apps/results-and-visualizations/plots-charts-graphs/ |
| VIKTOR worker installation | https://docs.viktor.ai/docs/create-apps/software-integrations/generic/worker/ |

The `develop` branches are used for the first implementation because the referenced JSON schemas and LCA method signatures are published there. Every build shall record the exact Git commit for each cloned repository. Production releases shall use tested commits or release tags, not a moving branch name.

## 3. Repository placement

Use this Windows directory structure on the development machine:

```text
C:\dev\bhom-lca\
├── viktor-bhom-lca-service\
└── external\
    ├── LifeCycleAssessment_Toolkit\
    ├── BHoM_JSONSchema\
    ├── BHoM\
    └── BHoM_Engine\
```

Create the service repository from the supplied starter archive:

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
powershell -ExecutionPolicy Bypass `
  -File .\scripts\clone-bhom-repositories.ps1 `
  -RootDirectory C:\dev\bhom-lca
```

The initialization script creates the local Git repository and initial commit. Git `user.name` and `user.email` must already be configured. A repository administrator can later run the same script with `-RemoteUrl` to set the approved origin URL.

The supplied clone script creates `C:\dev\bhom-lca\external`, obtains the required BHoM repositories, and writes `external-revisions.json` with the checked-out commit hashes.

The normal gateway build reads BHoM assemblies from:

```text
C:\ProgramData\BHoM\Assemblies
```

The source clones support inspection, schema validation, controlled toolkit builds, and debugging. They shall not be loaded dynamically by a worker job.

## 4. System architecture

```text
Calling VIKTOR app or manual upload
                 │
                 │ BHoM JSON files + analysis request
                 ▼
┌──────────────────────────────────────┐
│ VIKTOR LCA application              │
│                                      │
│ • validates the service request      │
│ • invokes GenericAnalysis            │
│ • reads normalized results           │
│ • creates Plotly views               │
│ • exposes a callable button method   │
└───────────────────┬──────────────────┘
                    │
                    │ executable_key = bhom_lca
                    ▼
┌──────────────────────────────────────┐
│ VIKTOR Generic Worker               │
│ Windows                              │
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│ BHoMLcaGateway.exe                  │
│                                      │
│ • reads BHoM JSON                    │
│ • deserializes BHoM objects          │
│ • calls EnvironmentalResults         │
│ • writes raw BHoM results            │
│ • writes normalized result records   │
│ • writes runtime and event files     │
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│ Pinned BHoM runtime                 │
│                                      │
│ • LifeCycleAssessment_Engine         │
│ • LifeCycleAssessment_oM             │
│ • Physical_oM                        │
│ • Matter_Engine                      │
│ • Serialiser_Engine                  │
│ • dependent BHoM assemblies          │
└──────────────────────────────────────┘
```

The worker is job-oriented. The VIKTOR application sends files to a registered executable and collects declared result files. The gateway is not an externally accessible HTTP service.

## 5. Contracts

### 5.1 Worker inputs

Each calculation job shall contain:

1. `analysis-request.json` — service settings and file names.
2. `takeoff.bhom.json` — one serialized `BH.oM.Physical.Materials.GeneralMaterialTakeoff`.
3. `template-materials.bhom.json` — a JSON array of serialized `BH.oM.Physical.Materials.Material` objects with LCA material properties.

The BHoM JSON schemas are the external compatibility authority for BHoM objects. The application also performs fast local checks before sending a job. Full schema validation is available through `scripts/validate_bhom_json.py`.

### 5.2 Worker outputs

Each successful job shall return:

1. `analysis-result.json` — normalized records for VIKTOR and other calling applications.
2. `bhom-results.json` — raw serialized BHoM material results.
3. `analysis-events.json` — gateway warnings, notes and errors.
4. `runtime-manifest.json` — assembly names, versions, file names and SHA-256 hashes.

### 5.3 Initial analysis request

```json
{
  "schema_version": "1.0",
  "job_id": "e2bb16f4-bb1c-57b6-9beb-36efb1c58be6",
  "analysis_profile": "general_environmental_results",
  "takeoff_filename": "takeoff.bhom.json",
  "template_materials_filename": "template-materials.bhom.json",
  "prioritise_template_materials": true,
  "metric_filters": ["ClimateChangeTotal"],
  "modules": ["A1", "A2", "A3"],
  "project": {
    "project_id": "sample-office",
    "project_name": "Sample Office",
    "gross_floor_area_m2": 500.0
  }
}
```

### 5.4 BHoM takeoff template

```json
{
  "_t": "BH.oM.Physical.Materials.GeneralMaterialTakeoff",
  "Name": "Sample project takeoff",
  "MaterialTakeoffItems": [
    {
      "_t": "BH.oM.Physical.Materials.TakeoffItem",
      "Material": {
        "_t": "BH.oM.Physical.Materials.Material",
        "Name": "Concrete C30/37",
        "Density": 2400.0,
        "Properties": []
      },
      "Volume": 10.0,
      "Mass": 24000.0,
      "Area": 0.0,
      "Length": 0.0,
      "NumberItem": 1,
      "ElectricCurrent": 0.0,
      "Energy": 0.0,
      "Power": 0.0,
      "VolumetricFlowRate": 0.0
    }
  ]
}
```

### 5.5 BHoM material and EPD template

```json
[
  {
    "_t": "BH.oM.Physical.Materials.Material",
    "Name": "Concrete C30/37",
    "Density": 2400.0,
    "Properties": [
      {
        "_t": "BH.oM.LifeCycleAssessment.MaterialFragments.EnvironmentalProductDeclaration",
        "Name": "Sample concrete EPD",
        "Type": "Sector",
        "QuantityType": "Mass",
        "EnvironmentalMetrics": [
          {
            "_t": "BH.oM.LifeCycleAssessment.MaterialFragments.ClimateChangeTotalMetric",
            "A1": 0.05,
            "A2": 0.01,
            "A3": 0.06,
            "A1toA3": 0.12
          }
        ]
      }
    ]
  }
]
```

The included factors are test data only. They shall not be used for project reporting.

## 6. BHoM execution

The gateway shall use the BHoM serializer for typed object creation:

```csharp
using BH.oM.Physical.Materials;
using BHoMSerialiser = BH.Engine.Serialiser.Convert;

string takeoffJson = File.ReadAllText(takeoffPath);
object? deserialized = BHoMSerialiser.FromJson(takeoffJson);

GeneralMaterialTakeoff takeoff = deserialized as GeneralMaterialTakeoff
    ?? throw new InvalidDataException(
        "takeoff.bhom.json is not a GeneralMaterialTakeoff.");
```

Template materials shall be deserialized from a JSON array:

```csharp
using BH.oM.Physical.Materials;
using BHoMSerialiser = BH.Engine.Serialiser.Convert;

string templateJson = File.ReadAllText(templatePath);
IEnumerable<object> deserializedTemplates =
    BHoMSerialiser.FromJsonArray(templateJson)
    ?? throw new InvalidDataException(
        "template-materials.bhom.json is not a JSON array.");

List<Material> templates = deserializedTemplates
    .Select(item => item as Material
        ?? throw new InvalidDataException(
            "Every template item must be a BHoM Material."))
    .ToList();
```

The initial calculation shall call the toolkit method directly:

```csharp
using BH.Engine.LifeCycleAssessment;
using BH.oM.LifeCycleAssessment;
using BH.oM.LifeCycleAssessment.Results;
using BH.oM.Physical.Materials;

List<MetricType> metrics = new()
{
    MetricType.ClimateChangeTotal
};

List<MaterialResult> results = takeoff.EnvironmentalResults(
    templateMaterials: templates,
    prioritiseTemplate: request.PrioritiseTemplateMaterials,
    metricFilter: metrics,
    evaluationConfig: null
);
```

Raw BHoM results shall be serialized with the same serializer:

```csharp
using BHoMSerialiser = BH.Engine.Serialiser.Convert;

string rawJson = BHoMSerialiser.ToJsonArray(results.Cast<object>());
File.WriteAllText(rawOutputPath, rawJson);
```

The gateway shall normalize selected result properties into a stable, long-form record model. Reflection is allowed only for converting known BHoM result classes into service records. It shall not be used to call arbitrary BHoM methods.

## 7. VIKTOR worker call

The VIKTOR application shall send the three input files and request four output files:

```python
from viktor.external.generic import GenericAnalysis

analysis = GenericAnalysis(
    files=[
        ("analysis-request.json", request_file),
        ("takeoff.bhom.json", takeoff_file),
        ("template-materials.bhom.json", template_file),
    ],
    executable_key="bhom_lca",
    output_filenames=[
        "analysis-result.json",
        "bhom-results.json",
        "analysis-events.json",
        "runtime-manifest.json",
    ],
)

analysis.execute(timeout=600)
result_file = analysis.get_output_file("analysis-result.json")
```

The worker configuration shall register the fixed executable:

```yaml
executables:
  bhom_lca:
    path: 'C:\Services\BHoMLcaGateway\BHoMLcaGateway.exe'
    arguments:
      - 'run'
      - '--request'
      - 'analysis-request.json'
      - '--output'
      - 'analysis-result.json'
      - '--raw-output'
      - 'bhom-results.json'
      - '--events'
      - 'analysis-events.json'
      - '--runtime-manifest'
      - 'runtime-manifest.json'

maxParallelProcesses: 2
```

Do not configure a shared working directory for the calculation command. The worker shall create a separate temporary job directory so concurrent calculations do not share files.

## 8. VIKTOR service interface

The same controller method shall support manual use and calls from another VIKTOR application. The method shall be a button method because VIKTOR entity computations can call button and view methods.

Example caller:

```python
from __future__ import annotations

from typing import Any

import viktor as vkt


def call_lca_service(
    *,
    token: str,
    workspace_id: int,
    entity_id: int,
    project_id: str,
    project_name: str,
    gross_floor_area_m2: float,
    takeoff_json: str,
    template_materials_json: str,
    timeout_seconds: int = 900,
) -> Any:
    api = vkt.api_v1.API(token=token)
    carbon_entity = api.get_entity(
        entity_id=entity_id,
        workspace_id=workspace_id,
    )
    return carbon_entity.compute(
        method_name="run_analysis",
        params={
            "project_id": project_id,
            "project_name": project_name,
            "gross_floor_area_m2": gross_floor_area_m2,
            "modules": ["A1", "A2", "A3"],
            "prioritise_template_materials": True,
            "takeoff_json": takeoff_json,
            "template_materials_json": template_materials_json,
            "chart_type": "Stacked bar",
            "group_by": "Material",
        },
        timeout=timeout_seconds,
    )
```

A complete reusable version is supplied in `templates/calling_app_client.py`.

For large Revit takeoffs, the producer shall store the JSON as a workspace file or on an entity and send an entity or file reference rather than a large inline string. The initial sample supports both uploaded files and inline JSON for development and API testing.

## 9. Visualization

Plotly runs in the VIKTOR app, not in the C# gateway. The gateway returns calculation records with:

```text
material
environmental_product_declaration
metric
module
value
unit
```

The initial interface shall provide:

- summary values for total kgCO2e, total tCO2e and kgCO2e/m²;
- a configurable bar or stacked-bar chart;
- treemap and sunburst views;
- grouping by material, EPD or module;
- a detailed result table;
- downloadable normalized JSON;
- downloadable raw BHoM JSON;
- downloadable events and runtime information.

Example:

```python
import plotly.express as px
import viktor as vkt

figure = px.bar(
    frame,
    x="material",
    y="value",
    facet_col=None,
    barmode="stack",
    pattern_shape="module",
)
return vkt.PlotlyResult(figure)
```

## 10. Scope

### 10.1 Included

- One independent VIKTOR LCA application.
- One Windows C# command-line gateway.
- One Generic Worker executable registration.
- BHoM JSON input validation.
- BHoM typed deserialization.
- `GeneralMaterialTakeoff.EnvironmentalResults`.
- Climate Change Total.
- Modules A1, A2 and A3.
- Raw and normalized result files.
- Plotly views and result table.
- Manual upload mode.
- Callable VIKTOR button method.
- Sample takeoff and EPD data.
- Build, install, diagnostic and validation scripts.
- Unit tests for contracts, result grouping and sample arithmetic.
- Exact source revision record.

### 10.2 Excluded

- Revit installation or extraction.
- Revit 2025 add-in code.
- SAP2000 integration.
- An HTTP server around the gateway.
- Automatic EPD sourcing.
- Authentication outside VIKTOR and its worker connection.
- Whole-life modules beyond the initial module set.
- Cost, transport, waste and IStructE profiles.
- Production certification of environmental data.
- Editing Revit objects with result values.

## 11. Functional requirements

| ID | Requirement |
|---|---|
| FR-01 | The app accepts a BHoM `GeneralMaterialTakeoff` JSON object. |
| FR-02 | The app accepts a BHoM JSON array of template `Material` objects. |
| FR-03 | The app validates the service request before worker execution. |
| FR-04 | The offline validator validates BHoM files against a cloned `BHoM_JSONSchema` repository. |
| FR-05 | The gateway rejects files that resolve outside the job directory. |
| FR-06 | The gateway calls `EnvironmentalResults` with selected metric filters. |
| FR-07 | The gateway rejects overlapping module selections such as A1, A2, A3 and A1toA3 in the same total. |
| FR-08 | The gateway writes all four declared output files. |
| FR-09 | A failed gateway command returns a nonzero process exit code. |
| FR-10 | Normalized results contain one record per result, metric and selected module. |
| FR-11 | The app can group result records without rerunning the BHoM calculation. |
| FR-12 | The app can be called through a VIKTOR button computation method. |
| FR-13 | Every result package includes gateway and BHoM assembly versions in `runtime-manifest.json`. |
| FR-14 | The worker uses a fixed `executable_key`; a job cannot choose an executable path. |

## 12. Nonfunctional requirements

| ID | Requirement |
|---|---|
| NFR-01 | A 10,000-item takeoff shall complete within the worker timeout agreed during performance testing. |
| NFR-02 | Each job uses an isolated working directory. |
| NFR-03 | All JSON files are UTF-8. |
| NFR-04 | Paths supplied in the request are relative file names only. |
| NFR-05 | Every release records source commits and assembly hashes. |
| NFR-06 | The service never executes a method or loads an assembly selected by request data. |
| NFR-07 | Error text identifies the failing contract, file or module. |
| NFR-08 | Calculation files are deterministic for the same input and pinned runtime. |
| NFR-09 | Test EPD data is marked as nonproduction data. |
| NFR-10 | Source and packaged runtime licensing notices are preserved. |

## 13. Work packages

### WP-01 — Repository and source lock

- Create the service repository from this scaffold.
- Run the clone script.
- Record exact commits.
- Install the agreed BHoM release.
- Confirm required assemblies in `C:\ProgramData\BHoM\Assemblies`.

**Acceptance:** `external-revisions.json` lists the checked-out commits and `diagnose.ps1` reports all required assemblies.

### WP-02 — Contracts and sample data

- Finalize `service-request.schema.json`.
- Finalize `normalized-result.schema.json`.
- Validate the sample BHoM takeoff and templates against the cloned BHoM schemas.
- Keep the initial sample arithmetic fixed.

**Acceptance:** all contract tests pass and the schema validator returns exit code 0.

### WP-03 — C# gateway

- Build command parsing.
- Add path checks.
- Add typed BHoM deserialization.
- Add the EnvironmentalResults execution.
- Add result normalization.
- Add raw result serialization.
- Add runtime manifest creation.
- Add structured events.
- Add the diagnose command.

**Acceptance:** the gateway produces the four output files and returns exit code 0 for the sample job.

### WP-04 — Generic Worker

- Publish the gateway as `win-x64`.
- Install files under `C:\Services\BHoMLcaGateway`.
- Register `bhom_lca` in the worker configuration.
- Restart the worker.
- Run the sample through VIKTOR.

**Acceptance:** VIKTOR receives all declared output files.

### WP-05 — VIKTOR application

- Add manual upload fields.
- Add inline development fields for remote computation.
- Add request creation and validation.
- Add the worker client.
- Add result caching for multiple views.
- Add summary, Plotly and table views.
- Add all four download actions.

**Acceptance:** a user can submit sample files once and open every view without creating inconsistent results.

### WP-06 — Cross-application contract

- Expose `run_analysis` as a VIKTOR button method.
- Document calling parameters and return shape.
- Add a small caller example.
- Test a call from a separate deployed VIKTOR workspace.

**Acceptance:** another VIKTOR app receives the normalized result response.

### WP-07 — Testing and handover

- Run Python tests.
- Run gateway tests on Windows.
- Test invalid schemas, missing EPDs, invalid modules and path traversal.
- Record deployment and rollback steps.
- Provide a sample runtime manifest.

**Acceptance:** the definition of done is satisfied.

## 14. Fixed sample acceptance result

The supplied sample uses:

```text
Concrete:
  volume = 10.0 m³
  density = 2400 kg/m³
  mass = 24,000 kg
  A1 = 0.05 kgCO2e/kg
  A2 = 0.01 kgCO2e/kg
  A3 = 0.06 kgCO2e/kg
  result = 2,880 kgCO2e

Steel:
  volume = 1.2 m³
  density = 7850 kg/m³
  mass = 9,420 kg
  A1 = 0.90 kgCO2e/kg
  A2 = 0.10 kgCO2e/kg
  A3 = 0.75 kgCO2e/kg
  result = 16,485 kgCO2e
```

Expected totals:

```text
Total = 19,365 kgCO2e
Total = 19.365 tCO2e
Gross floor area = 500 m²
Intensity = 38.73 kgCO2e/m²
```

These values are acceptance-test numbers, not environmental advice or approved EPD data.

## 15. Definition of done

The service is complete when:

1. The repository can be cloned into the stated directory structure.
2. The BHoM source revisions are recorded.
3. The sample BHoM JSON validates against the cloned schema repository.
4. The C# gateway builds on the Windows worker machine.
5. The diagnose command reports a compatible runtime.
6. The sample job produces the expected 19,365 kgCO2e total.
7. The normalized JSON validates against its service schema.
8. Raw BHoM results can be deserialized again with the pinned BHoM serializer.
9. VIKTOR displays summary, chart and table results.
10. All four output downloads work.
11. Another deployed VIKTOR app can call `run_analysis`.
12. Build, deployment, test and rollback instructions are committed.
13. No sample factor is presented as approved project data.
14. The worker only executes the registered gateway command.

## 16. Implementation-agent instructions

1. Begin with `README.md`, then read this SOW.
2. Run `scripts\clone-bhom-repositories.ps1`.
3. Run `scripts\validate_bhom_json.py` against the sample files.
4. Install or confirm the selected BHoM release.
5. Run `worker\diagnose.ps1`.
6. Run `scripts\build-gateway.ps1`.
7. Run `worker\run-local.ps1`.
8. Run `pytest`.
9. Start the VIKTOR app locally.
10. Install the published gateway on the worker.
11. Add the worker configuration and restart the worker.
12. Test the deployed VIKTOR entity.
13. Record actual commits and versions in the release notes.

Do not change BHoM contract property names to Python-style names. Do not calculate carbon in the VIKTOR presentation code. Do not send arbitrary class names or method names to the gateway. Add a new approved analysis profile in C# when another BHoM calculation is required.

## 17. Supplied scaffold and templates

The implementation package shall contain this structure:

```text
viktor-bhom-lca-service/
├── app.py
├── viktor.config.toml
├── requirements.txt
├── pyproject.toml
├── lca_service/
│   ├── contracts.py
│   ├── controller.py
│   ├── file_io.py
│   ├── parametrization.py
│   ├── service.py
│   ├── visualization.py
│   └── worker_client.py
├── gateway/
│   ├── BHoMLcaGateway.sln
│   └── src/BHoMLcaGateway/
├── contracts/
├── samples/
├── scripts/
├── worker/
├── templates/
├── tests/
├── docs/
├── AGENT_IMPLEMENTATION_GUIDE.md
├── README.md
└── SOW.md
```

The package includes:

- a VIKTOR controller and Plotly chart factory;
- a `GenericAnalysis` worker client;
- a C# command-line gateway template;
- service request and normalized-result schemas;
- BHoM takeoff and material templates;
- a caller module for a future Revit VIKTOR app;
- Windows scripts for cloning sources, building, installing, diagnosing and running the fixed sample;
- an offline validator for the cloned BHoM JSON schemas;
- Python acceptance tests and the fixed expected result.
