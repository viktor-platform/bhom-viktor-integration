from typing import Any

import viktor as vkt

from agent.runner import workflow_agent_runtime
from agent.state import load_state
from agent.types import AgentContext
from workflow_graph.state import build_canvas_state, save_canvas_state


class Parametrization(vkt.Parametrization):
    title = vkt.Text(
        """# BHoM LCA workflow agent
Pull a Revit material takeoff, search installed BHoM EPD datasets, approve material mappings, and run life-cycle assessment."""
    )
    chat = vkt.Chat(
        "",
        method="call_llm",
        flex=100,
        first_message=(
            "I can pull the Revit takeoff and search installed BHoM datasets. "
            "I will ask you to approve EPD mappings before I run LCA."
        ),
    )


class Controller(vkt.Controller):
    parametrization = Parametrization

    def call_llm(self, params: Any, **kwargs: Any) -> Any:
        if not params.chat:
            return None
        messages = params.chat.get_messages()
        stream = workflow_agent_runtime.stream(
            [
                {"role": message["role"], "content": message["content"]}
                for message in messages
            ],
            context=AgentContext(),
        )
        return vkt.ChatResult(params.chat, stream)

    @vkt.WebView("Workflow graph", width=100)
    def workflow_graph(self, params: Any, **kwargs: Any) -> Any:
        save_canvas_state()
        graph = build_canvas_state()
        nodes = "".join(
            f"<li><strong>{node.icon}</strong> {node.title}</li>"
            for node in graph.nodes
        )
        return vkt.WebResult(
            html=(
                "<html><body style='font-family:Arial;padding:16px'>"
                "<h2>BHoM Revit-to-LCA workflow</h2>"
                f"<ol>{nodes}</ol>"
                "<p>EPD mappings require explicit human approval.</p>"
                "</body></html>"
            )
        )

    @vkt.DataView("Workflow status", duration_guess=1)
    def workflow_status(self, params: Any, **kwargs: Any) -> Any:
        state = load_state()
        return vkt.DataResult(
            vkt.DataGroup(
                vkt.DataItem(
                    "Revit handoff", "Ready" if state.revit_handoff else "Not prepared"
                ),
                vkt.DataItem(
                    "Mapping handoff",
                    "Ready" if state.mapping_handoff else "Not prepared",
                ),
                vkt.DataItem(
                    "LCA handoff", "Ready" if state.lca_handoff else "Not prepared"
                ),
            )
        )
