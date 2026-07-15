from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def load(name: str):
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def factor_by_material() -> dict[str, dict[str, float]]:
    templates = load("template-materials.bhom.json")
    factors: dict[str, dict[str, float]] = {}
    for material in templates:
        epd = next(
            value
            for value in material["Properties"]
            if value["_t"].endswith("EnvironmentalProductDeclaration")
        )
        metric = next(
            value
            for value in epd["EnvironmentalMetrics"]
            if value["_t"].endswith("ClimateChangeTotalMetric")
        )
        factors[material["Name"]] = metric
    return factors


def test_fixed_sample_arithmetic() -> None:
    request = load("analysis-request.json")
    takeoff = load("takeoff.bhom.json")
    factors = factor_by_material()

    records = []
    for item in takeoff["MaterialTakeoffItems"]:
        material_name = item["Material"]["Name"]
        mass = item["Mass"]
        for module in request["modules"]:
            records.append(mass * factors[material_name][module])

    total = sum(records)
    assert total == pytest.approx(19365.0)
    assert total / 1000.0 == pytest.approx(19.365)
    assert total / request["project"]["gross_floor_area_m2"] == pytest.approx(38.73)
    assert len(records) == 6


def test_checked_in_normalized_sample_matches_arithmetic() -> None:
    result = load("normalized-result.sample.json")
    assert result["summary"]["total_kgco2e"] == pytest.approx(19365.0)
    assert sum(record["value"] for record in result["records"]) == pytest.approx(
        19365.0
    )
