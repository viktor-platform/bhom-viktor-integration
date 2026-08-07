import json
import uuid
from copy import deepcopy
from typing import Any

import viktor as vkt
from viktor.external.generic import GenericAnalysis

TAKEOFF_TYPE = "BH.oM.Physical.Materials.GeneralMaterialTakeoff"
MATERIAL_TYPE = "BH.oM.Physical.Materials.Material"


def _read_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8")
    getter = getattr(value, "getvalue", None)
    if callable(getter):
        value = getter()
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)
    raise RuntimeError("Worker output could not be read as UTF-8 text.")


def _run_worker(
    executable_key: str,
    files: list[tuple[str, str]],
    output_filenames: list[str],
    timeout_seconds: int,
) -> dict[str, str]:
    analysis = GenericAnalysis(
        files=[
            (name, vkt.File.from_data(text.encode("utf-8"))) for name, text in files
        ],
        executable_key=executable_key,
        output_filenames=output_filenames,
    )
    analysis.execute(timeout=timeout_seconds)
    outputs = {
        name: _read_text(analysis.get_output_file(name)) for name in output_filenames
    }
    for name, text in outputs.items():
        try:
            json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"Worker output '{name}' is not valid JSON: {error.msg}"
            ) from error
    return outputs


def build_revit_request(categories: list[str], element_limit: int) -> dict[str, Any]:
    allowed = {"Walls", "Floors", "Structural Columns", "Structural Framing", "Roofs"}
    selected = sorted(set(categories))
    if not selected or set(selected) - allowed:
        raise ValueError("Choose one or more supported Revit categories.")
    if not 1 <= element_limit <= 10_000:
        raise ValueError("element_limit must be between 1 and 10,000.")
    return {
        "schema_version": "1.0",
        "job_id": str(uuid.uuid4()),
        "operation": "pull_model_snapshot",
        "revit_version": "2025",
        "expected_document_name": None,
        "filters": {"categories": selected},
        "options": {
            "include_parameters": True,
            "include_material_takeoff": True,
            "include_geometry": False,
            "element_limit": element_limit,
        },
    }


def validate_takeoff(takeoff: Any) -> dict[str, Any]:
    if not isinstance(takeoff, dict) or takeoff.get("_t") != TAKEOFF_TYPE:
        raise ValueError("The Revit result must contain a BHoM GeneralMaterialTakeoff.")
    items = takeoff.get("MaterialTakeoffItems")
    if not isinstance(items, list) or not items:
        raise ValueError("The Revit takeoff has no material items.")
    return takeoff


def pull_revit_takeoff(categories: list[str], element_limit: int) -> dict[str, Any]:
    request = build_revit_request(categories, element_limit)
    outputs = _run_worker(
        "bhom_revit",
        [("revit-pull-request.json", json.dumps(request))],
        ["revit-metadata.json", "revit-elements.bhom.json", "takeoff.bhom.json"],
        300,
    )
    return validate_takeoff(json.loads(outputs["takeoff.bhom.json"]))


def inventory_from_takeoff(takeoff: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in validate_takeoff(takeoff)["MaterialTakeoffItems"]:
        material = item.get("Material") or {}
        name = str(material.get("Name") or "").strip()
        if not name:
            raise ValueError("Every takeoff item must have a material name.")
        row = grouped.setdefault(
            name.casefold(),
            {
                "material_name": name,
                "volume_m3": 0.0,
                "mass_kg": 0.0,
                "density_kg_m3": material.get("Density"),
            },
        )
        row["volume_m3"] += float(item.get("Volume") or 0)
        row["mass_kg"] += float(item.get("Mass") or 0)
    return list(grouped.values())


def search_material_database(takeoff: dict[str, Any]) -> dict[str, Any]:
    searches = [
        {
            "source_material": row["material_name"],
            "query": row["material_name"],
            "count": 8,
        }
        for row in inventory_from_takeoff(takeoff)
    ]
    request = {
        "schema_version": "1.0",
        "job_id": str(uuid.uuid4()),
        "dataset_scope": "All installed LCA datasets",
        "searches": searches,
    }
    outputs = _run_worker(
        "bhom_material_lookup",
        [("lookup-request.json", json.dumps(request))],
        ["lookup-result.json", "lookup-events.json", "runtime-manifest.json"],
        180,
    )
    lookup = json.loads(outputs["lookup-result.json"])
    if lookup.get("status") != "completed":
        raise RuntimeError("The BHoM material lookup did not complete.")
    return lookup


def candidate_summary(lookup: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "material": search.get("source_material"),
            "candidates": [
                {
                    key: candidate.get(key)
                    for key in (
                        "catalog_id",
                        "name",
                        "dataset_name",
                        "a1toa3_kgco2e_per_declared_unit",
                        "density_kg_m3",
                    )
                }
                for candidate in search.get("candidates", [])[:5]
            ],
        }
        for search in lookup.get("searches", [])
    ]


def build_templates(
    takeoff: dict[str, Any], lookup: dict[str, Any], mappings: dict[str, str]
) -> list[dict[str, Any]]:
    records = {
        str(candidate.get("catalog_id")): candidate
        for search in lookup.get("searches", [])
        for candidate in search.get("candidates", [])
    }
    templates = []
    for row in inventory_from_takeoff(takeoff):
        material_name = row["material_name"]
        catalog_id = mappings.get(material_name)
        if not catalog_id:
            raise ValueError(f"'{material_name}' requires an approved catalog_id.")
        record = records.get(catalog_id)
        if not record or not isinstance(record.get("epd"), dict):
            raise ValueError(
                f"'{catalog_id}' is not an available EPD candidate for '{material_name}'."
            )
        density = row.get("density_kg_m3") or record.get("density_kg_m3")
        if not density or float(density) <= 0:
            raise ValueError(f"'{material_name}' has no usable density.")
        templates.append(
            {
                "_t": MATERIAL_TYPE,
                "Name": material_name,
                "Density": float(density),
                "Properties": [deepcopy(record["epd"])],
            }
        )
    return templates


def run_lca(
    takeoff: dict[str, Any],
    templates: list[dict[str, Any]],
    project_name: str,
    gross_floor_area_m2: float,
    modules: list[str],
) -> dict[str, Any]:
    if not project_name.strip() or gross_floor_area_m2 <= 0:
        raise ValueError(
            "A project name and positive gross_floor_area_m2 are required."
        )
    request = {
        "schema_version": "1.0",
        "job_id": str(uuid.uuid4()),
        "analysis_profile": "general_environmental_results",
        "takeoff_filename": "takeoff.bhom.json",
        "template_materials_filename": "template-materials.bhom.json",
        "prioritise_template_materials": True,
        "metric_filters": ["ClimateChangeTotal"],
        "modules": modules,
        "project": {
            "project_id": project_name,
            "project_name": project_name,
            "gross_floor_area_m2": gross_floor_area_m2,
        },
    }
    outputs = _run_worker(
        "bhom_lca",
        [
            ("analysis-request.json", json.dumps(request)),
            ("takeoff.bhom.json", json.dumps(takeoff)),
            ("template-materials.bhom.json", json.dumps(templates)),
        ],
        [
            "analysis-result.json",
            "bhom-results.json",
            "analysis-events.json",
            "runtime-manifest.json",
        ],
        600,
    )
    return json.loads(outputs["analysis-result.json"])
