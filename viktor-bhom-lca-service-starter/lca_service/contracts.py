from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

CONTRACT_DIRECTORY = Path(__file__).resolve().parents[1] / "contracts"
TAKEOFF_TYPE = "BH.oM.Physical.Materials.GeneralMaterialTakeoff"
MATERIAL_TYPE = "BH.oM.Physical.Materials.Material"
ALLOWED_METRICS = frozenset({"ClimateChangeTotal"})
ALLOWED_MODULES = frozenset({"A1", "A2", "A3", "A1toA3"})
COMPONENT_MODULES = frozenset({"A1", "A2", "A3"})


class ContractError(ValueError):
    """Raised when service or BHoM input does not meet the service contract."""


@dataclass(frozen=True)
class Project:
    project_id: str
    project_name: str
    gross_floor_area_m2: float | None


@dataclass(frozen=True)
class AnalysisRequest:
    schema_version: str
    job_id: str
    analysis_profile: str
    takeoff_filename: str
    template_materials_filename: str
    prioritise_template_materials: bool
    metric_filters: tuple[str, ...]
    modules: tuple[str, ...]
    project: Project

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["metric_filters"] = list(self.metric_filters)
        value["modules"] = list(self.modules)
        return value

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


def parse_json(text: str, *, label: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ContractError(
            f"{label} is not valid JSON at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error


def validate_with_service_schema(instance: Any, schema_filename: str) -> None:
    schema_path = CONTRACT_DIRECTORY / schema_filename
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    if not errors:
        return

    messages = []
    for error in errors:
        path = "$"
        for part in error.absolute_path:
            path += f"[{part}]" if isinstance(part, int) else f".{part}"
        messages.append(f"{path}: {error.message}")
    raise ContractError(f"{schema_filename} validation failed:\n" + "\n".join(messages))


def validate_module_selection(modules: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(module) for module in modules))
    if not normalized:
        raise ContractError("Select at least one life-cycle module.")

    unsupported = sorted(set(normalized) - ALLOWED_MODULES)
    if unsupported:
        raise ContractError("Unsupported modules: " + ", ".join(unsupported))

    if "A1toA3" in normalized and set(normalized) & COMPONENT_MODULES:
        raise ContractError(
            "A1toA3 cannot be selected with A1, A2 or A3 because the total "
            "would count the same stages twice."
        )
    return normalized


def validate_metric_selection(metrics: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(metric) for metric in metrics))
    if not normalized:
        raise ContractError("Select at least one environmental metric.")

    unsupported = sorted(set(normalized) - ALLOWED_METRICS)
    if unsupported:
        raise ContractError(
            "Unsupported metrics in the initial service: " + ", ".join(unsupported)
        )
    return normalized


def validate_bhom_takeoff(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("The BHoM takeoff must be a JSON object.")
    if value.get("_t") != TAKEOFF_TYPE:
        raise ContractError(f"The takeoff _t must be '{TAKEOFF_TYPE}'.")
    items = value.get("MaterialTakeoffItems")
    if not isinstance(items, list) or not items:
        raise ContractError("MaterialTakeoffItems must be a nonempty JSON array.")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ContractError(f"MaterialTakeoffItems[{index}] must be an object.")
        material = item.get("Material")
        if not isinstance(material, dict):
            raise ContractError(
                f"MaterialTakeoffItems[{index}].Material must be an object."
            )
        if material.get("_t") != MATERIAL_TYPE:
            raise ContractError(
                f"MaterialTakeoffItems[{index}].Material._t must be '{MATERIAL_TYPE}'."
            )
    return value


def validate_bhom_templates(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ContractError("Template materials must be a nonempty JSON array.")
    for index, material in enumerate(value):
        if not isinstance(material, dict):
            raise ContractError(f"Template materials[{index}] must be an object.")
        if material.get("_t") != MATERIAL_TYPE:
            raise ContractError(
                f"Template materials[{index}]._t must be '{MATERIAL_TYPE}'."
            )
    return value


def stable_job_id(
    *,
    takeoff_json: str,
    template_materials_json: str,
    modules: tuple[str, ...],
    metrics: tuple[str, ...],
    project_id: str,
    project_name: str,
    gross_floor_area_m2: float | None,
    prioritise_template_materials: bool,
    analysis_profile: str,
) -> str:
    payload = {
        "analysis_profile": analysis_profile,
        "gross_floor_area_m2": gross_floor_area_m2,
        "metrics": list(metrics),
        "modules": list(modules),
        "prioritise_template_materials": prioritise_template_materials,
        "project_id": project_id,
        "project_name": project_name,
        "takeoff": takeoff_json,
        "template_materials": template_materials_json,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, digest))


def build_request(
    *,
    takeoff_json: str,
    template_materials_json: str,
    project_id: str,
    project_name: str,
    gross_floor_area_m2: float | None,
    modules: list[str] | tuple[str, ...],
    prioritise_template_materials: bool,
) -> AnalysisRequest:
    takeoff = validate_bhom_takeoff(parse_json(takeoff_json, label="takeoff JSON"))
    templates = validate_bhom_templates(
        parse_json(template_materials_json, label="template-material JSON")
    )

    normalized_takeoff = json.dumps(takeoff, separators=(",", ":"), sort_keys=True)
    normalized_templates = json.dumps(templates, separators=(",", ":"), sort_keys=True)
    normalized_modules = validate_module_selection(modules)
    metrics = validate_metric_selection(["ClimateChangeTotal"])

    area = None
    if gross_floor_area_m2 is not None:
        area = float(gross_floor_area_m2)
        if area < 0:
            raise ContractError("Gross floor area cannot be negative.")
        if area == 0:
            area = None

    clean_project_name = (project_name or "").strip()
    if not clean_project_name:
        raise ContractError("Project name is required.")

    clean_project_id = (project_id or clean_project_name).strip()
    if not clean_project_id:
        raise ContractError("Project ID is required.")

    analysis_profile = "general_environmental_results"
    prioritise_templates = bool(prioritise_template_materials)
    request = AnalysisRequest(
        schema_version="1.0",
        job_id=stable_job_id(
            takeoff_json=normalized_takeoff,
            template_materials_json=normalized_templates,
            modules=normalized_modules,
            metrics=metrics,
            project_id=clean_project_id,
            project_name=clean_project_name,
            gross_floor_area_m2=area,
            prioritise_template_materials=prioritise_templates,
            analysis_profile=analysis_profile,
        ),
        analysis_profile=analysis_profile,
        takeoff_filename="takeoff.bhom.json",
        template_materials_filename="template-materials.bhom.json",
        prioritise_template_materials=prioritise_templates,
        metric_filters=metrics,
        modules=normalized_modules,
        project=Project(
            project_id=clean_project_id,
            project_name=clean_project_name,
            gross_floor_area_m2=area,
        ),
    )
    validate_with_service_schema(request.to_dict(), "service-request.schema.json")
    return request


def validate_normalized_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("The normalized result must be a JSON object.")
    validate_with_service_schema(value, "normalized-result.schema.json")
    return value
