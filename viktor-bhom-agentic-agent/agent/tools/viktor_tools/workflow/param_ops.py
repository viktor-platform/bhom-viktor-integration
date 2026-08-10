from typing import Any, Literal, Protocol, cast

from agents.tool_context import ToolContext
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    model_validator,
)

from agent.tools.viktor_tools.bhom.common import deep_merge, paths_for_patch
from agent.tools.viktor_tools.sdk_compute import ViktorSdkComputeClient
from agent.tools.viktor_tools.tool_feedback import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.workflow.entity_ops import (
    ViktorRestEntityClient,
    WorkflowNodeId,
    WorkflowRunEntity,
    get_workflow_entity_service,
    needs_workflow_run_response,
)
from agent.types import AgentContext


class SetParamsInNodeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: WorkflowNodeId = Field(
        ...,
        description="BHoM workflow node whose saved VIKTOR params should be updated.",
    )
    params: dict[str, JsonValue] = Field(
        ...,
        min_length=1,
        description="JSON-safe params patch or replacement payload.",
    )
    merge: bool = Field(
        default=True,
        description="Deep merge into current saved params. If false, replace all saved params.",
    )


class GetParamsInNodeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: WorkflowNodeId = Field(
        ...,
        description="BHoM workflow node whose last saved params should be read.",
    )


class ClearParamsInNodeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: WorkflowNodeId = Field(
        ...,
        description="BHoM workflow node whose saved VIKTOR params should be cleared.",
    )
    confirm: bool = Field(
        default=False,
        description="Must be true to clear saved params.",
    )
    mode: Literal["replace_with_empty", "clear_paths"] = Field(
        default="replace_with_empty",
        description="Replace all saved params with {} or clear selected dot-separated paths.",
    )
    paths: list[str] = Field(
        default_factory=list,
        description="Dot-separated params paths to clear when mode is clear_paths.",
    )
    clear_value: Literal["null", "empty_string", "empty_list", "empty_object"] = Field(
        default="null",
        description="Value written at each selected path when mode is clear_paths.",
    )

    @model_validator(mode="after")
    def validate_mode(self) -> "ClearParamsInNodeArgs":
        if self.mode == "clear_paths" and not self.paths:
            raise ValueError("paths is required when mode is clear_paths.")
        if self.mode == "replace_with_empty" and self.paths:
            raise ValueError("paths can only be used when mode is clear_paths.")
        return self


class ApplySetParamsMethodInNodeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: WorkflowNodeId = Field(
        ...,
        description="BHoM workflow node whose set-params method should be applied.",
    )
    method_name: str = Field(
        ...,
        min_length=1,
        description="Name of a parametrization set-params-button method available on the target app.",
    )
    confirm: bool = Field(
        default=False,
        description="Must be true to persist the returned set_params patch into saved params.",
    )
    merge: bool = Field(
        default=True,
        description="Deep-merge returned set_params into current saved params. If false, replace saved params with the returned patch.",
    )
    timeout: int | None = Field(
        default=None,
        ge=1,
        description="Optional VIKTOR compute timeout in seconds.",
    )


def _clear_value(name: str) -> JsonValue:
    if name == "null":
        return None
    if name == "empty_string":
        return ""
    if name == "empty_list":
        return []
    if name == "empty_object":
        return {}
    raise ValueError(f"Unsupported clear value: {name}")


def _set_path(payload: dict[str, Any], path: str, value: JsonValue) -> None:
    parts = [part.strip() for part in path.split(".") if part.strip()]
    if not parts:
        raise ValueError("Params path cannot be empty.")
    current = payload
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise TypeError(
                f"Cannot clear nested path through non-object field '{part}'."
            )
        current = child
    current[parts[-1]] = value


def _patch_for_cleared_paths(paths: list[str], value: JsonValue) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for path in paths:
        _set_path(patch, path, value)
    return patch


SET_PARAMS_METHODS: dict[WorkflowNodeId, dict[str, dict[str, Any]]] = {
    "material_template_mapping": {
        "search_bhom_database": {
            "method_name": "search_bhom_database",
            "node_type": "set-params-button",
            "label": "Search installed BHoM datasets",
        }
    }
}


