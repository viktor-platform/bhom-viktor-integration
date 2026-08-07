"""Present the workflow agent chat and graph together in one VIKTOR app"""

from typing import Any

import viktor as vkt
from agents.items import TResponseInputItem
from dotenv import load_dotenv

from agent.runner import workflow_agent_runtime
from agent.types import AgentContext
from workflow_graph.state import delete_canvas_state, load_canvas_state
from workflow_graph.viewer import WorkflowViewer

load_dotenv()


class Parametrization(vkt.Parametrization):
    title = vkt.Text("""# BHoM Revit-to-LCA Workflow Agent
Prepare validated handoffs between the Revit connector, material-template mapping, and LCA analysis applications.""")
    chat = vkt.Chat("", method="call_llm", flex=100)


class Controller(vkt.Controller):
    parametrization = Parametrization

    def call_llm(
        self,
        params: Any,
        entity_id: int | None = None,
        workspace_id: int | None = None,
        **kwargs: Any,
    ) -> Any:
        if not params.chat:
            return None

        messages = params.chat.get_messages()
        chat_history: list[TResponseInputItem] = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
        ]
        stream = workflow_agent_runtime.stream(
            chat_history,
            context=AgentContext(entity_id=entity_id, workspace_id=workspace_id),
            show_tool_progress=True,
        )
        return vkt.ChatResult(params.chat, stream)

    @vkt.WebView("Workflow Graph", width=100)
    def workflow_view(self, params: Any, **kwargs: Any) -> Any:
        if not params.chat:
            delete_canvas_state()

        canvas_state = load_canvas_state()
        if canvas_state:
            return vkt.WebResult(
                html=WorkflowViewer(lambda: canvas_state).render_html()
            )

        html = (
            "<!doctype html><html><head><style>"
            "body{margin:0;background:#fff;}"
            "</style></head><body></body></html>"
        )
        return vkt.WebResult(html=html)
