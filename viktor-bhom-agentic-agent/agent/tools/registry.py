from typing import Any

from agent.tools.bhom import (
    prepare_lca_handoff_tool,
    prepare_mapping_handoff_tool,
    prepare_revit_handoff_tool,
)

TOOL_DISPLAY_NAMES = {
    "prepare_revit_handoff_tool": "Prepare Revit Material Takeoff Handoff",
    "prepare_mapping_handoff_tool": "Prepare BHoM EPD Mapping Handoff",
    "prepare_lca_handoff_tool": "Prepare BHoM LCA Handoff",
}


def get_tools() -> list[Any]:
    return [
        prepare_revit_handoff_tool,
        prepare_mapping_handoff_tool,
        prepare_lca_handoff_tool,
    ]
