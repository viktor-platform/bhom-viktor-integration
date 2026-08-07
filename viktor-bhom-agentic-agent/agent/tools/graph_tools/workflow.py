"""Let the agent compose a workflow DAG and maintain its visible execution plan"""

import json
from typing import Any, Literal

import viktor as vkt
from agents.tool_context import ToolContext
from pydantic import BaseModel, Field

from agent.tools.viktor_tools.bhom.common import (
    STORAGE_SCOPE,
    WORKFLOW_HTML_STORAGE_KEY,
    workflow_storage_key,
)
from agent.types import AgentContext, EmptyToolArgs
from workflow_graph.models import (
    Connection,
    Node,
    PlanTodo,
    Workflow,
    WorkflowCanvasState,
    WorkflowPlan,
)
from workflow_graph.state import (
    build_canvas_state,
    load_canvas_state,
    save_canvas_state,
)
from workflow_graph.viewer import WorkflowViewer


class WorkflowNodeInput(BaseModel):
    node_id: str = Field(..., description="Stable unique id for this workflow node.")
    label: str = Field(..., description="Human-readable node label.")
    node_type: str = Field(default="default", description="Visual node type.")
    icon: str | None = Field(
        default=None,
        description="Optional short icon label rendered in the node icon, for example R or F.",
    )
    icon_bg: str | None = Field(
        default=None,
        description="Optional CSS color for the node icon background.",
    )
    url: str | None = Field(default=None, description="Optional URL opened on click.")
    depends_on: list[str] = Field(
        default_factory=list,
        description="Upstream node ids that must run before this node.",
    )


class ComposeWorkflowGraphArgs(BaseModel):
    workflow_name: str = Field(..., description="Name shown in the graph state.")
    nodes: list[WorkflowNodeInput] = Field(..., description="DAG nodes.")


class PlanTodoInput(BaseModel):
    id: str = Field(..., description="Stable todo id.")
    label: str = Field(..., description="Short todo label.")
    status: Literal["pending", "in_progress", "completed", "failed", "cancelled"] = (
        "pending"
    )
    description: str | None = None


class SetWorkflowPlanArgs(BaseModel):
    title: str = Field(..., description="Plan card title.")
    description: str | None = None
    todos: list[PlanTodoInput] = Field(..., description="Ordered plan items.")
    max_visible_todos: int = Field(default=6, ge=1)


class UpdatePlanTodoInput(BaseModel):
    id: str = Field(..., description="Existing todo id to update.")
    label: str | None = None
    status: (
        Literal["pending", "in_progress", "completed", "failed", "cancelled"] | None
    ) = None
    description: str | None = None


class UpdateWorkflowPlanArgs(BaseModel):
    title: str | None = None
    description: str | None = None
    max_visible_todos: int | None = Field(default=None, ge=1)
    todos: list[UpdatePlanTodoInput] = Field(default_factory=list)
    append_missing: bool = Field(
        default=False,
        description="Append unknown todo ids. New items require a label.",
    )


