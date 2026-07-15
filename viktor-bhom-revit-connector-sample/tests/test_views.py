from __future__ import annotations

from types import SimpleNamespace

import viktor as vkt
from viktor.testing import mock_View

from revit_connector.controller import Controller


def sample_params() -> SimpleNamespace:
    return SimpleNamespace(
        source=SimpleNamespace(
            connection_mode="Bundled sample",
            document_name="Sample Office 2025.rvt",
            categories=["Walls", "Floors", "Structural Columns"],
            include_parameters=True,
            element_limit=2500,
        ),
        project=SimpleNamespace(
            project_id="sample-office-revit-2025",
            project_name="Sample Office — Revit 2025",
            gross_floor_area_m2=500.0,
            template_materials_file=None,
            modules=["A1", "A2", "A3"],
        ),
    )


@mock_View(Controller)
def test_webview_contains_model_audit_and_bhom_payload() -> None:
    result = Controller().model_explorer(params=sample_params())

    assert isinstance(result, vkt.WebResult)
    assert "BHoM model audit" in result.html
    assert "BH.oM.Physical.Elements.Wall" not in result.html
    assert "MODEL_DATA_BASE64" not in result.html


@mock_View(Controller)
def test_metadata_view_returns_data_result() -> None:
    result = Controller().metadata_view(params=sample_params())

    assert isinstance(result, vkt.DataResult)


def test_lca_handoff_download_is_available() -> None:
    result = Controller().download_lca_handoff(params=sample_params())

    assert isinstance(result, vkt.DownloadResult)
