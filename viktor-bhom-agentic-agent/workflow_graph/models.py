from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PlanStatus = Literal["pending", "in_progress", "completed", "failed"]


class Connection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    icon: str
    icon_bg: str
    depends_on: list[Connection] = Field(default_factory=list)


class PlanTodo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    status: PlanStatus = "pending"


class WorkflowCanvasState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_name: str
    nodes: list[Node]
    todos: list[PlanTodo]
