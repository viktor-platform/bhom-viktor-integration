# Windows Revit gateway

This directory implements `BHoMRevitGateway.exe`, the fixed read-only bridge
between the `bhom_revit` Generic Worker executable and the official BHoM Revit
Toolkit listener. It follows the same CLI, event, manifest, build, and install
structure as the BHoM LCA gateway while using Revit-specific contracts.

The gateway targets .NET Framework 4.8 because the pinned BHoM v9.2 beta
`Revit_Adapter.dll` targets .NET Framework 4.7.2 and its socket serializer uses
runtime dynamic dispatch. Running that adapter directly from a .NET 8 console
host causes its internal `DataPackage` serialization to fall through to the
unsupported-object path before a Revit request reaches the listener.
Before opening the socket connection, the gateway also loads and indexes the
bundled BHoM `*_oM.dll` assemblies. The normal BHoM UI does this during startup;
the standalone gateway must do it explicitly so returned Revit objects resolve
to concrete `Wall`, `Floor`, `Material`, and `Construction` types instead of
fallback `CustomObject` instances.
Because BHoM's JSON writer can emit bare `NaN` or infinite numeric values, the
gateway normalizes those non-standard tokens to JSON `null` outside quoted
strings before producing worker artifacts. This keeps the raw BHoM object graph
valid JSON without changing legitimate text values.

## Why the worker belongs on the Revit machine

The BHoM Revit Toolkit loads a Revit plugin (`RevitListener`) and exposes the
Revit Adapter over local sockets after the user activates it from the BHoM
ribbon. The current toolkit supports Revit 2025. A VIKTOR cloud process cannot
reach that loopback listener directly, while a VIKTOR Generic Worker executable
on the Windows/Revit workstation can.

```text
VIKTOR producer app
  └─ GenericAnalysis(executable_key="bhom_revit")
      └─ Windows Generic Worker
          └─ BHoMRevitGateway.exe
              └─ Revit Adapter / RevitListener (localhost)
                  └─ active Revit 2025 document
```

## Implemented gateway behavior

1. Read only `revit-pull-request.json` from the isolated worker job directory.
2. Reject any operation except `pull_model_snapshot` and any Revit version
   except `2025`.
3. Confirm the expected active document name when one is supplied.
4. Map the category allow-list to BHoM/Revit Adapter requests.
5. Pull elements with a `RevitPullConfig` whose material-takeoff option is on.
6. Preserve BHoM objects and `RevitPulledParameters` in
   `revit-elements.bhom.json` using the BHoM serializer.
7. Read each `VolumetricMaterialTakeoff` fragment and aggregate it into one
   `BH.oM.Physical.Materials.GeneralMaterialTakeoff` for `takeoff.bhom.json`.
8. Derive `revit-metadata.json` from the pulled objects. Metadata is a stable UI
   projection; it is not a replacement BHoM object model.
9. Write events and a runtime manifest even when a pull fails after request
   parsing.

## Security and operating rules

- The executable key, DLL set, BHoM method, and listener ports are fixed in the
  installed gateway. Request JSON cannot select them.
- Run with `maxParallelProcesses: 1`: Revit API access is serialized and one
  Revit instance owns a listener port pair.
- This first operation is read-only. Do not implement Push or Remove behind the
  same request profile.
- Compile the Revit Toolkit for its `2025` configuration and pin one BHoM
  runtime set. Record assembly hashes in the manifest.
- Do not expose RevitListener ports outside the Windows host.

## Build and install

From the sample root in Administrator PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-gateway.ps1
powershell -ExecutionPolicy Bypass -File worker\install-gateway.ps1
powershell -ExecutionPolicy Bypass -File worker\diagnose.ps1
```

Merge `worker/config.example.yaml` into the VIKTOR Generic Worker configuration
and restart the worker. The gateway executable is installed at
`C:\Services\BHoMRevitGateway\BHoMRevitGateway.exe`.

## Windows acceptance

- Start Revit 2025, open the intended document, and activate the BHoM listener.
- Execute one fixed sample through the installed worker and validate every BHoM
  output with the matching `BHoM_JSONSchema` commit.
- Confirm quantities are SI (`m`, `m²`, `m³`, `kg`) before calling the LCA app.
- Confirm linked-model behavior and decide whether linked elements are excluded
  or namespaced in a later contract revision.
