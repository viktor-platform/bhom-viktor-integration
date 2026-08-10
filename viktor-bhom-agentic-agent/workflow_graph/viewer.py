import json
from collections.abc import Callable
from pathlib import Path

from workflow_graph.models import WorkflowCanvasState


class WorkflowViewer:
    def __init__(
        self,
        workflow_factory: Callable[[], WorkflowCanvasState],
    ) -> None:
        self._workflow_factory = workflow_factory

    def render_html(self) -> str:
        module_dir = Path(__file__).resolve().parent
        template = (module_dir / "workflow.html").read_text(encoding="utf-8")
        css = (module_dir / "styles.css").read_text(encoding="utf-8")
        js = (module_dir / "workflow.js").read_text(encoding="utf-8")
        js = js.replace("export class WorkflowGraph", "class WorkflowGraph")

        canvas_state = self._workflow_factory()
        state_json = json.dumps(canvas_state.model_dump(), ensure_ascii=False).replace(
            "<", "\\u003c"
        )

        return (
            template.replace("{{ workflow_css }}", css)
            .replace("{{ workflow_state }}", state_json)
            .replace("{{ workflow_js }}", js)
        )
