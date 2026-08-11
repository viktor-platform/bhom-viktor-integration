import json
from typing import Any

from agents.tool_context import ToolContext
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.tools.viktor_tools.bhom.common import (
    MATERIAL_TEMPLATE_MAPPING_STORAGE_KEY,
    REVIT_CONNECTOR_STORAGE_KEY,
    deep_merge,
    try_read_json_from_storage,
)
from agent.tools.viktor_tools.tool_feedback import (
    execution_error_response,
    needs_prerequisite_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.workflow.entity_ops import (
    WorkflowEntityService,
    WorkflowNodeId,
    WorkflowRunEntity,
    get_workflow_entity_service,
    needs_workflow_run_response,
)
from agent.types import AgentContext

TAKEOFF_TYPE = "BH.oM.Physical.Materials.GeneralMaterialTakeoff"
MATERIAL_TYPE = "BH.oM.Physical.Materials.Material"
DEFAULT_MODULES = ["A1", "A2", "A3"]


class HandoffRevitToMappingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    takeoff_json: str | None = Field(
        default=None,
        description="Optional explicit GeneralMaterialTakeoff JSON. Stored Revit output is used when omitted.",
    )
    gross_floor_area_m2: float | None = Field(default=None, gt=0)


class HandoffMappingToLcaArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    takeoff_json: str | None = None
    template_materials_json: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    gross_floor_area_m2: float | None = Field(default=None, gt=0)
    modules: list[str] = Field(default_factory=lambda: list(DEFAULT_MODULES))


def _json_text(value: Any, *, field_name: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{field_name} cannot be empty.")
        json.loads(text)
        return text
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    raise ValueError(f"{field_name} must be a JSON string, object, or array.")


def _validate_takeoff(value: Any) -> str:
    text = _json_text(value, field_name="takeoff_json")
    payload = json.loads(text)
    if not isinstance(payload, dict) or payload.get("_t") != TAKEOFF_TYPE:
        raise ValueError("takeoff_json must contain a BHoM GeneralMaterialTakeoff.")
    items = payload.get("MaterialTakeoffItems")
    if not isinstance(items, list) or not items:
        raise ValueError("The BHoM takeoff contains no material items.")
    return text


def _validate_templates(value: Any, *, expected_count: int | None = None) -> str:
    text = _json_text(value, field_name="template_materials_json")
    payload = json.loads(text)
    if not isinstance(payload, list) or not payload:
        raise ValueError(
            "template_materials_json must contain a non-empty Material array."
        )
    for item in payload:
        if not isinstance(item, dict) or item.get("_t") != MATERIAL_TYPE:
            raise ValueError("Every approved template must be a BHoM Material.")
        if not str(item.get("Name") or "").strip():
            raise ValueError("Every approved BHoM Material must have a Name.")
        properties = item.get("Properties")
        if not isinstance(properties, list) or not properties:
            raise ValueError(
                "Every approved BHoM Material must contain a selected EPD in Properties."
            )
    if expected_count is not None and len(payload) != expected_count:
        raise ValueError(
            "The approved BHoM Material count must match the material inventory."
        )
    return text


def _value(source: Any, key: str) -> Any:
    return source.get(key) if isinstance(source, dict) else None


def _takeoff_from_source(explicit: str | None, source: Any) -> str:
    candidate = explicit or _value(source, "takeoff_json")
    if (
        candidate is None
        and isinstance(source, dict)
        and source.get("_t") == TAKEOFF_TYPE
    ):
        candidate = source
    return _validate_takeoff(candidate)


def _positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _material_density(material: dict[str, Any]) -> float | None:
    direct = _positive_number(material.get("Density"))
    if direct is not None:
        return direct
    fallback = None
    properties = material.get("Properties")
    if not isinstance(properties, list):
        return None
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        density = _positive_number(prop.get("Density"))
        if density is None:
            continue
        if str(prop.get("_t", "")).endswith(".SolidMaterial"):
            return density
        fallback = fallback or density
    return fallback


def _material_inventory(takeoff_json: str) -> list[dict[str, Any]]:
    takeoff = json.loads(takeoff_json)
    grouped: dict[str, dict[str, Any]] = {}
    for item in takeoff["MaterialTakeoffItems"]:
        material = item["Material"]
        name = str(material.get("Name") or "").strip()
        if not name:
            raise ValueError("Every Revit takeoff material must have a name.")
        volume = float(item.get("Volume") or 0)
        density = _material_density(material)
        row = grouped.setdefault(
            name.casefold(),
            {
                "material_name": name,
                "search_query": name,
                "volume_m3": 0.0,
                "density_mass_kg": 0.0,
                "density_volume_m3": 0.0,
            },
        )
        row["volume_m3"] += volume
        if density is not None:
            row["density_mass_kg"] += density * volume
            row["density_volume_m3"] += volume

    inventory = []
    for row in grouped.values():
        density_volume = float(row.pop("density_volume_m3"))
        density_mass = float(row.pop("density_mass_kg"))
        row["density_kg_m3"] = (
            density_mass / density_volume if density_volume > 0 else None
        )
        inventory.append(row)
    return sorted(inventory, key=lambda row: str(row["material_name"]).casefold())


def _set_and_verify(
    service: WorkflowEntityService,
    node_id: WorkflowNodeId,
    patch: dict[str, Any],
    *,
    message: str,
) -> WorkflowRunEntity:
    target = service.resolve_entity(node_id)
    current = service.read_last_saved_params(target)
    next_params = deep_merge(current, patch)
    service.set_last_saved_params(target, next_params, message=message)
    verified = service.read_last_saved_params(target)
    for key, expected in patch.items():
        if verified.get(key) != expected:
            raise RuntimeError(f"Saved params readback failed for '{node_id}.{key}'.")
    return target


def _completed_handoff(
    *, source: WorkflowNodeId, target: WorkflowRunEntity, fields: list[str]
) -> str:
    return tool_response(
        "completed",
        source=source,
        target=target.node_id,
        target_entity_id=target.entity_id,
        target_url=target.url,
        updated_fields=fields,
        readback_verified=True,
    )


async def handoff_revit_connector_to_material_template_mapping_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    try:
        payload = HandoffRevitToMappingArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="handoff_revit_connector_to_material_template_mapping",
            message="Invalid Revit-to-mapping handoff arguments.",
            error=exc,
            retry_tool="handoff_revit_connector_to_material_template_mapping",
        )

    source = try_read_json_from_storage(REVIT_CONNECTOR_STORAGE_KEY)
    if source is None and payload.takeoff_json is None:
        return needs_prerequisite_response(
            tool="handoff_revit_connector_to_material_template_mapping",
            message="No Revit material takeoff is stored for this workflow run.",
            missing_storage_key=REVIT_CONNECTOR_STORAGE_KEY,
            retry_tool="run_revit_connector",
            retry_reason="Run the Revit connector result tool, or provide takeoff_json explicitly.",
        )

    try:
        takeoff_json = _takeoff_from_source(payload.takeoff_json, source)
        patch: dict[str, Any] = {
            "material_inventory": _material_inventory(takeoff_json),
            "lookup_results_json": "",
            "mapping_state_json": '{"schema_version":"1.0","mappings":{}}',
            "template_materials_json": "[]",
        }
        if payload.gross_floor_area_m2 is not None:
            patch["gross_floor_area_m2"] = payload.gross_floor_area_m2
        target = _set_and_verify(
            get_workflow_entity_service(),
            "material_template_mapping",
            patch,
            message="Agent handed the Revit material takeoff to material mapping.",
        )
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="handoff_revit_connector_to_material_template_mapping",
            node_id="material_template_mapping",
        )
    except ValueError as exc:
        return validation_error_response(
            tool="handoff_revit_connector_to_material_template_mapping",
            message="The stored Revit handoff is not valid.",
            error=exc,
            retry_tool="run_revit_connector",
        )
    except (RuntimeError, TypeError, AttributeError) as exc:
        return execution_error_response(
            tool="handoff_revit_connector_to_material_template_mapping",
            message="Could not update or verify material-mapping params.",
            error=exc,
        )

    return _completed_handoff(
        source="revit_connector", target=target, fields=sorted(patch)
    )


