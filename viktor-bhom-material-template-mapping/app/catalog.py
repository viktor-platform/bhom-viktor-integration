from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .contracts import MATERIAL_TYPE, ContractError

LOOKUP_SCHEMA_VERSION = "1.0"
DEFAULT_SOURCE = {
    "dataset": "All installed LCA datasets",
    "toolkit": "BHoM Library_Engine",
    "library_path": "LifeCycleAssessment",
    "dataset_count": 0,
    "epd_count": 0,
}


def parse_lookup_results(text: str | None) -> dict[str, Any]:
    try:
        value = json.loads(text or "{}")
    except json.JSONDecodeError as error:
        raise ContractError(
            f"BHoM lookup result is invalid JSON: {error.msg}"
        ) from error
    if not isinstance(value, dict):
        raise ContractError("BHoM lookup result must be a JSON object.")
    if not value:
        return {
            "schema_version": LOOKUP_SCHEMA_VERSION,
            "status": "not_searched",
            "source": dict(DEFAULT_SOURCE),
            "searches": [],
        }
    if value.get("schema_version") != LOOKUP_SCHEMA_VERSION:
        raise ContractError("BHoM lookup result must use schema_version 1.0.")
    searches = value.get("searches")
    if not isinstance(searches, list):
        raise ContractError("BHoM lookup result searches must be an array.")

    normalized = deepcopy(value)
    for search in normalized["searches"]:
        if not isinstance(search, dict) or not isinstance(
            search.get("candidates"), list
        ):
            raise ContractError("Every BHoM lookup search requires a candidates array.")
        for candidate in search["candidates"]:
            epd_json = candidate.pop("epd_json", None)
            if epd_json is not None:
                try:
                    candidate["epd"] = json.loads(epd_json)
                except json.JSONDecodeError as error:
                    candidate_id = candidate.get("catalog_id", "")
                    raise ContractError(
                        f"Candidate '{candidate_id}' has invalid EPD JSON."
                    ) from error
            if not isinstance(candidate.get("epd"), dict):
                raise ContractError("Every BHoM lookup candidate requires a typed EPD.")
    return normalized


def catalogue_source(lookup: dict[str, Any] | None = None) -> dict[str, Any]:
    if lookup and isinstance(lookup.get("source"), dict):
        return dict(lookup["source"])
    return dict(DEFAULT_SOURCE)


def catalog_records(lookup: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        candidate
        for search in lookup.get("searches", [])
        for candidate in search.get("candidates", [])
    ]


def candidates_for_material(
    lookup: dict[str, Any], material_name: str
) -> list[dict[str, Any]]:
    for search in lookup.get("searches", []):
        if str(search.get("source_material", "")) == material_name:
            return list(search.get("candidates", []))
    return []


def record_by_id(lookup: dict[str, Any], catalog_id: str) -> dict[str, Any] | None:
    return next(
        (
            record
            for record in catalog_records(lookup)
            if str(record.get("catalog_id", "")) == catalog_id
        ),
        None,
    )


def climate_change_a1toa3(record: dict[str, Any]) -> float | None:
    direct = record.get("a1toa3_kgco2e_per_declared_unit")
    if direct is not None:
        return float(direct)
    metrics = record.get("epd", {}).get("EnvironmentalMetrics", [])
    for metric in metrics:
        if str(metric.get("_t", "")).endswith(".ClimateChangeTotalMetric"):
            value = metric.get("A1toA3")
            if value is None and isinstance(metric.get("Indicators"), dict):
                value = metric["Indicators"].get("A1toA3")
            return float(value) if value is not None else None
    return None


def build_template_materials(
    inventory: list[dict[str, Any]],
    mappings: dict[str, str],
    lookup: dict[str, Any],
) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for row in inventory:
        material_name = str(row["material_name"])
        catalog_id = mappings.get(material_name)
        if not catalog_id:
            continue
        record = record_by_id(lookup, catalog_id)
        if record is None:
            raise ContractError(
                f"The mapping for '{material_name}' references a result that is "
                "not present. Search the installed BHoM datasets again."
            )

        density = row.get("density_kg_m3") or record.get("density_kg_m3")
        if not density or float(density) <= 0:
            raise ContractError(f"'{material_name}' has no usable material density.")

        templates.append(
            {
                "_t": MATERIAL_TYPE,
                "Name": material_name,
                "Density": float(density),
                "Properties": [deepcopy(record["epd"])],
            }
        )
    return templates


def template_json(
    inventory: list[dict[str, Any]],
    mappings: dict[str, str],
    lookup: dict[str, Any],
) -> str:
    return json.dumps(
        build_template_materials(inventory, mappings, lookup),
        indent=2,
        ensure_ascii=False,
    )
