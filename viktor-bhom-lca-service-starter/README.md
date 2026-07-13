# VIKTOR - BHoM - LCA Analysis

![Thumbnail](assets/thumbnail.png)

Life-cycle assessment (LCA) carbon analysis powered by BHoM and VIKTOR.

---

## Setup

### Prerequisites

| Tool | Where |
|------|-------|
| BHoM v9 | https://bhom.xyz → Download → run installer |
| .NET 8 SDK | https://dotnet.microsoft.com/download |
| Git | https://git-scm.com |
| PowerShell 5.1+ | built-in on Windows 10/11 |

### 1. Clone and Build the Gateway

```powershell
# Clone this repo
git clone <repo-url> C:\dev\bhom-lca\viktor-bhom-lca-service
cd C:\dev\bhom-lca\viktor-bhom-lca-service

# Clone BHoM source (LCA Engine + JSON schemas)
powershell -ExecutionPolicy Bypass -File scripts\clone-bhom-repositories.ps1 -RootDirectory C:\dev\bhom-lca

# Build and publish the gateway
powershell -ExecutionPolicy Bypass -File scripts\build-gateway.ps1 -RootDirectory C:\dev\bhom-lca
```

---

## VIKTOR Generic Worker

### 2. Install the Gateway

The gateway must be installed to `C:\Services\BHoMLcaGateway` for the VIKTOR worker to access it.

```powershell
# Run as Administrator
powershell -ExecutionPolicy Bypass -File worker\install-gateway.ps1
```

### 3. Configure the Generic Worker

Edit the Generic Worker config (default location):

```
%LOCALAPPDATA%\Viktor\VIKTOR - generic (v6.1.0)\config.yaml
```

Replace the content with:

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
    workingDirectoryPath: ''

maxParallelProcesses: 2
```

### 4. Verify the Worker

```powershell
powershell -ExecutionPolicy Bypass -File worker\run-local.ps1
# Expected output: total_kgco2e = 19365
```

---

## VIKTOR App

### 5. Create and Start the App

```powershell
# Create the VIKTOR app (first time only)
viktor-cli create-app "BHoM LCA Carbon Analysis" --registered-name bhom-lca-carbon-analysis

# Install dependencies and start development
viktor-cli clean-start
```

### 6. Using the App

1. **Upload files**:
   - `samples/takeoff.bhom.json` → BHoM material takeoff
   - `samples/template-materials.bhom.json` → EPD template materials

2. **Configure analysis**:
   - Set project info (ID, name, gross floor area)
   - Select life-cycle modules (A1, A2, A3)

3. **Run**:
   - Click **"Run and download normalized JSON"**

4. **View results**:
   - **Summary** → Total emissions (kgCO2e, tCO2e, carbon intensity)
   - **Analysis chart** → Visualization by material/EPD/module
   - **Detailed records** → Table breakdown

---

## Troubleshooting

### Different BHoM Version

| What changed | What to update |
|---|---|
| `Dimensional_oM` no longer needed | Remove it from `BHoMLcaGateway.csproj` references |
| Result properties back to `A1`/`A2`/`A3` (pre-v9) | Revert `ResultNormalizer.cs` to use reflection on individual properties instead of `Indicators` dict |
| `System.Drawing.Common` no longer a BHoM dep | Remove the `runtimeconfig.json` patch block in `build-gateway.ps1` |
| New module enum values | Update `ModuleSelection.cs` allowed list |
