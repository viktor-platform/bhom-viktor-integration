# BHoM JSON contracts

## Authority

BHoM object payloads are checked against the schemas generated in:

```text
https://github.com/BHoM/BHoM_JSONSchema
```

The service keeps only a manifest of expected paths. It does not copy generated BHoM schemas into this repository.

## Required inputs

### General material takeoff

File: `takeoff.bhom.json`

```json
{
  "_t": "BH.oM.Physical.Materials.GeneralMaterialTakeoff",
  "Name": "Project takeoff",
  "MaterialTakeoffItems": []
}
```

`MaterialTakeoffItems` must contain serialized `BH.oM.Physical.Materials.TakeoffItem` objects. The current BHoM schema requires material, volume, mass, area, length, item count, current, energy, power and volumetric flow rate on every takeoff item.

### Template materials

File: `template-materials.bhom.json`

```json
[
  {
    "_t": "BH.oM.Physical.Materials.Material",
    "Name": "Concrete C30/37",
    "Density": 2400.0,
    "Properties": []
  }
]
```

Each template material used for LCA must contain an `EnvironmentalProductDeclaration` in `Properties`.

### Environmental Product Declaration

```json
{
  "_t": "BH.oM.LifeCycleAssessment.MaterialFragments.EnvironmentalProductDeclaration",
  "Name": "Verified EPD name",
  "Type": "Product",
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
```

For a mass-based EPD, metric factors are interpreted per kilogram. Takeoff masses use kilograms. The service does not convert imperial units.

## Type discriminators

The BHoM schema marks `_t` as optional, but this service requires it at the input boundary because the BHoM serializer needs a deterministic concrete type. Do not remove `_t` from sample or producer files.

## Validation command

```powershell
python .\scripts\validate_bhom_json.py `
  --schema-root C:\dev\bhom-lca\external\BHoM_JSONSchema `
  --takeoff .\samples\takeoff.bhom.json `
  --materials .\samples\template-materials.bhom.json
```

The validator registers the local schema clone and resolves BHoM `$ref` links without downloading schemas during a test run.

## Versioning

- Record the exact BHoM schema commit in `external-revisions.json`.
- Record runtime assembly versions and hashes in `runtime-manifest.json`.
- Treat a change to required BHoM fields or type names as a contract change.
- Keep `schema_version` for service contracts separate from `_bhomVersion` used by BHoM serialization.

## Service result

`analysis-result.json` is intentionally not a BHoM object. It is a stable, long-form result contract for VIKTOR charts, tables and calling apps. `bhom-results.json` remains available when a caller requires the original BHoM material result objects.
