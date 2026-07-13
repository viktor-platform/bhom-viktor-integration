from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import viktor as vkt


@dataclass(frozen=True)
class LcaServiceLocation:
    token: str
    workspace_id: int
    entity_id: int


def call_lca_service(
    *,
    location: LcaServiceLocation,
    project_id: str,
    project_name: str,
    gross_floor_area_m2: float | None,
    takeoff_json: str,
    template_materials_json: str,
    modules: tuple[str, ...] = ("A1", "A2", "A3"),
    prioritise_template_materials: bool = True,
    timeout_seconds: int = 900,
) -> Any:
    """Run the deployed LCA entity from another VIKTOR application."""
    api = vkt.api_v1.API(token=location.token)
    entity = api.get_entity(
        location.entity_id,
        workspace_id=location.workspace_id,
    )
    return entity.compute(
        method_name="run_analysis",
        params={
            "project_id": project_id,
            "project_name": project_name,
            "gross_floor_area_m2": gross_floor_area_m2 or 0.0,
            "modules": list(modules),
            "prioritise_template_materials": prioritise_template_materials,
            "takeoff_json": takeoff_json,
            "template_materials_json": template_materials_json,
            "chart_type": "Stacked bar",
            "group_by": "Material",
        },
        timeout=timeout_seconds,
    )
