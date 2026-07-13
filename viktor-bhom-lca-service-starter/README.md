# BHoM LCA Gateway — Install Guide

**Tested with: BHoM v9 (assemblies 9.0.0.0), .NET 8 SDK, Windows 10/11**

## Prerequisites

| Tool | Where |
|------|-------|
| BHoM v9 | https://bhom.xyz → Download → run installer |
| .NET 8 SDK | https://dotnet.microsoft.com/download |
| Git | https://git-scm.com |
| PowerShell 5.1+ | built-in on Windows 10/11 |

## First-time setup

```powershell
# 1. Clone this repo and enter it
git clone <repo-url> C:\dev\bhom-lca\viktor-bhom-lca-service
cd C:\dev\bhom-lca\viktor-bhom-lca-service

# 2. Clone BHoM source (LCA Engine + JSON schemas)
powershell -ExecutionPolicy Bypass -File scripts\clone-bhom-repositories.ps1 -RootDirectory C:\dev\bhom-lca

# 3. Build and publish the gateway
powershell -ExecutionPolicy Bypass -File scripts\build-gateway.ps1 -RootDirectory C:\dev\bhom-lca

# 4. Verify — should print total_kgco2e = 19365
powershell -ExecutionPolicy Bypass -File worker\run-local.ps1
```

## If using a different BHoM version

| What changed | What to update |
|---|---|
| `Dimensional_oM` no longer needed | Remove it from `BHoMLcaGateway.csproj` references |
| Result properties back to `A1`/`A2`/`A3` (pre-v9) | Revert `ResultNormalizer.cs` to use reflection on individual properties instead of `Indicators` dict |
| `System.Drawing.Common` no longer a BHoM dep | Remove the `runtimeconfig.json` patch block in `build-gateway.ps1` |
| New module enum values | Update `ModuleSelection.cs` allowed list |
