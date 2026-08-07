# BHoM workflow tests

The unit tests cover the fixed workflow order and IDs:

`revit_connector (3424/14972) -> material_template_mapping (3425/14969) -> lca_analysis (3423/14973)`

They verify the storage-backed Revit-to-mapping and approved-mapping-to-LCA
parameter handoffs. All VIKTOR services and storage reads are replaced with local
fakes or monkeypatches; the suite makes no network calls.

Run the focused handoff contract with:

```bash
uvx --with openai-agents pytest tests/hand_off/test_hand_off.py
```
