---
name: bhom-revit-lca-workflow
description: Operate or modify the BHoM VIKTOR workflow agent that transfers a Revit material takeoff through material-template mapping into life-cycle assessment.
---

# BHoM Revit-to-LCA workflow

The workflow has three fixed nodes:

1. `revit_connector` — workspace 3424, entity 14972.
2. `material_template_mapping` — workspace 3425, entity 14969.
3. `lca_analysis` — workspace 3423, entity 14973.

Use VIKTOR's built-in LLM through `vkt.ViktorOpenAI`; do not require an external
LLM API key.

## Rules

- Create the workflow entity directory before reading node inputs or results.
- Preserve user-entered app inputs by deep-merging handoff fields.
- Read back saved target parameters after every critical handoff.
- Store large node outputs in entity-scoped VIKTOR Storage.
- Never invent a Revit takeoff, material mapping, EPD selection, or LCA result.
- The user must review and save material-to-EPD mappings in the mapping app.
- When the user says a manual step is complete, read the node params and stored
  result before continuing.

## Validation

```bash
uvx ruff format .
uvx ruff check .
uvx ty check --python .venv/bin/python
uvx mypy .
uvx pytest -q
xmllint --noout agent/system_prompt.xml
```
