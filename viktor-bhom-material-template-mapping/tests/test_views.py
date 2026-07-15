import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import viktor as vkt

from app import Controller

LOOKUP_PATH = Path(__file__).parents[1] / "samples" / "lookup-result.sample.json"
CONCRETE_ID = "7b9515a9-7bab-4e98-8542-3fa179c731e5"
STEEL_ID = "a372a265-fd6e-4445-9c03-29ac36e25682"


def params(mapping_state_json='{"schema_version":"1.0","mappings":{}}'):
    return SimpleNamespace(
        takeoff_json="",
        takeoff_file=None,
        dataset_scope="All installed LCA datasets",
        material_inventory=[
            SimpleNamespace(
                material_name="Concrete C30/37",
                search_query="ready mix concrete C30/37",
                volume_m3=32.0,
                density_kg_m3=2400.0,
            ),
            SimpleNamespace(
                material_name="Structural Steel",
                search_query="structural steel",
                volume_m3=0.4,
                density_kg_m3=7850.0,
            ),
        ],
        lookup_results_json=LOOKUP_PATH.read_text(encoding="utf-8"),
        mapping_state_json=mapping_state_json,
        template_materials_json="[]",
        gross_floor_area_m2=1000,
    )


def call_view(controller: Controller, name: str, view_params: SimpleNamespace):
    decorated_method = Controller.__dict__[name]
    view = decorated_method.__self__
    return view._view_function(controller, params=view_params)


class TestViews(unittest.TestCase):
    @patch.dict("os.environ", {"VIKTOR_JS_SDK_PATH": "/sdk/"})
    def test_mapping_view_uses_worker_candidates(self):
        result = call_view(Controller(), "mapping_view", params())

        self.assertIsInstance(result, vkt.WebResult)
        self.assertIn("Material and EPD mapping", result.html)
        self.assertIn("installed BHoM datasets", result.html)

    def test_template_view_reports_worker_search_results(self):
        result = call_view(Controller(), "template_view", params())

        self.assertIsInstance(result, vkt.DataResult)

    def test_complete_template_download_uses_exact_names_and_typed_epds(self):
        state = json.dumps(
            {
                "schema_version": "1.0",
                "mappings": {
                    "Concrete C30/37": CONCRETE_ID,
                    "Structural Steel": STEEL_ID,
                },
            }
        )

        result = Controller().download_template(params=params(state))

        self.assertEqual(result._file_name, "template-materials.bhom.json")
        self.assertIn('"Name": "Concrete C30/37"', result._file_content)
        self.assertIn('"Name": "Structural Steel"', result._file_content)
        self.assertIn("EnvironmentalProductDeclaration", result._file_content)