def _matches_patch(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _matches_patch(actual[key], value)
            for key, value in expected.items()
        )
    return bool(actual == expected)


def _validate_set_params_method(
    node_id: WorkflowNodeId, method_name: str
) -> dict[str, Any]:
    methods = SET_PARAMS_METHODS.get(node_id, {})
    try:
        return methods[method_name]
    except KeyError as exc:
        available = ", ".join(sorted(methods)) or "<none>"
        raise ValueError(
            f"Method '{method_name}' is not a set-params-button for node '{node_id}'. "
            f"Available set-params methods: {available}."
        ) from exc


def _extract_set_params_patch(result: dict[str, Any]) -> dict[str, Any]:
    set_params = result.get("set_params")
    if isinstance(set_params, dict):
        for key in ("parameters", "params"):
            patch = set_params.get(key)
            if isinstance(patch, dict):
                return cast(dict[str, Any], patch)
        return cast(dict[str, Any], set_params)
    keys = ", ".join(sorted(result)) or "<none>"
    raise ValueError(
        f"SetParams method result does not contain a set_params object. Available keys: {keys}."
    )


def _set_params_method_inputs(
    node_id: WorkflowNodeId,
    method_name: str,
    saved_params: dict[str, Any],
) -> dict[str, Any]:
    if node_id == "material_template_mapping" and method_name == "search_bhom_database":
        return {
            key: saved_params[key]
            for key in ("dataset_scope", "material_inventory")
            if key in saved_params
        }
    return saved_params


def _target_metadata(target: WorkflowRunEntity) -> dict[str, Any]:
    saved_params_are_shared = target.saved_params_are_shared
    metadata: dict[str, Any] = {
        "entity_mode": target.entity_mode,
        "created_for_run": target.created_for_run,
        "saved_params_are_shared": saved_params_are_shared,
    }
    if saved_params_are_shared:
        metadata["shared_params_warning"] = (
            "This node is bound to an existing editor entity; saved param writes mutate that shared entity."
        )
    return metadata


def _uses_rest_job_backend(target: WorkflowRunEntity) -> bool:
    return target.entity_mode == "existing_entity" or not target.created_for_run


def _try_create_editor_session(
    client: ViktorRestEntityClient, target: WorkflowRunEntity
) -> str | None:
    if target.entity_mode != "existing_entity":
        return None
    try:
        return client.create_editor_session(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
        )
    except (RuntimeError, ValueError, TypeError, AttributeError):
        return None


class NodeEntityService(Protocol):
    client: Any

    def resolve_entity(self, node_id: WorkflowNodeId) -> WorkflowRunEntity: ...

    def read_last_saved_params(self, target: WorkflowRunEntity) -> dict[str, Any]: ...

    def read_raw_saved_params(self, target: WorkflowRunEntity) -> dict[str, Any]: ...

    def set_last_saved_params(
        self,
        target: WorkflowRunEntity,
        params: dict[str, Any],
        *,
        message: str,
    ) -> None: ...


def _run_method(
    *,
    entity_service: NodeEntityService,
    compute_client: ViktorSdkComputeClient | None,
    target: WorkflowRunEntity,
    method_name: str,
    method_type: str | None,
    params: dict[str, Any],
    timeout: int | None,
) -> dict[str, Any]:
    if compute_client is not None or not _uses_rest_job_backend(target):
        compute = compute_client or ViktorSdkComputeClient()
        return compute.compute_method(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
            method_name=method_name,
            params=params,
            timeout=timeout,
        )

    rest_client = entity_service.client or ViktorRestEntityClient()
    return rest_client.run_entity_method(
        workspace_id=target.workspace_id,
        entity_id=target.entity_id,
        method_name=method_name,
        method_type=method_type,
        params=params,
        editor_session=_try_create_editor_session(rest_client, target),
        timeout=timeout,
        max_poll_seconds=float(timeout or 120),
    )


