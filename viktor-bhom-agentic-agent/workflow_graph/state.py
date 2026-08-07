import re

import viktor as vkt

from agent.tools.viktor_tools.bhom.common import (
    STORAGE_SCOPE,
    WORKFLOW_GRAPH_STATE_STORAGE_KEY,
    delete_storage_key,
    workflow_storage_key,
)
from workflow_graph.models import (
    Node,
    PlanTodo,
    Workflow,
    WorkflowCanvasState,
    WorkflowPlan,
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "workflow"


def topological_node_order(workflow: Workflow) -> list[Node]:
    by_id = {node.id: node for node in workflow.nodes}
    indegree = {node.id: 0 for node in workflow.nodes}
    outgoing: dict[str, list[str]] = {node.id: [] for node in workflow.nodes}

    for node in workflow.nodes:
        for dependency in node.depends_on:
            outgoing.setdefault(dependency.node_id, []).append(node.id)
            indegree[node.id] = indegree.get(node.id, 0) + 1

    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    order: list[str] = []
    while queue:
        node_id = queue.pop(0)
        order.append(node_id)
        for downstream in outgoing.get(node_id, []):
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                queue.append(downstream)

    if len(order) != len(workflow.nodes):
        return workflow.nodes
    return [by_id[node_id] for node_id in order]


def describe_node(node: Node) -> str | None:
    if not node.depends_on:
        return "Starting point for this workflow."
    upstream = ", ".join(dependency.node_id for dependency in node.depends_on)
    return f"Depends on: {upstream}."


def build_default_plan(workflow_name: str, workflow: Workflow) -> WorkflowPlan:
    todos = [
        PlanTodo(id=node.id, label=node.title, description=describe_node(node))
        for node in topological_node_order(workflow)
    ]
    return WorkflowPlan(
        id=f"{slugify(workflow_name)}-plan",
        title=f"{workflow_name} Plan",
        description="Agent-managed checklist for the current workflow graph.",
        todos=todos,
        max_visible_todos=min(max(len(todos), 1), 6),
    )


def build_canvas_state(workflow_name: str, workflow: Workflow) -> WorkflowCanvasState:
    return WorkflowCanvasState(
        workflow_name=workflow_name,
        workflow=workflow,
        plan=build_default_plan(workflow_name, workflow),
    )


def save_canvas_state(state: WorkflowCanvasState, *, run_id: str | None = None) -> None:
    vkt.Storage().set(
        workflow_storage_key(WORKFLOW_GRAPH_STATE_STORAGE_KEY, run_id=run_id),
        data=vkt.File.from_data(state.model_dump_json()),
        scope=STORAGE_SCOPE,
    )


def load_canvas_state(*, run_id: str | None = None) -> WorkflowCanvasState | None:
    storage_key = workflow_storage_key(WORKFLOW_GRAPH_STATE_STORAGE_KEY, run_id=run_id)
    for candidate_key in (storage_key, WORKFLOW_GRAPH_STATE_STORAGE_KEY):
        try:
            stored_file = vkt.Storage().get(candidate_key, scope=STORAGE_SCOPE)
            raw = stored_file.getvalue_binary().decode("utf-8")
            state = WorkflowCanvasState.model_validate_json(raw)
        except (FileNotFoundError, RuntimeError, ValueError, TypeError, AttributeError):
            state = None
        if state is not None:
            return state
    return None


def delete_canvas_state() -> None:
    delete_storage_key(WORKFLOW_GRAPH_STATE_STORAGE_KEY)
