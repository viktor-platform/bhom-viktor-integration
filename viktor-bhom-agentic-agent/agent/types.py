from dataclasses import dataclass


@dataclass
class AgentContext:
    entity_id: int | None = None
    workspace_id: int | None = None