class WorkflowNodeParamService:
    def __init__(
        self,
        entity_service: NodeEntityService | None = None,
        compute_client: ViktorSdkComputeClient | None = None,
    ) -> None:
        self.entity_service = entity_service or get_workflow_entity_service()
        self.compute_client = compute_client

    def get_params(self, payload: GetParamsInNodeArgs) -> dict[str, Any]:
        target = self.entity_service.resolve_entity(payload.node_id)
        params = self.entity_service.read_last_saved_params(target)
        return {
            "node_id": payload.node_id,
            "entity_id": target.entity_id,
            "url": target.url,
            **_target_metadata(target),
            "top_level_keys": sorted(params),
            "params": params,
        }

    def set_params(self, payload: SetParamsInNodeArgs) -> dict[str, Any]:
        target = self.entity_service.resolve_entity(payload.node_id)
        updates = dict(payload.params)
        next_params = updates
        current_top_level_keys: list[str] = []

        if payload.merge:
            current_params = self.entity_service.read_last_saved_params(target)
            current_top_level_keys = sorted(current_params)
            next_params = deep_merge(current_params, updates)

        self.entity_service.set_last_saved_params(
            target,
            next_params,
            message="Agent updated BHoM workflow node params.",
        )
        verified_params = self.entity_service.read_last_saved_params(target)
        if not _matches_patch(verified_params, updates):
            raise RuntimeError(
                "Saved params readback did not match the requested patch."
            )
        return {
            "node_id": payload.node_id,
            "entity_id": target.entity_id,
            "url": target.url,
            **_target_metadata(target),
            "merge": payload.merge,
            "existing_top_level_keys": current_top_level_keys,
            "updated_top_level_keys": sorted(updates),
            "updated_field_paths": paths_for_patch(updates),
            "readback_verified": True,
        }

    def clear_params(self, payload: ClearParamsInNodeArgs) -> dict[str, Any]:
        target = self.entity_service.resolve_entity(payload.node_id)
        current_params = self.entity_service.read_last_saved_params(target)

        if payload.mode == "replace_with_empty":
            patch: dict[str, Any] = {}
            next_params: dict[str, Any] = {}
            cleared_field_paths = ["<all>"]
        else:
            patch = _patch_for_cleared_paths(
                payload.paths, _clear_value(payload.clear_value)
            )
            next_params = deep_merge(current_params, patch)
            cleared_field_paths = paths_for_patch(patch)

        self.entity_service.set_last_saved_params(
            target,
            next_params,
            message="Agent cleared BHoM workflow node params.",
        )
        verified_params = self.entity_service.read_raw_saved_params(target)
        if verified_params != next_params:
            raise RuntimeError(
                "Saved params readback did not match the clear operation payload."
            )

        return {
            "node_id": payload.node_id,
            "entity_id": target.entity_id,
            "url": target.url,
            **_target_metadata(target),
            "mode": payload.mode,
            "clear_value": payload.clear_value
            if payload.mode == "clear_paths"
            else None,
            "previous_top_level_keys": sorted(current_params),
            "remaining_top_level_keys": sorted(verified_params),
            "cleared_field_paths": cleared_field_paths,
            "readback_verified": True,
        }

    def apply_set_params_method(
        self, payload: ApplySetParamsMethodInNodeArgs
    ) -> dict[str, Any]:
        method = _validate_set_params_method(payload.node_id, payload.method_name)
        target = self.entity_service.resolve_entity(payload.node_id)
        current_params = self.entity_service.read_last_saved_params(target)
        result = _run_method(
            entity_service=self.entity_service,
            compute_client=self.compute_client,
            target=target,
            method_name=payload.method_name,
            method_type=str(method.get("node_type") or "") or None,
            params=_set_params_method_inputs(
                payload.node_id,
                payload.method_name,
                current_params,
            ),
            timeout=payload.timeout,
        )
        patch = _extract_set_params_patch(result)
        next_params = deep_merge(current_params, patch) if payload.merge else patch
        self.entity_service.set_last_saved_params(
            target,
            next_params,
            message=f"Agent applied set-params method {payload.method_name}.",
        )
        verified_params = self.entity_service.read_raw_saved_params(target)
        if verified_params != next_params:
            raise RuntimeError(
                "Saved params readback did not match the set-params method payload."
            )

        return {
            "node_id": payload.node_id,
            "entity_id": target.entity_id,
            "url": target.url,
            **_target_metadata(target),
            "method_name": payload.method_name,
            "method_label": method.get("label"),
            "merge": payload.merge,
            "applied_changes": paths_for_patch(patch),
            "previous_top_level_keys": sorted(current_params),
            "remaining_top_level_keys": sorted(verified_params),
            "readback_verified": True,
        }


