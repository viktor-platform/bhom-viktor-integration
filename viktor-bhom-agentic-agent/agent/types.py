"""Share request context and empty-input schemas across the agent and its tools"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict


@dataclass
class AgentContext:
    entity_id: int | None = None
    workspace_id: int | None = None


class EmptyToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
