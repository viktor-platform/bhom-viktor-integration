from __future__ import annotations

import json
from pathlib import Path

import pytest

from revit_connector.bhom_formatter import build_lca_handoff, summarize_snapshot
from revit_connector.contracts import ContractError
from revit_connector.sample_loader import load_bundled_sample

ROOT = Path(__file__).resolve().parents[1]


def test_sample_is_lca_ready_general_material_takeoff() -> None:
    result = load_bundled_sample()
    summary = summarize_snapshot(result)

    assert result.takeoff["_t"] == "BH.oM.Physical.Materials.GeneralMaterialTakeoff"
    assert summary["element_count"] == 4
    assert summary["material_count"] == 2
    assert summary["total_volume_m3"] == pytest.approx(32.4)
    assert summary["total_mass_kg"] == pytest.approx(79940.0)


def test_lca_handoff_matches_carbon_analysis_parameter_names() -> None:
    result = load_bundled_sample()
    templates = (ROOT / "samples/template-materials.bhom.json").read_text(
        encoding="utf-8"
    )

    handoff = build_lca_handoff(
        result=result,
        project_id="sample-office-revit-2025",
        project_name="Sample Office — Revit 2025",
        gross_floor_area_m2=500.0,
        modules=["A1", "A2", "A3"],
        template_materials_json=templates,
    )

    assert handoff["target"] == {
        "app": "bhom-lca-carbon-analysis",
        "method_name": "run_analysis",
    }
    assert set(handoff["params"]) == {
        "project_id",
        "project_name",
        "gross_floor_area_m2",
        "modules",
        "prioritise_template_materials",
        "takeoff_json",
        "template_materials_json",
        "chart_type",
        "group_by",
    }
    assert json.loads(handoff["params"]["takeoff_json"])["_t"].endswith(
        "GeneralMaterialTakeoff"
    )


def test_combined_module_cannot_overlap_individual_modules() -> None:
    result = load_bundled_sample()
    templates = (ROOT / "samples/template-materials.bhom.json").read_text(
        encoding="utf-8"
    )

    with pytest.raises(ContractError, match="cannot be combined"):
        build_lca_handoff(
            result=result,
            project_id="sample",
            project_name="Sample",
            gross_floor_area_m2=500.0,
            modules=["A1", "A1toA3"],
            template_materials_json=templates,
        )
