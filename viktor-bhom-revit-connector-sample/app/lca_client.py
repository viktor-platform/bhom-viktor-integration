from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import viktor as vkt


@dataclass(frozen=True)
class LcaServiceLocation:
    token: str
    workspace_id: int
    entity_id: int


def call_lca_service(
    *,
    location: LcaServiceLocation,
    handoff: dict[str, Any],
    timeout_seconds: int = 900,
) -> Any:
    """Call the independently deployed carbon-analysis entity."""
    api = vkt.api_v1.API(token=location.token)
    entity = api.get_entity(
        location.entity_id,
        workspace_id=location.workspace_id,
    )
    return entity.compute(
        method_name=str(handoff["target"]["method_name"]),
        params=dict(handoff["params"]),
        timeout=timeout_seconds,
    )
