import json

from agents import function_tool
from agents.tool_context import ToolContext
from pydantic import BaseModel, ConfigDict, Field

from agent.app_registry import applications
from agent.pipeline import build_revit_request, validate_takeoff
from agent.state import load_state, save_state
from agent.types import AgentContext


class PrepareRevitHandoffArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[str] = Field(default_factory=lambda: ["Walls", "Floors"])
    element_limit: int = Field(default=2500, ge=1, le=10_000)


class PrepareMappingHandoffArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    takeoff_json: str = Field(
        description="GeneralMaterialTakeoff JSON downloaded from the Revit connector."
    )
    gross_floor_area_m2: float = Field(gt=0)


class PrepareLcaHandoffArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    takeoff_json: str
    template_materials_json: str = Field(
        description="Material[] JSON exported by the mapping app after user approval."
    )
    project_name: str
    project_id: str | None = None
    gross_floor_area_m2: float = Field(gt=0)
    modules: list[str] = Field(default_factory=lambda: ["A1toA3"])


def _response(application_key: str, payload: dict[str, object], next_step: str) -> str:
    application = applications()[application_key]
    return json.dumps(
        {
            "status": "handoff_ready",
            "target": {"app": application.label, "url": application.url},
            "params": payload,
            "next_step": next_step,
        },
        ensure_ascii=False,
    )


@function_tool
async def prepare_revit_handoff_tool(
    context: ToolContext[AgentContext], args: PrepareRevitHandoffArgs
) -> str:
    request = build_revit_request(args.categories, args.element_limit)
    state = load_state()
    state.revit_handoff = request
    save_state(state)
    return _response(
        "revit",
        {"pull_request_json": json.dumps(request, ensure_ascii=False)},
        "Open the Revit app, run the pull, then download takeoff.bhom.json and return here with its contents.",
    )


@function_tool
async def prepare_mapping_handoff_tool(
    context: ToolContext[AgentContext], args: PrepareMappingHandoffArgs
) -> str:
    takeoff = validate_takeoff(json.loads(args.takeoff_json))
    payload = {
        "takeoff_json": json.dumps(takeoff, separators=(",", ":"), ensure_ascii=False),
        "gross_floor_area_m2": args.gross_floor_area_m2,
    }
    state = load_state()
    state.mapping_handoff = payload
    save_state(state)
    return _response(
        "mapping",
        payload,
        "Open the mapping app, search the installed BHoM datasets, review and approve one EPD per material, then export template-materials JSON.",
    )


@function_tool
async def prepare_lca_handoff_tool(
    context: ToolContext[AgentContext], args: PrepareLcaHandoffArgs
) -> str:
    takeoff = validate_takeoff(json.loads(args.takeoff_json))
    templates = json.loads(args.template_materials_json)
    if not isinstance(templates, list) or not templates:
        raise ValueError(
            "template_materials_json must contain a non-empty Material[] array."
        )
    payload = {
        "takeoff_json": json.dumps(takeoff, separators=(",", ":"), ensure_ascii=False),
        "template_materials_json": json.dumps(
            templates, separators=(",", ":"), ensure_ascii=False
        ),
        "project_id": (args.project_id or args.project_name).strip(),
        "project_name": args.project_name.strip(),
        "gross_floor_area_m2": args.gross_floor_area_m2,
        "modules": args.modules,
        "prioritise_template_materials": True,
    }
    state = load_state()
    state.lca_handoff = payload
    save_state(state)
    return _response(
        "lca",
        payload,
        "Open the LCA app, apply these run_analysis parameters, and run the analysis on the Windows BHoM worker.",
    )
