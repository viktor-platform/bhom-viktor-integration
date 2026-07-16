import base64
import json
import re
from pathlib import Path
from unittest.mock import patch

from app.catalog import parse_lookup_results
from app.webview import build_mapping_html

LOOKUP_PATH = Path(__file__).parents[1] / "samples" / "lookup-result.sample.json"
CONCRETE_ID = "7b9515a9-7bab-4e98-8542-3fa179c731e5"
STEEL_ID = "a372a265-fd6e-4445-9c03-29ac36e25682"
INVENTORY = [
    {
        "material_name": "Concrete C30/37",
        "volume_m3": 32.0,
        "density_kg_m3": 2400.0,
        "mass_kg": 76_800.0,
    },
    {
        "material_name": "Structural Steel [S355]",
        "volume_m3": 0.4,
        "density_kg_m3": 7850.0,
        "mass_kg": 3140.0,
    },
]


def sample_lookup():
    return parse_lookup_results(LOOKUP_PATH.read_text(encoding="utf-8"))


@patch.dict("os.environ", {"VIKTOR_JS_SDK_PATH": "/sdk/"})
def test_webview_injects_worker_candidates_and_serialized_mapping_state():
    html = build_mapping_html(
        INVENTORY,
        {
            "Concrete C30/37": CONCRETE_ID,
            "Structural Steel [S355]": STEEL_ID,
        },
        sample_lookup(),
    )

    assert 'src="/sdk/v1.js"' in html
    assert "BOOTSTRAP_BASE64" not in html
    match = re.search(r'atob\("([^"]+)"\)', html)
    assert match is not None
    bootstrap = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
    assert bootstrap["inventory"] == INVENTORY
    assert bootstrap["mappings"] == {
        "Concrete C30/37": CONCRETE_ID,
        "Structural Steel [S355]": STEEL_ID,
    }
    assert bootstrap["searches"][0]["candidates"][0]["catalog_id"] == CONCRETE_ID
    assert bootstrap["searches"][0]["candidates"][0]["dataset_name"] == "Boverket"
    assert bootstrap["source"]["dataset"] == "All installed LCA datasets"


@patch.dict("os.environ", {"VIKTOR_JS_SDK_PATH": "/sdk/"})
def test_webview_palette_is_grayscale_with_accessible_black_controls():
    html = build_mapping_html(INVENTORY, {}, sample_lookup())
    style_match = re.search(r"<style>(.*?)</style>", html, re.DOTALL)

    assert style_match is not None
    styles = style_match.group(1).lower()
    forbidden_tokens = (
        "--accent",
        "--warning",
        "--success",
        "--danger",
        "--error",
        ".green",
        ".yellow",
        ".warning",
        ".success",
        ".failure",
        ".error",
        "#176b5b",
        "#e5f2ee",
        "#9a6200",
        "#fff3d6",
    )
    assert not any(token in styles for token in forbidden_tokens)
    forbidden_named_colors = re.compile(
        r"\b(?:aqua|blue|brown|cyan|fuchsia|gold|green|lime|magenta|maroon|navy|"
        r"olive|orange|pink|purple|red|teal|violet|yellow)\b"
    )
    assert forbidden_named_colors.search(styles) is None

    for color in re.findall(r"#[0-9a-f]{3,8}\b", styles):
        digits = color[1:]
        channels = (
            list(digits[:3])
            if len(digits) in (3, 4)
            else [digits[0:2], digits[2:4], digits[4:6]]
        )
        assert len(set(channels)) == 1, f"{color} is not grayscale"

    for components in re.findall(r"rgba?\(([^)]*)\)", styles):
        channels = [part.strip() for part in components.split(",")[:3]]
        assert len(channels) == 3
        assert len(set(channels)) == 1, f"rgb({components}) is not grayscale"
    assert "hsl(" not in styles
    assert "hsla(" not in styles

    assert "--panel: #ffffff;" in styles
    assert "--canvas: #ffffff;" in styles
    assert ".actions button.primary { background: #000000;" in styles
    assert (
        ".actions button.primary:hover:not(:disabled) { background: #333333;" in styles
    )
    assert ".actions button.primary:disabled { background: #666666;" in styles
    assert "accent-color: #000000;" in styles
    assert "outline: 2px solid #000000;" in styles


@patch.dict("os.environ", {"VIKTOR_JS_SDK_PATH": "/sdk/"})
def test_webview_selection_updates_mapping_without_approval_action():
    html = build_mapping_html(INVENTORY, {}, sample_lookup())

    assert "Approve selection" not in html
    assert "approveSelection" not in html
    assert 'id="approve-button"' not in html
    assert "selectedCatalogId" not in html
    assert "mappings[radio.dataset.sourceMaterial] = radio.dataset.catalogId;" in html
    assert "radio.onchange = function () {" in html
    assert "markDirty();" in html
    assert "delete mappings[row.material_name];" in html
    assert '"Unsaved changes."' in html


@patch.dict("os.environ", {"VIKTOR_JS_SDK_PATH": "/sdk/"})
def test_webview_saved_selection_renders_checked_with_dom_safe_data():
    html = build_mapping_html(
        INVENTORY,
        {"Concrete C30/37": CONCRETE_ID},
        sample_lookup(),
    )

    assert "radio.dataset.sourceMaterial = row.material_name;" in html
    assert "radio.dataset.catalogId = record.catalog_id;" in html
    assert "radio.checked = mappings[row.material_name] === record.catalog_id;" in html
    assert "[data-source-material][data-catalog-id]:checked" in html


@patch.dict("os.environ", {"VIKTOR_JS_SDK_PATH": "/sdk/"})
def test_webview_save_synchronizes_checked_radios_before_serialization():
    html = build_mapping_html(INVENTORY, {}, sample_lookup())
    save_start = html.index("async function saveSelections()")
    synchronize = html.index("synchronizeCheckedMappings();", save_start)
    serialize = html.index(
        'const state = {schema_version: "1.0", mappings: mappings};',
        save_start,
    )
    send = html.index(
        "await viktorSdk.sendParams("
        "{mapping_state_json: JSON.stringify(state)}, true);",
        save_start,
    )

    assert synchronize < serialize < send
    assert ".forEach(function (radio) {" in html
    assert "mappings[sourceMaterial] = catalogId;" in html
    assert "template_materials_json" not in html


@patch.dict("os.environ", {"VIKTOR_JS_SDK_PATH": "/sdk/"})
def test_webview_save_awaits_feedback_and_disables_only_while_saving():
    html = build_mapping_html(INVENTORY, {}, sample_lookup())

    assert ">Save selections</button>" in html
    assert "async function saveSelections()" in html
    assert "button.disabled = true;" in html
    assert "button.disabled = false;" in html
    assert '"Saving…";' in html
    assert '"Selections saved."' in html
    assert '"Save failed: "' in html
    assert "a1toa3_kgco2e_per_declared_unit" in html
