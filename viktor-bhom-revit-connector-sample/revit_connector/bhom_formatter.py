from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .contracts import ContractError, GatewayResult, parse_json, validate_modules


def summarize_snapshot(result: GatewayResult) -> dict[str, Any]:
    metadata_elements = result.metadata["elements"]
    categories = Counter(
        str(item.get("category", "Uncategorized")) for item in metadata_elements
    )
    types = Counter(str(item.get("bhom_type", "Unknown")) for item in metadata_elements)
    takeoff_items = result.takeoff["MaterialTakeoffItems"]
    materials = Counter(
        str(item.get("Material", {}).get("Name", "Unnamed material"))
        for item in takeoff_items
    )

    return {
        "element_count": len(metadata_elements),
        "category_count": len(categories),
        "material_count": len(materials),
        "parameter_count": sum(
            len(item.get("parameters", [])) for item in metadata_elements
        ),
        "total_mass_kg": sum(float(item.get("Mass", 0.0)) for item in takeoff_items),
        "total_volume_m3": sum(
            float(item.get("Volume", 0.0)) for item in takeoff_items
        ),
        "categories": dict(categories.most_common()),
        "bhom_types": dict(types.most_common()),
        "materials": dict(materials.most_common()),
    }


def validate_template_materials(text: str) -> list[dict[str, Any]]:
    value = parse_json(text.strip(), label="template-materials.bhom.json")
    if not isinstance(value, list) or not value:
        raise ContractError("Template materials must be a non-empty BHoM JSON array.")
    for index, material in enumerate(value):
        if not isinstance(material, dict):
            raise ContractError(f"Template material {index} must be a JSON object.")
        if material.get("_t") != "BH.oM.Physical.Materials.Material":
            raise ContractError(f"Template material {index} must be a BHoM Material.")
    return value


def build_lca_handoff(
    *,
    result: GatewayResult,
    project_id: str,
    project_name: str,
    gross_floor_area_m2: float,
    modules: list[str],
    template_materials_json: str,
) -> dict[str, Any]:
    clean_project_id = project_id.strip()
    clean_project_name = project_name.strip()
    if not clean_project_id:
        raise ContractError("Project ID is required for the LCA handoff.")
    if not clean_project_name:
        raise ContractError("Project name is required for the LCA handoff.")
    if gross_floor_area_m2 < 0:
        raise ContractError("Gross floor area cannot be negative.")

    clean_modules = validate_modules(modules)
    templates = validate_template_materials(template_materials_json)
    takeoff_json = json.dumps(result.takeoff, separators=(",", ":"), ensure_ascii=False)
    templates_json = json.dumps(templates, separators=(",", ":"), ensure_ascii=False)

    return {
        "schema_version": "1.0",
        "target": {
            "app": "bhom-lca-carbon-analysis",
            "method_name": "run_analysis",
        },
        "source": {
            "app": "bhom-revit-2025-connector-sample",
            "document": result.metadata["source"]["document_name"],
            "revit_version": result.metadata["source"]["revit_version"],
            "gateway_job_id": result.metadata["job_id"],
        },
        "params": {
            "project_id": clean_project_id,
            "project_name": clean_project_name,
            "gross_floor_area_m2": gross_floor_area_m2,
            "modules": clean_modules,
            "prioritise_template_materials": True,
            "takeoff_json": takeoff_json,
            "template_materials_json": templates_json,
            "chart_type": "Stacked bar",
            "group_by": "Material",
        },
    }
