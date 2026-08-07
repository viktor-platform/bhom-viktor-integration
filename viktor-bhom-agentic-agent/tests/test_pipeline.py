import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.pipeline import build_revit_request, inventory_from_takeoff

TAKEOFF = {
    "_t": "BH.oM.Physical.Materials.GeneralMaterialTakeoff",
    "MaterialTakeoffItems": [
        {
            "Material": {
                "_t": "BH.oM.Physical.Materials.Material",
                "Name": "Concrete",
                "Density": 2400,
            },
            "Volume": 2,
            "Mass": 4800,
        }
    ],
}


def test_inventory_groups_takeoff_materials():
    assert inventory_from_takeoff(TAKEOFF) == [
        {
            "material_name": "Concrete",
            "volume_m3": 2.0,
            "mass_kg": 4800.0,
            "density_kg_m3": 2400,
        }
    ]


def test_revit_handoff_uses_existing_worker_contract():
    request = build_revit_request(["Walls"], 100)
    assert request["operation"] == "pull_model_snapshot"
    assert request["options"]["include_material_takeoff"] is True
