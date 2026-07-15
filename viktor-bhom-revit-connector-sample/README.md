# VIKTOR BHoM Revit 2025 connector sample

A read-only VIKTOR producer app for pulling a Revit 2025 model through BHoM,
reviewing model metadata, and preparing the existing carbon-analysis app's BHoM
LCA input.

The app runs immediately with a bundled fixture. Live Revit extraction uses a
fixed VIKTOR Generic Worker executable named `bhom_revit`; the Windows gateway
implementation and Revit/BHoM acceptance test are the next Windows-only work
package.

## What is included

- A VIKTOR WebView model audit with category filtering, element search, BHoM
  type/GUID traceability, Revit parameters, and material quantities.
- A VIKTOR DataView with source runtime, element/parameter counts, and aggregate
  takeoff totals.
- A strict Revit 2025 pull-request contract with category allow-list, element
  limit, expected-document guard, material takeoff enabled, and geometry disabled.
- A `bhom_revit` Generic Worker client that collects raw BHoM elements, normalized
  metadata, `GeneralMaterialTakeoff`, events, and the runtime manifest.
- A bundled mock gateway result and synthetic test EPDs.
- An LCA handoff builder whose `params` match `app/carbon-analysis` method
  `run_analysis` exactly.
- A reusable `call_lca_service()` helper for the separately deployed carbon app.
- JSON schemas and tests for the producer-side contract.

## Architecture

```text
Revit 2025
  └─ BHoM Revit Toolkit + activated RevitListener
      └─ BHoMRevitGateway.exe on Windows Generic Worker (`bhom_revit`)
          └─ this VIKTOR producer
              └─ carbon-analysis.run_analysis
                  └─ BHoM LCA gateway (`bhom_lca`)
                      └─ EnvironmentalResults()
```

The producer does not calculate carbon. It produces the BHoM
`GeneralMaterialTakeoff` already accepted by the LCA app. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the payload boundaries and
[`gateway/README.md`](gateway/README.md) for the Windows implementation contract.
The exact upstream commits inspected are recorded in
[`docs/SOURCE_REVISIONS.md`](docs/SOURCE_REVISIONS.md).

## Run the bundled sample

From this folder:

```bash
python3.13 -m venv venv
venv/bin/pip install -r requirements.txt
viktor-cli create-app "BHoM Revit 2025 Connector Sample" \
  --registered-name bhom-revit-2025-connector-sample
viktor-cli clean-start
```

Leave **Connection mode** as **Bundled sample**. The app does not need Revit or a
worker in that mode.

## Run the checks

```bash
uvx ruff format .
uvx ruff check .
uvx ty check --python venv/bin/python
venv/bin/python -m pytest
viktor-cli test
```

If reusing the environment from `../viktor-bhom-lca-service-starter`, pass that
Python path to `ty` and `pytest` instead of creating a second environment.

## Connect Revit 2025

1. Install one compatible, pinned BHoM release and the Revit Toolkit build for
   Revit 2025 on the Windows workstation.
2. Start Revit 2025, open the intended model, and activate **Revit Listener** in
   the BHoM ribbon. BHoM's documentation describes default local ports 14128 and
   14129; keep them local to the workstation.
3. Implement/build the gateway against the pinned toolkit client API and install
   it at `C:\Services\BHoMRevitGateway`.
4. Merge [`gateway/config.example.yaml`](gateway/config.example.yaml) into the
   Generic Worker config and restart the worker.
5. Switch the app to **Revit 2025 worker** and first test with a small category
   set and an exact expected document name.
6. Validate the raw objects and takeoff with the `BHoM_JSONSchema` commit that
   matches the pinned runtime.

The public Revit Toolkit source confirms support for Revit 2025 and describes
Adapter/RevitListener socket communication. Its material-takeoff pull attaches a
`VolumetricMaterialTakeoff` fragment to each BHoM object. The Windows gateway must
use the pinned adapter API instead of reimplementing an undocumented socket wire
protocol.

## Send data to carbon-analysis

The **Build carbon-analysis handoff** action downloads `lca-handoff.json`. For a
deployed integration, pass that object's `params` to the carbon entity:

```python
response = call_lca_service(
    location=LcaServiceLocation(
        token=os.environ["VIKTOR_LCA_TOKEN"],
        workspace_id=int(os.environ["VIKTOR_LCA_WORKSPACE_ID"]),
        entity_id=int(os.environ["VIKTOR_LCA_ENTITY_ID"]),
    ),
    handoff=handoff,
)
```

Keep the token out of parameters, WebView HTML, downloads, logs, and source
control. Inline takeoff JSON is appropriate for this sample. Before production,
measure large Revit payloads and version a VIKTOR entity/file-reference contract.

## Data notice

The bundled Revit model data and EPD factors are synthetic test fixtures. They are
not approved for project reporting. The raw BHoM element fixture is deliberately
trimmed for UI/contract tests; the live gateway must write complete objects with
the BHoM serializer and validate them against the pinned schemas.

## Primary references

- [BHoM Revit Toolkit](https://github.com/BHoM/Revit_Toolkit)
- [BHoM Revit Toolkit documentation](https://bhom.xyz/documentation/Guides-and-Tutorials/Visual-Programming-with-BHoM/Revit%20Toolkit/)
- [Pull of material takeoffs](https://bhom.xyz/documentation/Guides-and-Tutorials/Visual-Programming-with-BHoM/Revit%20Toolkit/Pull/Material%20Takeoffs/)
- [BHoM LCA Toolkit](https://github.com/BHoM/LifeCycleAssessment_Toolkit)
- [BHoM JSON schemas](https://github.com/BHoM/BHoM_JSONSchema)
