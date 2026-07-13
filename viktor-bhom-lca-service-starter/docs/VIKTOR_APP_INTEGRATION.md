# Calling the LCA service from another VIKTOR app

The LCA app is deployed independently. The producing app sends BHoM JSON to the LCA entity and calls the `run_analysis` button method through the VIKTOR SDK API.

## Complete caller module

Copy `templates/calling_app_client.py` into the producing app. Store the access token as a secret and read the workspace and entity IDs from configuration.

```python
from __future__ import annotations

import os
from pathlib import Path

from calling_app_client import LcaServiceLocation, call_lca_service


def run_sample() -> object:
    source = Path(__file__).resolve().parent / "samples"
    takeoff_json = (source / "takeoff.bhom.json").read_text(encoding="utf-8")
    template_json = (source / "template-materials.bhom.json").read_text(
        encoding="utf-8"
    )

    location = LcaServiceLocation(
        token=os.environ["VIKTOR_LCA_TOKEN"],
        workspace_id=int(os.environ["VIKTOR_LCA_WORKSPACE_ID"]),
        entity_id=int(os.environ["VIKTOR_LCA_ENTITY_ID"]),
    )
    return call_lca_service(
        location=location,
        project_id="revit-model-2025",
        project_name="Revit model 2025",
        gross_floor_area_m2=500.0,
        takeoff_json=takeoff_json,
        template_materials_json=template_json,
    )
```

The computation response is the serialized result of the VIKTOR button method. The initial method returns `analysis-result.json` as a `DownloadResult`. Confirm the exact response shape in the deployed VIKTOR environment before writing the producer-side download adapter.

## Data-size rule

Inline JSON is suitable for the sample and for small takeoffs. For large Revit datasets, persist the input files in VIKTOR and pass a file or entity reference in a later contract revision. Do not increase inline payload size without a measured platform test.

## Development limitation

Remote entity computation is intended for a deployed entity. A development app cannot call an entity in its own development workspace. Test the caller against a separately deployed LCA workspace.

## Authentication

- Keep the token outside source control.
- Grant the token access only to the required LCA workspace.
- Rotate the token according to the organization policy.
- Never send the token to the Generic Worker.
