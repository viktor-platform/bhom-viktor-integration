"""Define the graph, plan, and canvas state shared by storage and rendering"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PlanStatus = Literal["pending", "in_progress", "completed", "failed", "cancelled"]


class Connection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    kind: str = "default"


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    type: str = "default"
    icon: str | None = None
    icon_bg: str | None = None
    url: str | None = None
    depends_on: list[Connection] = Field(default_factory=list)


class Workflow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[Node] = Field(default_factory=list)


class PlanTodo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    status: PlanStatus = "pending"
    description: str | None = None


class WorkflowPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str | None = None
    todos: list[PlanTodo] = Field(default_factory=list)
    max_visible_todos: int = Field(default=6, ge=1)


class WorkflowCanvasState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_name: str
    workflow: Workflow
    plan: WorkflowPlan | None = None
