import json
from dataclasses import asdict, dataclass
from typing import Any

import viktor as vkt

STORAGE_KEY = "bhom-agentic-workflow/state.json"


@dataclass
class WorkflowState:
    revit_handoff: dict[str, Any] | None = None
    mapping_handoff: dict[str, Any] | None = None
    lca_handoff: dict[str, Any] | None = None


def save_state(state: WorkflowState) -> None:
    vkt.Storage().set(
        STORAGE_KEY,
        data=vkt.File.from_data(json.dumps(asdict(state), ensure_ascii=False)),
        scope="entity",
    )


def load_state() -> WorkflowState:
    try:
        stored = vkt.Storage().get(STORAGE_KEY, scope="entity")
        data = json.loads(stored.getvalue_binary().decode("utf-8"))
    except (
        AttributeError,
        FileNotFoundError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return WorkflowState()
    return WorkflowState(
        revit_handoff=data.get("revit_handoff"),
        mapping_handoff=data.get("mapping_handoff"),
        lca_handoff=data.get("lca_handoff"),
    )