async def handoff_material_template_mapping_to_lca_analysis_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    try:
        payload = HandoffMappingToLcaArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="handoff_material_template_mapping_to_lca_analysis",
            message="Invalid mapping-to-LCA handoff arguments.",
            error=exc,
            retry_tool="handoff_material_template_mapping_to_lca_analysis",
        )

    stored = try_read_json_from_storage(MATERIAL_TEMPLATE_MAPPING_STORAGE_KEY)
    stored_takeoff = try_read_json_from_storage(REVIT_CONNECTOR_STORAGE_KEY)
    try:
        service = get_workflow_entity_service()
        mapping = service.resolve_entity("material_template_mapping")
        saved_mapping_params = service.read_last_saved_params(mapping)
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="handoff_material_template_mapping_to_lca_analysis",
            node_id="material_template_mapping",
        )
    except (RuntimeError, TypeError, AttributeError) as exc:
        return execution_error_response(
            tool="handoff_material_template_mapping_to_lca_analysis",
            message="Could not read the material-mapping node params.",
            error=exc,
        )

    source = (
        deep_merge(saved_mapping_params, stored)
        if isinstance(stored, dict)
        else saved_mapping_params
    )
    template_value = payload.template_materials_json or _value(
        source, "template_materials_json"
    )
    if stored is None and not template_value:
        return needs_prerequisite_response(
            tool="handoff_material_template_mapping_to_lca_analysis",
            message="No approved material template is saved or stored.",
            missing_storage_key=MATERIAL_TEMPLATE_MAPPING_STORAGE_KEY,
            retry_tool="run_material_template_mapping",
            retry_reason="Open the mapping app, approve and save the material mappings, then tell the agent to read the node again.",
        )
    if isinstance(stored, dict) and stored.get("approved") is False:
        return tool_response(
            "needs_user_input",
            tool="handoff_material_template_mapping_to_lca_analysis",
            message="Open the material-mapping app, approve and save every material-to-EPD selection, then tell the agent it is ready.",
            node_id="material_template_mapping",
            url=mapping.url,
        )

    try:
        takeoff_json = _takeoff_from_source(
            payload.takeoff_json,
            stored_takeoff if stored_takeoff is not None else source,
        )
        inventory = _value(source, "material_inventory")
        expected_template_count = (
            len(inventory) if isinstance(inventory, list) else None
        )
        template_materials_json = _validate_templates(
            template_value,
            expected_count=expected_template_count,
        )
        project_name = (
            payload.project_name or _value(source, "project_name") or "BHoM LCA Project"
        ).strip()
        project_id = (
            payload.project_id or _value(source, "project_id") or project_name
        ).strip()
        gross_floor_area_m2 = payload.gross_floor_area_m2 or _value(
            source, "gross_floor_area_m2"
        )
        if (
            not isinstance(gross_floor_area_m2, (int, float))
            or gross_floor_area_m2 <= 0
        ):
            raise ValueError(
                "gross_floor_area_m2 must be provided and greater than zero."
            )
        patch = {
            "takeoff_json": takeoff_json,
            "template_materials_json": template_materials_json,
            "project_id": project_id,
            "project_name": project_name,
            "gross_floor_area_m2": float(gross_floor_area_m2),
            "modules": payload.modules,
        }
        target = _set_and_verify(
            service,
            "lca_analysis",
            patch,
            message="Agent handed the approved material template to LCA analysis.",
        )
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="handoff_material_template_mapping_to_lca_analysis",
            node_id="lca_analysis",
        )
    except ValueError as exc:
        return validation_error_response(
            tool="handoff_material_template_mapping_to_lca_analysis",
            message="The approved material-mapping handoff is not valid.",
            error=exc,
            retry_tool="get_params_in_node",
        )
    except (RuntimeError, TypeError, AttributeError) as exc:
        return execution_error_response(
            tool="handoff_material_template_mapping_to_lca_analysis",
            message="Could not update or verify LCA params.",
            error=exc,
        )

    return _completed_handoff(
        source="material_template_mapping", target=target, fields=sorted(patch)
    )


handoff_revit_connector_to_material_template_mapping = (
    handoff_revit_connector_to_material_template_mapping_func
)
handoff_material_template_mapping_to_lca_analysis = (
    handoff_material_template_mapping_to_lca_analysis_func
)
