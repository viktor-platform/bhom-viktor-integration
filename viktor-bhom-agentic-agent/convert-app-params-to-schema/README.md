# BHoM app discovery notebooks

These notebooks capture the deployed contracts for the three workflow nodes:

1. `bhom_revit_connector_14972.ipynb` — workspace 3424, entity 14972.
2. `bhom_material_template_mapping_14969.ipynb` — workspace 3425, entity 14969.
3. `bhom_lca_analysis_14973.ipynb` — workspace 3423, entity 14973.

Credentials are loaded from `.env`; use `.env.example` as the template. Method
execution is off by default and requires both `RUN_METHOD=true` and an explicit
`METHOD_NAME`.

The three notebooks are executed in place. Their exact input schemas and method
inventories are written to `artifacts/`.
