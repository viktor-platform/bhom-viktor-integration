from __future__ import annotations

import json
from typing import Any, Final

TAKEOFF_TYPE: Final[str] = "BH.oM.Physical.Materials.GeneralMaterialTakeoff"
MATERIAL_TYPE: Final[str] = "BH.oM.Physical.Materials.Material"
MAPPING_SCHEMA_VERSION: Final[str] = "1.0"


class ContractError(ValueError):
    """Raised when a takeoff or mapping payload is invalid."""


def value_of(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def parse_json(text: str, *, label: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ContractError(
            f"{label} is not valid JSON at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error


def _number(value: Any, *, label: str, minimum: float = 0.0) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError) as error:
        raise ContractError(f"{label} must be a number.") from error
    if number < minimum:
        raise ContractError(f"{label} must be at least {minimum:g}.")
    return number


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("_v"), list):
        return value["_v"]
    return []


def material_density(material: dict[str, Any]) -> float | None:
    direct = _number(material.get("Density"), label="Material density")
    if direct > 0:
        return direct

    fallback: float | None = None
    for fragment in _sequence(material.get("Properties")):
        if not isinstance(fragment, dict):
            continue
        density = _number(fragment.get("Density"), label="Material fragment density")
        if density <= 0:
            continue
        if str(fragment.get("_t", "")).endswith(".SolidMaterial"):
            return density
        fallback = fallback or density
    return fallback


def validate_takeoff(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("_t") != TAKEOFF_TYPE:
        raise ContractError(f"The takeoff _t must be '{TAKEOFF_TYPE}'.")

    items = value.get("MaterialTakeoffItems")
    if not isinstance(items, list) or not items:
        raise ContractError("MaterialTakeoffItems must be a non-empty JSON array.")

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ContractError(f"MaterialTakeoffItems[{index}] must be an object.")
        material = item.get("Material")
        if not isinstance(material, dict) or material.get("_t") != MATERIAL_TYPE:
            raise ContractError(
                f"MaterialTakeoffItems[{index}].Material must be a BHoM Material."
            )
    return value


def inventory_from_takeoff(takeoff: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(takeoff["MaterialTakeoffItems"]):
        material = item["Material"]
        name = str(material.get("Name") or "").strip()
        if not name:
            raise ContractError(f"MaterialTakeoffItems[{index}] has no material name.")

        volume = _number(item.get("Volume"), label=f"{name} volume")
        reported_mass = _number(item.get("Mass"), label=f"{name} mass")
        density = material_density(material)
        mass = reported_mass if reported_mass > 0 else volume * (density or 0)

        key = name.casefold()
        row = grouped.setdefault(
            key,
            {
                "material_name": name,
                "volume_m3": 0.0,
                "density_mass_kg": 0.0,
                "density_volume_m3": 0.0,
                "mass_kg": 0.0,
            },
        )
        row["volume_m3"] += volume
        row["mass_kg"] += mass
        if density is not None:
            row["density_mass_kg"] += density * volume
            row["density_volume_m3"] += volume

    inventory: list[dict[str, Any]] = []
    for row in grouped.values():
        density_volume = float(row.pop("density_volume_m3"))
        density_mass = float(row.pop("density_mass_kg"))
        row["density_kg_m3"] = (
            density_mass / density_volume if density_volume > 0 else None
        )
        inventory.append(row)
    return sorted(inventory, key=lambda row: str(row["material_name"]).casefold())


def inventory_from_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ContractError("Add at least one material or upload a BHoM takeoff.")

    grouped: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(rows):
        name = str(value_of(source, "material_name", "") or "").strip()
        if not name:
            raise ContractError(f"Material row {index + 1} requires a name.")
        volume = _number(
            value_of(source, "volume_m3", 0),
            label=f"{name} volume",
        )
        density_value = _number(
            value_of(source, "density_kg_m3", 0),
            label=f"{name} density",
        )
        density = density_value if density_value > 0 else None

        key = name.casefold()
        row = grouped.setdefault(
            key,
            {
                "material_name": name,
                "volume_m3": 0.0,
                "mass_kg": 0.0,
                "density_mass_kg": 0.0,
                "density_volume_m3": 0.0,
            },
        )
        row["volume_m3"] += volume
        if density is not None:
            row["mass_kg"] += volume * density
            row["density_mass_kg"] += volume * density
            row["density_volume_m3"] += volume

    inventory: list[dict[str, Any]] = []
    for row in grouped.values():
        density_volume = float(row.pop("density_volume_m3"))
        density_mass = float(row.pop("density_mass_kg"))
        row["density_kg_m3"] = (
            density_mass / density_volume if density_volume > 0 else None
        )
        inventory.append(row)
    return sorted(inventory, key=lambda row: str(row["material_name"]).casefold())


def build_takeoff(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for row in inventory:
        material: dict[str, Any] = {
            "_t": MATERIAL_TYPE,
            "Name": row["material_name"],
            "Properties": [],
        }
        density = row.get("density_kg_m3")
        if density is not None:
            material["Density"] = density
        items.append(
            {
                "_t": "BH.oM.Physical.Materials.TakeoffItem",
                "Material": material,
                "Volume": row["volume_m3"],
                "Mass": row["mass_kg"],
                "Area": 0.0,
                "Length": 0.0,
                "NumberItem": 0,
            }
        )
    return {
        "_t": TAKEOFF_TYPE,
        "Name": "VIKTOR material inventory",
        "MaterialTakeoffItems": items,
    }


def parse_mapping_state(text: str | None) -> dict[str, str]:
    value = parse_json(text or "{}", label="mapping state")
    if not isinstance(value, dict):
        raise ContractError("Mapping state must be a JSON object.")
    version = str(value.get("schema_version", MAPPING_SCHEMA_VERSION))
    if version != MAPPING_SCHEMA_VERSION:
        raise ContractError("Mapping state must use schema_version 1.0.")
    mappings = value.get("mappings", {})
    if not isinstance(mappings, dict):
        raise ContractError("Mapping state mappings must be a JSON object.")
    return {
        str(material).strip(): str(catalog_id).strip()
        for material, catalog_id in mappings.items()
        if str(material).strip() and str(catalog_id).strip()
    }


def resolve_inputs(params: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_json = str(value_of(params, "takeoff_json", "") or "").strip()
    file_resource = value_of(params, "takeoff_file")
    if raw_json:
        takeoff = validate_takeoff(parse_json(raw_json, label="takeoff JSON"))
        return inventory_from_takeoff(takeoff), takeoff
    if file_resource is not None:
        with file_resource.file.open(encoding="utf-8") as stream:
            takeoff = validate_takeoff(parse_json(stream.read(), label="takeoff file"))
        return inventory_from_takeoff(takeoff), takeoff

    inventory = inventory_from_rows(value_of(params, "material_inventory", []))
    return inventory, build_takeoff(inventory)
