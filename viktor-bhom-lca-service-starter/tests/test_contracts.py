from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.contracts import (
    AnalysisRequest,
    ContractError,
    build_request,
    validate_bhom_takeoff,
    validate_module_selection,
    validate_normalized_result,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def sample_text(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")


def sample_request(*, gross_floor_area_m2: float = 500.0) -> AnalysisRequest:
    return build_request(
        takeoff_json=sample_text("takeoff.bhom.json"),
        template_materials_json=sample_text("template-materials.bhom.json"),
        project_id="sample-office",
        project_name="Sample Office",
        gross_floor_area_m2=gross_floor_area_m2,
        modules=["A1", "A2", "A3"],
        prioritise_template_materials=True,
    )


def test_build_request_from_samples() -> None:
    request = build_request(
        takeoff_json=sample_text("takeoff.bhom.json"),
        template_materials_json=sample_text("template-materials.bhom.json"),
        project_id="sample-office",
        project_name="Sample Office",
        gross_floor_area_m2=500.0,
        modules=["A1", "A2", "A3"],
        prioritise_template_materials=True,
    )
    assert request.analysis_profile == "general_environmental_results"
    assert request.modules == ("A1", "A2", "A3")
    assert request.metric_filters == ("ClimateChangeTotal",)
    assert request.takeoff_filename == "takeoff.bhom.json"


def test_stable_request_job_id() -> None:
    request = sample_request()
    assert request.job_id == "e2bb16f4-bb1c-57b6-9beb-36efb1c58be6"
    assert request.job_id == sample_request().job_id


def test_job_id_changes_with_analysis_input() -> None:
    first = sample_request()
    second = sample_request(gross_floor_area_m2=750.0)
    assert first.job_id != second.job_id


def test_rejects_overlapping_module_total() -> None:
    with pytest.raises(ContractError, match="cannot be selected"):
        validate_module_selection(["A1", "A1toA3"])


def test_rejects_wrong_takeoff_type() -> None:
    value = json.loads(sample_text("takeoff.bhom.json"))
    value["_t"] = "BH.oM.Physical.Materials.Material"
    with pytest.raises(ContractError, match="takeoff _t"):
        validate_bhom_takeoff(value)


def test_normalized_sample_meets_service_schema() -> None:
    value = json.loads(sample_text("normalized-result.sample.json"))
    assert validate_normalized_result(value)["status"] == "completed"
