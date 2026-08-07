# BHoM Revit-to-LCA workflow agent

This VIKTOR agent coordinates three deployed BHoM applications and keeps their
inputs and results connected through workflow-node tools and entity-scoped
VIKTOR Storage.

```text
Revit connector → GeneralMaterialTakeoff → material-template mapping → BHoM LCA
```

## Workflow tools

- Workflow directory tools resolve the three deployed VIKTOR entities and links.
- Node parameter tools read, deep-merge, replace, and verify saved app inputs.
- Node result tools read persisted outputs from entity-scoped VIKTOR Storage.
- Handoff tools propagate the Revit takeoff into material mapping, then propagate
  the approved material template and takeoff into LCA.
- Run tools can execute configured VIKTOR methods and store their selected result.

The mapping step requires an engineer to review and approve the material-to-EPD
choices. When a user completes an app step manually, the agent reads the saved
node parameters or stored result before continuing.

## Configuration

Copy `.env.example` to `.env`. `TOKEN_VK_APP` and `ENV_VKT` are used only for
VIKTOR entity and method access. The chat model uses `vkt.ViktorOpenAI`, so no
external LLM API key is required. `.env` is ignored and must never be committed.

## Project structure

- `agent/tools/graph_tools/` and `workflow_graph/`: graph, plan, HTML, CSS, and JavaScript.
- `agent/tools/viktor_tools/workflow/`: entity, parameter, result, and compute abstractions.
- `agent/tools/viktor_tools/bhom/`: BHoM storage, run, and handoff behavior.
- `convert-app-params-to-schema/`: discovery notebooks and captured app contracts.
- `tests/`: isolated workflow and handoff tests that do not call live VIKTOR apps.

## Validation

```bash
uv run ruff format --check --no-cache .
uv run ruff check --no-cache .
uv run ty check .
uv run mypy .
xmllint --noout agent/system_prompt.xml
```