def validate_dag(nodes: list[WorkflowNodeInput]) -> list[tuple[str, str]]:
    ids = [node.node_id for node in nodes]
    duplicate_ids = sorted({node_id for node_id in ids if ids.count(node_id) > 1})
    if duplicate_ids:
        raise ValueError(f"Duplicate node id(s): {', '.join(duplicate_ids)}")

    id_set = set(ids)
    edges: list[tuple[str, str]] = []
    for node in nodes:
        unknown = [dep for dep in node.depends_on if dep not in id_set]
        if unknown:
            raise ValueError(
                f"Node '{node.node_id}' depends on unknown node(s): {', '.join(unknown)}"
            )
        for dep in node.depends_on:
            edges.append((dep, node.node_id))

    indegree = {node_id: 0 for node_id in ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for source, target in edges:
        outgoing[source].append(target)
        indegree[target] += 1

    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        node_id = queue.pop(0)
        visited += 1
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if visited != len(ids):
        raise ValueError("Cycle detected in depends_on; workflow graph must be a DAG.")
    return edges


def require_canvas_state() -> WorkflowCanvasState:
    state = load_canvas_state()
    if state is None:
        raise ValueError("No workflow graph exists. Run compose_workflow_graph first.")
    return state


def tool_response(status: str, **payload: Any) -> str:
    return json.dumps({"status": status, **payload}, indent=2)


def tool_error_response(tool: str, error: Exception) -> str:
    return tool_response(
        "error",
        tool=tool,
        error_type=type(error).__name__,
        message=str(error),
    )


async def compose_workflow_graph_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    try:
        payload = ComposeWorkflowGraphArgs.model_validate_json(args or "{}")
        edges = validate_dag(payload.nodes)

        workflow = Workflow(
            nodes=[
                Node(
                    id=node.node_id,
                    title=node.label,
                    type=node.node_type,
                    icon=node.icon,
                    icon_bg=node.icon_bg,
                    url=node.url,
                    depends_on=[Connection(node_id=dep) for dep in node.depends_on],
                )
                for node in payload.nodes
            ]
        )
        state = build_canvas_state(payload.workflow_name, workflow)
        viewer = WorkflowViewer(lambda: state)
        save_canvas_state(state)
        vkt.Storage().set(
            workflow_storage_key(WORKFLOW_HTML_STORAGE_KEY),
            data=vkt.File.from_data(
                json.dumps(
                    {
                        "workflow_name": payload.workflow_name,
                        "html": viewer.render_html(),
                    }
                )
            ),
            scope=STORAGE_SCOPE,
        )

        return tool_response(
            "completed",
            workflow_name=payload.workflow_name,
            node_count=len(payload.nodes),
            dependency_count=len(edges),
            storage_key=workflow_storage_key(WORKFLOW_HTML_STORAGE_KEY),
        )
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return tool_error_response("compose_workflow_graph", exc)


async def get_workflow_plan_func(context: ToolContext[AgentContext], args: str) -> str:
    try:
        EmptyToolArgs.model_validate_json(args or "{}")
        state = load_canvas_state()
        if state is None:
            raise ValueError(
                "No workflow graph exists. Run compose_workflow_graph first."
            )
        if state.plan is None:
            raise ValueError("No workflow plan exists. Run set_workflow_plan first.")

        return tool_response(
            "completed",
            workflow_name=state.workflow_name,
            title=state.plan.title,
            description=state.plan.description,
            todos=[todo.model_dump() for todo in state.plan.todos],
        )
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return tool_error_response("get_workflow_plan", exc)


async def set_workflow_plan_func(context: ToolContext[AgentContext], args: str) -> str:
    try:
        payload = SetWorkflowPlanArgs.model_validate_json(args or "{}")
        state = require_canvas_state()

        state.plan = WorkflowPlan(
            id=state.plan.id if state.plan else "workflow-plan",
            title=payload.title,
            description=payload.description,
            todos=[
                PlanTodo(
                    id=todo.id,
                    label=todo.label,
                    status=todo.status,
                    description=todo.description,
                )
                for todo in payload.todos
            ],
            max_visible_todos=payload.max_visible_todos,
        )
        save_canvas_state(state)
        return tool_response("completed", todo_count=len(payload.todos))
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return tool_error_response("set_workflow_plan", exc)


async def update_workflow_plan_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    try:
        payload = UpdateWorkflowPlanArgs.model_validate_json(args or "{}")
        state = require_canvas_state()

        if state.plan is None:
            raise ValueError("No workflow plan exists. Run set_workflow_plan first.")

        todos_by_id = {todo.id: todo for todo in state.plan.todos}
        missing: list[str] = []
        updated = 0
        appended = 0

        for update in payload.todos:
            todo = todos_by_id.get(update.id)
            if todo is None:
                if not payload.append_missing:
                    missing.append(update.id)
                    continue
                if not update.label:
                    raise ValueError(f"New todo '{update.id}' requires a label.")
                todo = PlanTodo(
                    id=update.id,
                    label=update.label,
                    status=update.status or "pending",
                    description=update.description,
                )
                state.plan.todos.append(todo)
                todos_by_id[todo.id] = todo
                appended += 1
                continue

            if update.label is not None:
                todo.label = update.label
            if update.status is not None:
                todo.status = update.status
            if update.description is not None:
                todo.description = update.description
            updated += 1

        if missing:
            raise ValueError(f"Unknown todo id(s): {', '.join(missing)}")

        if payload.title is not None:
            state.plan.title = payload.title
        if payload.description is not None:
            state.plan.description = payload.description
        if payload.max_visible_todos is not None:
            state.plan.max_visible_todos = payload.max_visible_todos

        save_canvas_state(state)
        return tool_response("completed", updated=updated, appended=appended)
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return tool_error_response("update_workflow_plan", exc)
