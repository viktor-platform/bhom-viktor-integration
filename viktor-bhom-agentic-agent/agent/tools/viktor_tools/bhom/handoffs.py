"""Propagate verified BHoM outputs through the Revit-to-LCA workflow."""

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


def _validate_templates(value: Any) -> str:
    text = _json_text(value, field_name="template_materials_json")
    payload = json.loads(text)
    if not isinstance(payload, list) or not payload:
        raise ValueError(
            "template_materials_json must contain a non-empty Material array."
        )
    if any(
        not isinstance(item, dict) or item.get("_t") != MATERIAL_TYPE
        for item in payload
    ):
        raise ValueError("Every approved template must be a BHoM Material.")
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
            "gross_floor_area_m2": float(gross_floor_area_m2),
        }
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
        takeoff_json = _takeoff_from_source(payload.takeoff_json, source)
        template_materials_json = _validate_templates(template_value)
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
