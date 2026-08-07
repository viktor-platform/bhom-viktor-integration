import viktor as vkt

from workflow_graph.models import Connection, Node, PlanTodo, WorkflowCanvasState

STORAGE_KEY = "bhom-agentic-workflow/graph.json"


def build_canvas_state() -> WorkflowCanvasState:
    nodes = [
        Node(id="revit", title="Revit material takeoff", icon="R", icon_bg="#dbeafe"),
        Node(
            id="epd",
            title="EPD database mapping",
            icon="E",
            icon_bg="#fef3c7",
            depends_on=[Connection(node_id="revit")],
        ),
        Node(
            id="lca",
            title="BHoM LCA analysis",
            icon="L",
            icon_bg="#dcfce7",
            depends_on=[Connection(node_id="epd")],
        ),
    ]
    return WorkflowCanvasState(
        workflow_name="BHoM Revit-to-LCA workflow",
        nodes=nodes,
        todos=[PlanTodo(id=node.id, label=node.title) for node in nodes],
    )


def save_canvas_state() -> None:
    vkt.Storage().set(
        STORAGE_KEY,
        data=vkt.File.from_data(build_canvas_state().model_dump_json()),
        scope="entity",
    )
