import json
from pathlib import Path

import pytest

from app.catalog import (
    build_template_materials,
    candidates_for_material,
    catalogue_source,
    climate_change_a1toa3,
    parse_lookup_results,
)
from app.contracts import ContractError

SAMPLE_PATH = Path(__file__).parents[1] / "samples" / "lookup-result.sample.json"
CONCRETE_ID = "7b9515a9-7bab-4e98-8542-3fa179c731e5"


def sample_lookup():
    return parse_lookup_results(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_worker_result_exposes_installed_bhom_source_and_typed_epds():
    lookup = sample_lookup()
    source = catalogue_source(lookup)
    concrete = candidates_for_material(lookup, "Concrete C30/37")[0]

    assert source["dataset"] == "All installed LCA datasets"
    assert source["toolkit"] == "BHoM Library_Engine"
    assert source["library_path"] == "LifeCycleAssessment"
    assert source["epd_count"] == 2273
    assert concrete["catalog_id"] == CONCRETE_ID
    assert concrete["dataset_name"] == "Boverket"
    assert concrete["epd"]["_t"].endswith(".EnvironmentalProductDeclaration")
    assert climate_change_a1toa3(concrete) == pytest.approx(0.1446)


def test_template_preserves_exact_source_name_and_attaches_worker_epd():
    inventory = [
        {
            "material_name": "Concrete C30/37",
            "volume_m3": 10.0,
            "density_kg_m3": 2400.0,
            "mass_kg": 24_000.0,
        }
    ]

    templates = build_template_materials(
        inventory,
        {"Concrete C30/37": CONCRETE_ID},
        sample_lookup(),
    )

    assert templates[0]["Name"] == "Concrete C30/37"
    assert templates[0]["Density"] == pytest.approx(2400)
    assert templates[0]["Properties"][0]["Name"].startswith("Ready-mix made")


def test_empty_lookup_represents_not_searched_state():
    lookup = parse_lookup_results("")

    assert lookup["status"] == "not_searched"
    assert lookup["source"]["toolkit"] == "BHoM Library_Engine"
    assert lookup["searches"] == []


def test_invalid_worker_epd_json_is_rejected():
    payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    payload["searches"][0]["candidates"][0]["epd_json"] = "{broken"

    with pytest.raises(ContractError, match="invalid EPD JSON"):
        parse_lookup_results(json.dumps(payload))


def test_mapping_to_absent_worker_result_is_rejected():
    inventory = [
        {
            "material_name": "Unknown",
            "volume_m3": 1.0,
            "density_kg_m3": 1000.0,
            "mass_kg": 1000.0,
        }
    ]

    with pytest.raises(ContractError, match="not present"):
        build_template_materials(
            inventory,
            {"Unknown": "missing-id"},
            sample_lookup(),
        )