async def get_params_in_node_func(context: ToolContext[AgentContext], args: str) -> str:
    try:
        payload = GetParamsInNodeArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="get_params_in_node",
            message="Invalid BHoM workflow node params arguments.",
            error=exc,
            retry_tool="get_params_in_node",
            retry_reason="Retry with node_id.",
        )

    try:
        result = WorkflowNodeParamService().get_params(payload)
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="get_params_in_node", node_id=payload.node_id
        )
    except (RuntimeError, TypeError, AttributeError) as exc:
        return execution_error_response(
            tool="get_params_in_node",
            message="Could not read BHoM workflow node saved params.",
            error=exc,
        )

    return tool_response(
        "completed", message="Read BHoM workflow node saved params.", **result
    )


async def set_params_in_node_func(context: ToolContext[AgentContext], args: str) -> str:
    try:
        payload = SetParamsInNodeArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="set_params_in_node",
            message="Invalid BHoM workflow node params arguments.",
            error=exc,
            retry_tool="set_params_in_node",
            retry_reason="Retry with node_id and a non-empty JSON-safe params object.",
        )

    try:
        result = WorkflowNodeParamService().set_params(payload)
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="set_params_in_node", node_id=payload.node_id
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        return execution_error_response(
            tool="set_params_in_node",
            message="Could not update BHoM workflow node saved params.",
            error=exc,
        )

    return tool_response(
        "completed", message="Updated BHoM workflow node saved params.", **result
    )


async def clear_params_in_node_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    try:
        payload = ClearParamsInNodeArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="clear_params_in_node",
            message="Invalid BHoM workflow node params cleanup arguments.",
            error=exc,
            retry_tool="clear_params_in_node",
            retry_reason="Retry with node_id, confirm=true, and either replace_with_empty or clear_paths arguments.",
        )

    if not payload.confirm:
        return tool_response(
            "needs_user_input",
            tool="clear_params_in_node",
            node_id=payload.node_id,
            message="Confirm params cleanup by retrying with confirm=true.",
            confirmation_required=True,
        )

    try:
        result = WorkflowNodeParamService().clear_params(payload)
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="clear_params_in_node", node_id=payload.node_id
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        return execution_error_response(
            tool="clear_params_in_node",
            message="Could not clear BHoM workflow node saved params.",
            error=exc,
        )

    return tool_response(
        "completed", message="Cleared BHoM workflow node saved params.", **result
    )


async def apply_set_params_method_in_node_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    try:
        payload = ApplySetParamsMethodInNodeArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="apply_set_params_method_in_node",
            message="Invalid BHoM workflow set-params method arguments.",
            error=exc,
            retry_tool="apply_set_params_method_in_node",
            retry_reason="Retry with node_id, method_name, and confirm=true.",
        )

    if not payload.confirm:
        return tool_response(
            "needs_user_input",
            tool="apply_set_params_method_in_node",
            node_id=payload.node_id,
            method_name=payload.method_name,
            message="Confirm set-params method persistence by retrying with confirm=true.",
            confirmation_required=True,
        )

    try:
        result = WorkflowNodeParamService().apply_set_params_method(payload)
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="apply_set_params_method_in_node",
            node_id=payload.node_id,
        )
    except ValueError as exc:
        return validation_error_response(
            tool="apply_set_params_method_in_node",
            message="The requested method is not a valid set-params cleanup method for this node.",
            error=exc,
            retry_tool="apply_set_params_method_in_node",
            retry_reason="Retry with one of the available set-params-button method names for this node.",
        )
    except (RuntimeError, TypeError, AttributeError) as exc:
        return execution_error_response(
            tool="apply_set_params_method_in_node",
            message="Could not apply BHoM workflow set-params method to saved params.",
            error=exc,
        )

    return tool_response(
        "completed",
        message="Applied BHoM workflow set-params method to saved params.",
        **result,
    )
