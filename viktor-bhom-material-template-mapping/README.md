# BHoM material template mapping

The second app in the sequential Revit-to-LCA workflow:

1. The Revit connector produces a BHoM `GeneralMaterialTakeoff`.
2. This app searches typed EPDs installed with BHoM, lets the user approve one EPD per material, and produces a typed BHoM `Material[]` template.
3. The LCA app consumes the takeoff, material template, and gross floor area.

## User flow

1. Upload `takeoff.bhom.json` or edit the material input table.
2. Choose the installed BHoM dataset scope and optionally refine each material's **Search query**.
3. Select **Search installed BHoM datasets**. A VIKTOR Generic Worker runs the .NET gateway.
4. Open **Mapping**. The interactive WebView shows the ranked EPD candidates returned for each source material.
5. Approve one EPD per material and select **Save to VIKTOR**.
6. Review **Validated template**, then download `template-materials.bhom.json` or `lca-handoff.json`.

The worker response is stored in `lookup_results_json`. The WebView writes approved BHoM GUIDs to `mapping_state_json` and a preview to `template_materials_json`. Export methods rebuild the final template from the worker's typed BHoM EPD payloads.

## Installed BHoM data

The gateway calls BHoM `Library_Engine.Query.Datasets` and reads the LifeCycleAssessment library installed under:

`C:\ProgramData\BHoM\Datasets\LifeCycleAssessment`

The selectable scopes are all installed LCA datasets, ICE, Boverket, local EC3 snapshots, EPiC, and Oekobaudat. The search is local: it does not call Carbon Query Database and does not require an API token.

## Windows Generic Worker

The executable key is `bhom_material_lookup`.

```powershell
.\scripts\build-gateway.ps1
.\worker\install-gateway.ps1
.\worker\diagnose.ps1
.\worker\run-local.ps1
.\scripts\test-lca-handoff.ps1
```

Merge `worker/config.example.yaml` into the Generic Worker configuration. See `worker/INSTALL.md` for the complete setup.

## Development

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
uvx ruff format .
uvx ruff check .
uvx ty check --python venv\Scripts\python.exe
venv\Scripts\python.exe -m pytest -q
viktor-cli test
viktor-cli start
```
