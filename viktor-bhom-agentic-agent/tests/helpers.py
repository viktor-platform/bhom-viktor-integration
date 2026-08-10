from copy import deepcopy
from typing import Any


class FakeNodeService:
    def __init__(
        self, directory: Any, params_by_node: dict[str, dict[str, Any]]
    ) -> None:
        self.client: Any = None
        self.directory = directory
        self.params_by_node = deepcopy(params_by_node)
        self.saved_messages: list[str] = []

    def load_directory(self) -> Any:
        return self.directory

    def resolve_entity(self, node_id: str) -> Any:
        return self.directory.entities[node_id]

    def read_last_saved_params(self, target: Any) -> dict[str, Any]:
        return deepcopy(self.params_by_node[target.node_id])

    def read_raw_saved_params(self, target: Any) -> dict[str, Any]:
        return self.read_last_saved_params(target)

    def set_last_saved_params(
        self, target: Any, params: dict[str, Any], *, message: str
    ) -> None:
        self.params_by_node[target.node_id] = deepcopy(params)
        self.saved_messages.append(message)
