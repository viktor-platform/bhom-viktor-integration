from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .contracts import ContractError, GatewayResult, parse_json, validate_modules

BHOM_SCHEMA_COMMIT = "9a3bde86d287cb9e07f40b5538a059cc546c59dc"


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


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        wrapped = value.get("_v")
        if isinstance(wrapped, list):
            return wrapped
    return []


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def material_density(material: dict[str, Any]) -> tuple[float | None, str]:
    """Resolve density using the same information available in the BHoM payload."""
    direct_density = _positive_float(material.get("Density"))
    if direct_density is not None:
        return direct_density, "BHoM Material.Density"

    fallback: tuple[float, str] | None = None
    for prop in _sequence(material.get("Properties")):
        if not isinstance(prop, dict):
            continue
        density = _positive_float(prop.get("Density"))
        if density is None:
            continue
        fragment_type = str(prop.get("_t", "")).rsplit(".", maxsplit=1)[-1]
        candidate = (density, f"{fragment_type}.Density")
        if fragment_type == "SolidMaterial":
            return candidate
        fallback = fallback or candidate

    return fallback or (None, "Unavailable")


def summarize_material_inputs(
    result: GatewayResult,
    template_materials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate takeoff items into the material inputs required by LCA."""
    template_names = {
        str(material.get("Name", "")).strip().casefold()
        for material in template_materials
        if str(material.get("Name", "")).strip()
    }
    grouped: dict[str, dict[str, Any]] = {}

    for item in result.takeoff["MaterialTakeoffItems"]:
        material = item.get("Material")
        if not isinstance(material, dict):
            continue
        name = str(material.get("Name") or "Unnamed material").strip()
        key = name.casefold()
        row = grouped.setdefault(
            key,
            {
                "name": name,
                "volume_m3": 0.0,
                "reported_mass_kg": 0.0,
                "calculated_mass_kg": 0.0,
                "number_items": 0,
                "density_mass_kg": 0.0,
                "density_volume_m3": 0.0,
                "density_sources": set(),
                "template_match": key in template_names,
            },
        )

        volume = float(item.get("Volume", 0.0) or 0.0)
        reported_mass = float(item.get("Mass", 0.0) or 0.0)
        density, density_source = material_density(material)
        calculated_mass = reported_mass
        if calculated_mass <= 0 and density is not None:
            calculated_mass = volume * density

        row["volume_m3"] += volume
        row["reported_mass_kg"] += reported_mass
        row["calculated_mass_kg"] += calculated_mass
        row["number_items"] += int(item.get("NumberItem", 0) or 0)
        if density is not None:
            row["density_mass_kg"] += volume * density
            row["density_volume_m3"] += volume
            row["density_sources"].add(density_source)

    rows: list[dict[str, Any]] = []
    for row in grouped.values():
        density_volume = float(row.pop("density_volume_m3"))
        density_mass = float(row.pop("density_mass_kg"))
        sources = sorted(row.pop("density_sources"))
        row["density_kg_m3"] = (
            density_mass / density_volume if density_volume > 0 else None
        )
        row["density_source"] = ", ".join(sources) if sources else "Unavailable"
        row["density_complete"] = density_volume >= float(row["volume_m3"])
        rows.append(row)

    return sorted(rows, key=lambda row: str(row["name"]).casefold())


def summarize_bhom_contract(result: GatewayResult) -> dict[str, Any]:
    """Summarize the element-to-material contract exposed by the gateway."""
    metadata_elements = result.metadata["elements"]
    takeoff_items = result.takeoff["MaterialTakeoffItems"]
    element_types = sorted(
        {str(item.get("bhom_type", "Unknown")) for item in metadata_elements}
    )
    mapped_elements = sum(
        bool(item.get("revit_element_id")) and bool(item.get("bhom_guid"))
        for item in metadata_elements
    )
    material_links = sum(len(item.get("materials", [])) for item in metadata_elements)

    return {
        "schema_version": str(result.metadata["schema_version"]),
        "schema_commit": BHOM_SCHEMA_COMMIT,
        "element_contract": "BH.oM.Base.IBHoMObject[]",
        "material_fragment_contract": (
            "BH.oM.Physical.Materials.VolumetricMaterialTakeoff"
        ),
        "takeoff_contract": str(result.takeoff["_t"]),
        "element_count": len(metadata_elements),
        "mapped_element_count": mapped_elements,
        "element_types": element_types,
        "material_link_count": material_links,
        "takeoff_item_count": len(takeoff_items),
        "valid": (
            mapped_elements == len(metadata_elements)
            and result.takeoff["_t"]
            == "BH.oM.Physical.Materials.GeneralMaterialTakeoff"
        ),
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
