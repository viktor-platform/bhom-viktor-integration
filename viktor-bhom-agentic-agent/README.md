# BHoM agentic workflow

This VIKTOR coordinator runs a controlled BHoM workflow:

```text
Revit 2025 → GeneralMaterialTakeoff → installed BHoM EPD lookup → Material[] template → LCA result
```

It uses the three worker contracts already implemented in this repository:

- `bhom_revit` from `viktor-bhom-revit-connector-sample`
- `bhom_material_lookup` from `viktor-bhom-material-template-mapping`
- `bhom_lca` from `viktor-bhom-lca-service-starter`

The agent prepares typed handoffs and target links; it does not call VIKTOR APIs or run a Generic Worker. Review and explicitly approve EPD mappings in the mapping app before preparing the LCA handoff.

Set these VIKTOR app-environment variables after the three applications have been deployed. Their values are returned in the agent's handoff links and are never guessed in code:

- `VIKTOR_BHOM_REVIT_APP_URL`
- `VIKTOR_BHOM_MAPPING_APP_URL`
- `VIKTOR_BHOM_LCA_APP_URL`

## Run locally

```bash
python3.13 -m venv venv
venv/bin/pip install -r requirements.txt
viktor-cli create-app "BHoM Agentic Workflow" --registered-name bhom-agentic-agent
viktor-cli clean-start
```

The live workflow requires a Windows Generic Worker configured with all three executable keys. The agent cannot validate BHoM typed deserialization or `EnvironmentalResults()` on Linux.
