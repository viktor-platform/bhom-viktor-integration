# Starter-package validation

**Validation date:** July 13, 2026

## Completed in the build environment

- All checked-in JSON files parse successfully.
- `service-request.schema.json` and `normalized-result.schema.json` validate the supplied service samples.
- Python source compiles under Python 3.13.
- The complete VIKTOR app imports with VIKTOR SDK 14.30.0.
- The contract, sample-arithmetic and Plotly tests pass.
- The standalone SOW and the copy inside the starter package are identical.

Run the Python checks after installing the requirements:

```powershell
python -m pytest
viktor-cli test
python -m compileall app.py lca_service scripts templates tests
dotnet run --project gateway/tests/BHoMLcaGateway.PortableTests
```

The portable .NET harness does not load BHoM assemblies. It validates the gateway
CLI and file boundary on any .NET 8 host; the calculation path remains part of the
required Windows verification below.

## Required Windows verification

The following checks require Windows, .NET 8 and a compatible local BHoM installation. They were not executed in the package-generation environment:

```powershell
python .\scripts\validate_bhom_json.py `
  --schema-root C:\dev\bhom-lca\external\BHoM_JSONSchema `
  --takeoff .\samples\takeoff.bhom.json `
  --materials .\samples\template-materials.bhom.json

powershell -ExecutionPolicy Bypass `
  -File .\scripts\build-gateway.ps1 `
  -RootDirectory C:\dev\bhom-lca

powershell -ExecutionPolicy Bypass `
  -File .\worker\run-local.ps1
```

The Windows acceptance run must produce:

```text
total_kgco2e = 19365
total_tco2e = 19.365
carbon_intensity_kgco2e_m2 = 38.73
```

A package is ready for deployment only after the gateway builds against the selected BHoM assemblies, the local BHoM schema validation passes, and the fixed worker sample returns these values.
