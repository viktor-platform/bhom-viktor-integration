import base64
import json
import re
from pathlib import Path
from unittest.mock import patch

from app.catalog import parse_lookup_results
from app.webview import build_mapping_html

LOOKUP_PATH = Path(__file__).parents[1] / "samples" / "lookup-result.sample.json"
CONCRETE_ID = "7b9515a9-7bab-4e98-8542-3fa179c731e5"
INVENTORY = [
    {
        "material_name": "Concrete C30/37",
        "volume_m3": 32.0,
        "density_kg_m3": 2400.0,
        "mass_kg": 76_800.0,
    }
]


def sample_lookup():
    return parse_lookup_results(LOOKUP_PATH.read_text(encoding="utf-8"))


@patch.dict("os.environ", {"VIKTOR_JS_SDK_PATH": "/sdk/"})
def test_webview_injects_worker_candidates_and_serialized_mapping_state():
    html = build_mapping_html(
        INVENTORY,
        {"Concrete C30/37": CONCRETE_ID},
        sample_lookup(),
    )

    assert 'src="/sdk/v1.js"' in html
    assert "BOOTSTRAP_BASE64" not in html
    match = re.search(r'atob\("([^"]+)"\)', html)
    assert match is not None
    bootstrap = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
    assert bootstrap["inventory"] == INVENTORY
    assert bootstrap["mappings"]["Concrete C30/37"] == CONCRETE_ID
    assert bootstrap["searches"][0]["candidates"][0]["catalog_id"] == CONCRETE_ID
    assert bootstrap["searches"][0]["candidates"][0]["dataset_name"] == "Boverket"
    assert bootstrap["source"]["dataset"] == "All installed LCA datasets"


@patch.dict("os.environ", {"VIKTOR_JS_SDK_PATH": "/sdk/"})
def test_webview_saves_mapping_and_template_json_fields():
    html = build_mapping_html(INVENTORY, {}, sample_lookup())

    assert "mapping_state_json: JSON.stringify(state)" in html
    assert "template_materials_json: JSON.stringify(buildTemplates())" in html
    assert "viktorSdk.sendParams" in html
    assert "a1toa3_kgco2e_per_declared_unit" in html
