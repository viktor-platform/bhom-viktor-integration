import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.contracts import (
    ContractError,
    inventory_from_rows,
    inventory_from_takeoff,
    parse_mapping_state,
    validate_takeoff,
)

SAMPLE_PATH = Path(__file__).parents[1] / "samples" / "takeoff.bhom.json"


def test_revit_takeoff_builds_derived_mass_inventory():
    takeoff = validate_takeoff(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")))

    inventory = inventory_from_takeoff(takeoff)

    assert [row["material_name"] for row in inventory] == [
        "Concrete C30/37",
        "Structural Steel",
    ]
    assert inventory[0]["mass_kg"] == pytest.approx(76_800)
    assert inventory[1]["mass_kg"] == pytest.approx(3_140)


def test_table_rows_are_aggregated_by_exact_source_name():
    rows = [
        SimpleNamespace(
            material_name="Concrete C30/37",
            volume_m3=2,
            density_kg_m3=2400,
        ),
        SimpleNamespace(
            material_name="Concrete C30/37",
            volume_m3=3,
            density_kg_m3=2400,
        ),
    ]

    inventory = inventory_from_rows(rows)

    assert len(inventory) == 1
    assert inventory[0]["volume_m3"] == pytest.approx(5)
    assert inventory[0]["mass_kg"] == pytest.approx(12_000)


def test_mapping_state_rejects_unknown_schema_version():
    with pytest.raises(ContractError, match="schema_version 1.0"):
        parse_mapping_state('{"schema_version":"2.0","mappings":{}}')
