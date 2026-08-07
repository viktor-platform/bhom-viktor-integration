"""Run configured BHoM app methods and persist their selected outputs."""

import json
from typing import Any

import requests
from agents.tool_context import ToolContext
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from agent.tools.viktor_tools.bhom.common import deep_merge, write_json_to_storage
from agent.tools.viktor_tools.sdk_compute import (
    ViktorSdkComputeClient,
    select_result_key,
)
from agent.tools.viktor_tools.tool_feedback import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.workflow.entity_ops import (
    ViktorJobUserError,
    ViktorRestEntityClient,
    WorkflowEntityService,
    WorkflowNodeId,
    WorkflowRunEntity,
    get_workflow_entity_service,
    needs_workflow_run_response,
)
from agent.types import AgentContext


class RunNodeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    params_override: dict[str, JsonValue] | None = Field(
        default=None,
        description="Optional JSON-safe params patch for this run.",
    )
    merge_params: bool = Field(
        default=True,
        description="Deep merge the override into saved params before execution.",
    )
    save_params: bool = Field(
        default=False,
        description="Persist the resolved params before running the node method.",
    )
    timeout: int | None = Field(default=None, ge=1)


def _resolve_compute_params(
    saved_params: dict[str, Any],
    override_params: dict[str, JsonValue] | None,
    *,
    merge_params: bool,
) -> dict[str, Any]:
    if not override_params:
        return saved_params
    updates = dict(override_params)
    return deep_merge(saved_params, updates) if merge_params else updates


def _try_editor_session(
    client: ViktorRestEntityClient, target: WorkflowRunEntity
) -> str | None:
    try:
        return client.create_editor_session(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
        )
    except (RuntimeError, ValueError, TypeError, AttributeError):
        return None


def _execute(
    *,
    service: WorkflowEntityService,
    target: WorkflowRunEntity,
    params: dict[str, Any],
    timeout: int | None,
) -> tuple[dict[str, Any], str]:
    if target.entity_mode != "existing_entity" and target.created_for_run:
        return (
            ViktorSdkComputeClient().compute_method(
                workspace_id=target.workspace_id,
                entity_id=target.entity_id,
                method_name=target.method_name,
                params=params,
                timeout=timeout,
            ),
            "sdk_compute",
        )

    client = service.client or ViktorRestEntityClient()
    return (
        client.run_entity_method(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
            method_name=target.method_name,
            params=params,
            editor_session=_try_editor_session(client, target),
            timeout=timeout,
            max_poll_seconds=float(timeout or 300),
        ),
        "rest_job",
    )


def _download_json(selected: Any, client: ViktorRestEntityClient | None) -> Any:
    if not isinstance(selected, dict):
        return selected
    url = selected.get("url")
    if not isinstance(url, str) or not url:
        return selected
    headers = client.auth_headers if client else {}
    response = requests.get(url, headers=headers, timeout=(5.0, 60.0))
    response.raise_for_status()
    try:
        return response.json()
    except requests.JSONDecodeError:
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return selected


def _summary(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"kind": "object", "keys": sorted(map(str, value))[:30]}
    if isinstance(value, list):
        return {"kind": "array", "item_count": len(value)}
    if isinstance(value, str):
        return {"kind": "text", "chars": len(value)}
    return {"kind": type(value).__name__}


async def _run_node(
    *, tool_name: str, node_id: WorkflowNodeId, payload: RunNodeArgs
) -> str:
    try:
        service = get_workflow_entity_service()
        target = service.resolve_entity(node_id)
        saved_params = service.read_last_saved_params(target)
        compute_params = _resolve_compute_params(
            saved_params,
            payload.params_override,
            merge_params=payload.merge_params,
        )
        if payload.save_params:
            service.set_last_saved_params(
                target,
                compute_params,
                message=f"Agent saved params before {tool_name}.",
            )
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(tool=tool_name, node_id=node_id)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        return execution_error_response(
            tool=tool_name,
            message="Could not resolve the BHoM workflow node or its saved params.",
            error=exc,
        )

    try:
        result, backend = _execute(
            service=service,
            target=target,
            params=compute_params,
            timeout=payload.timeout,
        )
        selected = select_result_key(result, target.result_key)
        if target.result_key == "download":
            selected = _download_json(selected, service.client)
        resolved_storage_key = write_json_to_storage(target.storage_key, selected)
    except ViktorJobUserError as exc:
        return validation_error_response(
            tool=tool_name,
            message="The BHoM app rejected the current saved inputs.",
            error=exc,
            retry_tool="get_params_in_node",
            retry_reason="Read the node inputs, correct them in chat or in the app, save, and retry.",
        )
    except (KeyError, ValueError) as exc:
        return validation_error_response(
            tool=tool_name,
            message="The BHoM app returned an unexpected result shape.",
            error=exc,
            retry_tool=tool_name,
        )
    except (
        RuntimeError,
        TypeError,
        AttributeError,
        requests.RequestException,
    ) as exc:
        return execution_error_response(
            tool=tool_name,
            message="BHoM method execution or result storage failed.",
            error=exc,
        )

    return tool_response(
        "completed",
        node_id=node_id,
        entity_id=target.entity_id,
        url=target.url,
        method_name=target.method_name,
        execution_backend=backend,
        result_key=target.result_key,
        storage_key=resolved_storage_key,
        saved_params=payload.save_params,
        summary=_summary(selected),
    )


def _args(args: str, tool_name: str) -> RunNodeArgs | str:
    try:
        return RunNodeArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool=tool_name,
            message="Invalid BHoM node run arguments.",
            error=exc,
            retry_tool=tool_name,
        )


async def run_revit_connector_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    payload = _args(args, "run_revit_connector")
    if isinstance(payload, str):
        return payload
    return await _run_node(
        tool_name="run_revit_connector", node_id="revit_connector", payload=payload
    )


async def run_material_template_mapping_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    payload = _args(args, "run_material_template_mapping")
    if isinstance(payload, str):
        return payload
    return await _run_node(
        tool_name="run_material_template_mapping",
        node_id="material_template_mapping",
        payload=payload,
    )


async def run_lca_analysis_func(context: ToolContext[AgentContext], args: str) -> str:
    payload = _args(args, "run_lca_analysis")
    if isinstance(payload, str):
        return payload
    return await _run_node(
        tool_name="run_lca_analysis", node_id="lca_analysis", payload=payload
    )


run_revit_connector = run_revit_connector_func
run_material_template_mapping = run_material_template_mapping_func
run_lca_analysis = run_lca_analysis_func
