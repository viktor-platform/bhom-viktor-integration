# BHoM Revit Gateway installation

This gateway is installed by the administrator of the Windows VIKTOR Generic
Worker. VIKTOR web-app users do not install software locally.

## Requirements

- Windows x64
- Revit 2025
- BHoM v9.2.beta.0 with the Revit Toolkit
- Official BHoM Revit 2025 add-in registered for the current Windows user
- VIKTOR Generic Worker
- Administrator access for installation

## Install

From the repository sample directory in Administrator PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-gateway.ps1
powershell -ExecutionPolicy Bypass -File worker\install-gateway.ps1
powershell -ExecutionPolicy Bypass -File worker\diagnose.ps1
```

Merge `config.example.yaml` into the Generic Worker configuration and restart
the worker. Keep `maxParallelProcesses: 1` because one Revit instance owns the
listener port pair.

For live acceptance, open exactly one Revit 2025 process, open the expected
document, activate **Revit Listener** in the BHoM ribbon, and run:

```powershell
powershell -ExecutionPolicy Bypass -File worker\run-local.ps1
```
