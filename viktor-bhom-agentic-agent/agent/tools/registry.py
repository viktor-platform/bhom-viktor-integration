"""Assemble graph, node, run, storage, and BHoM handoff tools."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    module: str
    schema: str
    function: str
    strict_json_schema: bool = True


GRAPH_TOOL_SPECS = (
    ToolSpec(
        "compose_workflow_graph",
        "Compose the Revit-to-LCA dependency graph in the workflow WebView.",
        "agent.tools.graph_tools",
        "ComposeWorkflowGraphArgs",
        "compose_workflow_graph_func",
    ),
    ToolSpec(
        "get_workflow_plan",
        "Read current workflow plan ids and statuses.",
        "agent.tools.graph_tools.workflow",
        "EmptyToolArgs",
        "get_workflow_plan_func",
    ),
    ToolSpec(
        "set_workflow_plan",
        "Set the Revit-to-LCA workflow plan.",
        "agent.tools.graph_tools",
        "SetWorkflowPlanArgs",
        "set_workflow_plan_func",
    ),
    ToolSpec(
        "update_workflow_plan",
        "Update workflow plan items by stable id.",
        "agent.tools.graph_tools",
        "UpdateWorkflowPlanArgs",
        "update_workflow_plan_func",
    ),
)


BHOM_TOOL_SPECS = (
    ToolSpec(
        "create_workflow_entity_directory",
        "Resolve the three deployed BHoM node entities and publish their graph.",
        "agent.tools.viktor_tools.workflow.entity_ops",
        "CreateWorkflowEntityDirectoryArgs",
        "create_workflow_entity_directory_func",
    ),
    ToolSpec(
        "get_workflow_entity_directory",
        "Read active BHoM node entity ids, URLs, methods, storage keys, and dependencies.",
        "agent.tools.viktor_tools.workflow.entity_ops",
        "EmptyToolArgs",
        "get_workflow_entity_directory_func",
    ),
    ToolSpec(
        "reset_workflow_entity_directory",
        "Clear the active BHoM workflow directory after explicit confirmation.",
        "agent.tools.viktor_tools.workflow.entity_ops",
        "ResetWorkflowEntityDirectoryArgs",
        "reset_workflow_entity_directory_func",
    ),
    ToolSpec(
        "get_params_in_node",
        "Read the last saved params from one BHoM workflow node.",
        "agent.tools.viktor_tools.workflow.param_ops",
        "GetParamsInNodeArgs",
        "get_params_in_node_func",
    ),
    ToolSpec(
        "set_params_in_node",
        "Deep-merge or replace saved params in one BHoM workflow node and verify readback.",
        "agent.tools.viktor_tools.workflow.param_ops",
        "SetParamsInNodeArgs",
        "set_params_in_node_func",
        False,
    ),
    ToolSpec(
        "clear_params_in_node",
        "Clear selected or all saved params after explicit confirmation.",
        "agent.tools.viktor_tools.workflow.param_ops",
        "ClearParamsInNodeArgs",
        "clear_params_in_node_func",
        False,
    ),
    ToolSpec(
        "apply_set_params_method_in_node",
        "Run and persist a supported BHoM set-params-button result.",
        "agent.tools.viktor_tools.workflow.param_ops",
        "ApplySetParamsMethodInNodeArgs",
        "apply_set_params_method_in_node_func",
        False,
    ),
    ToolSpec(
        "get_result_from_node",
        "Read the result persisted in VIKTOR Storage for one workflow node.",
        "agent.tools.viktor_tools.workflow.result_ops",
        "GetResultFromNodeArgs",
        "get_result_from_node_func",
    ),
    ToolSpec(
        "run_revit_connector",
        "Run download_takeoff for the Revit connector and store the takeoff result.",
        "agent.tools.viktor_tools.bhom.run_apps",
        "RunNodeArgs",
        "run_revit_connector_func",
        False,
    ),
    ToolSpec(
        "handoff_revit_connector_to_material_template_mapping",
        "Patch the stored Revit takeoff and floor area into material mapping and verify readback.",
        "agent.tools.viktor_tools.bhom.handoffs",
        "HandoffRevitToMappingArgs",
        "handoff_revit_connector_to_material_template_mapping_func",
    ),
    ToolSpec(
        "run_material_template_mapping",
        "Read workflow_handoff_view from material mapping and store its result.",
        "agent.tools.viktor_tools.bhom.run_apps",
        "RunNodeArgs",
        "run_material_template_mapping_func",
        False,
    ),
    ToolSpec(
        "handoff_material_template_mapping_to_lca_analysis",
        "Patch the approved material template and takeoff into LCA and verify readback.",
        "agent.tools.viktor_tools.bhom.handoffs",
        "HandoffMappingToLcaArgs",
        "handoff_material_template_mapping_to_lca_analysis_func",
    ),
    ToolSpec(
        "run_lca_analysis",
        "Run the LCA analysis download method and store the normalized result.",
        "agent.tools.viktor_tools.bhom.run_apps",
        "RunNodeArgs",
        "run_lca_analysis_func",
        False,
    ),
)


TOOL_DISPLAY_NAMES = {
    "compose_workflow_graph": "Compose BHoM Workflow Graph",
    "get_workflow_plan": "Get BHoM Workflow Plan",
    "set_workflow_plan": "Set BHoM Workflow Plan",
    "update_workflow_plan": "Update BHoM Workflow Plan",
    "create_workflow_entity_directory": "Resolve BHoM Workflow Apps",
    "get_workflow_entity_directory": "Get BHoM Workflow Apps",
    "reset_workflow_entity_directory": "Reset BHoM Workflow Apps",
    "get_params_in_node": "Get BHoM Node Params",
    "set_params_in_node": "Set BHoM Node Params",
    "clear_params_in_node": "Clear BHoM Node Params",
    "apply_set_params_method_in_node": "Apply BHoM SetParams Method",
    "get_result_from_node": "Get BHoM Node Result",
    "run_revit_connector": "Get Revit Takeoff",
    "handoff_revit_connector_to_material_template_mapping": "Send Takeoff to Material Mapping",
    "run_material_template_mapping": "Read Approved Material Mapping",
    "handoff_material_template_mapping_to_lca_analysis": "Send Approved Template to LCA",
    "run_lca_analysis": "Run BHoM LCA Analysis",
}


def _has_open_additional_properties(value: Any) -> bool:
    if isinstance(value, dict):
        additional_properties = value.get("additionalProperties")
        if additional_properties not in (None, False):
            return True
        return any(_has_open_additional_properties(child) for child in value.values())
    if isinstance(value, list):
        return any(_has_open_additional_properties(item) for item in value)
    return False


def _load_tool(spec: ToolSpec) -> tuple[type[BaseModel], Any]:
    module = import_module(spec.module)
    schema = getattr(module, spec.schema)
    function = getattr(module, spec.function)
    return schema, function


def _function_tool(spec: ToolSpec) -> Any:
    from agents import FunctionTool

    schema, function = _load_tool(spec)
    params_json_schema = schema.model_json_schema()
    strict = spec.strict_json_schema and not _has_open_additional_properties(
        params_json_schema
    )
    return FunctionTool(
        name=spec.name,
        description=spec.description,
        params_json_schema=params_json_schema,
        on_invoke_tool=function,
        strict_json_schema=strict,
    )


def get_tools() -> list[Any]:
    return [_function_tool(spec) for spec in GRAPH_TOOL_SPECS + BHOM_TOOL_SPECS]
