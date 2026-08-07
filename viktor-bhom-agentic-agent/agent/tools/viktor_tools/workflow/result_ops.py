"""Retrieve persisted computation output for an active workflow node"""

from agents.tool_context import ToolContext
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.tools.viktor_tools.bhom.common import (
    read_json_from_storage,
    workflow_storage_key,
)
from agent.tools.viktor_tools.tool_feedback import (
    execution_error_response,
    needs_prerequisite_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.workflow.entity_ops import (
    WorkflowNodeId,
    get_workflow_entity_service,
    needs_workflow_run_response,
)
from agent.types import AgentContext


class GetResultFromNodeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: WorkflowNodeId = Field(
        ...,
        description="BHoM workflow node whose stored result should be read.",
    )


async def get_result_from_node_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    try:
        payload = GetResultFromNodeArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="get_result_from_node",
            message="Invalid BHoM workflow node result arguments.",
            error=exc,
            retry_tool="get_result_from_node",
            retry_reason="Retry with a known BHoM workflow node_id.",
        )

    try:
        directory = get_workflow_entity_service().load_directory()
        target = directory.entities[payload.node_id]
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="get_result_from_node", node_id=payload.node_id
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        return execution_error_response(
            tool="get_result_from_node",
            message="Could not resolve the BHoM workflow node result.",
            error=exc,
        )

    resolved_storage_key = workflow_storage_key(
        target.storage_key, run_id=directory.run_id
    )
    try:
        result = read_json_from_storage(
            target.storage_key,
            run_id=directory.run_id,
        )
    except FileNotFoundError:
        return needs_prerequisite_response(
            tool="get_result_from_node",
            message=f"No stored result exists for {payload.node_id}.",
            missing_storage_key=resolved_storage_key,
            retry_tool=f"run_{payload.node_id}",
            retry_reason=f"Run {payload.node_id} to compute and store its result.",
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        return execution_error_response(
            tool="get_result_from_node",
            message="Could not read the stored BHoM workflow node result.",
            error=exc,
        )

    return tool_response(
        "completed",
        message=f"Read the stored result for {payload.node_id}.",
        node_id=payload.node_id,
        entity_id=target.entity_id,
        url=target.url,
        result_key=target.result_key,
        storage_key=resolved_storage_key,
        result=result,
    )


get_result_from_node = get_result_from_node_func
