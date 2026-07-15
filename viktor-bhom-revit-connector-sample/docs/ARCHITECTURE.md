# Revit producer architecture and LCA connection

## Decision

Use two independent VIKTOR apps and two independent Windows boundaries:

```text
Revit 2025 + BHoM Revit Toolkit
  │ local RevitListener / Adapter
  ▼
BHoMRevitGateway.exe (`bhom_revit` worker executable)
  │ raw BHoM array + metadata projection + GeneralMaterialTakeoff
  ▼
VIKTOR Revit producer (this folder)
  │ `run_analysis` params / VIKTOR entity compute
  ▼
VIKTOR carbon-analysis app (`app/carbon-analysis`)
  │ `bhom_lca` worker executable
  ▼
BHoM LCA gateway → `EnvironmentalResults()`
```

The producer owns extraction, traceability, and takeoff aggregation. The LCA app
continues to own EPD matching, module selection, BHoM calculation, and normalized
carbon results. The producer must not reproduce `EnvironmentalResults()` in
Python or C#.

## Three payloads, three jobs

| File | Role | Authority |
|---|---|---|
| `revit-elements.bhom.json` | Lossless BHoM-serialized objects returned by the Revit Adapter | Pinned BHoM serializer and object schemas |
| `revit-metadata.json` | Small, stable projection for VIKTOR WebView/DataView | This producer contract |
| `takeoff.bhom.json` | Aggregated `GeneralMaterialTakeoff` consumed by carbon-analysis | BHoM Physical_oM schema and the LCA service contract |

Keeping the UI projection separate prevents Revit parameter names from becoming
calculation properties. It also lets the gateway retain `RevitPulledParameters`
without forcing the browser to understand every BHoM fragment.

## Material flow

Current Revit Toolkit source attaches a
`BH.oM.Physical.Materials.VolumetricMaterialTakeoff` fragment to each pulled
object when the pull configuration enables material takeoff. That fragment has
parallel `Materials` and `Volumes` collections. The gateway aggregates equal
materials into BHoM `TakeoffItem` records and derives mass as
`volume × material density` only when a compatible density is present.

The LCA handoff uses the carbon app's existing parameter names exactly:

- `project_id`
- `project_name`
- `gross_floor_area_m2`
- `modules`
- `prioritise_template_materials`
- `takeoff_json`
- `template_materials_json`
- `chart_type`
- `group_by`

For small samples these are inline strings. Before production-scale Revit models,
measure the deployed VIKTOR payload limit and add a versioned entity/file-reference
contract instead of silently increasing inline payloads.

## Parameter philosophy

Pulled Revit parameters are metadata. Physical BHoM properties and material
quantities are calculation inputs. Do not flatten both into one dictionary.
This is consistent with the Revit Toolkit's dedicated
`RevitPulledParameters`/`RevitParametersToPush` fragments and avoids the old
property-vs-parameter overwrite conflict. This producer is read-only, so it never
creates `RevitParametersToPush`.

## Version pinning

Pin and record all of these together for a Windows release:

- Revit 2025 build
- BHoM installer/release
- Revit Toolkit commit and 2025 build configuration
- BHoM JSON Schema commit
- Revit gateway build/hash
- LCA gateway build/hash

A change to any of those items requires rerunning the Revit pull fixture, BHoM
schema validation, and the LCA fixed-sample acceptance test.
