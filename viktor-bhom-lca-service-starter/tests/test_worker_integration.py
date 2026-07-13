from __future__ import annotations

import json
import unittest
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import viktor as vkt
from viktor.testing import mock_GenericAnalysis

from lca_service.controller import Controller
from lca_service.worker_client import CACHE_VERSION, execute_worker

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def sample_text(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")


def output_bytes(text: str) -> BytesIO:
    return BytesIO(text.encode("utf-8"))


def mocked_outputs() -> dict[
    str,
    Sequence[BytesIO | vkt.File] | BytesIO | vkt.File,
]:
    return {
        "analysis-result.json": output_bytes(
            sample_text("normalized-result.sample.json")
        ),
        "bhom-results.json": output_bytes("[]"),
        "analysis-events.json": output_bytes(
            json.dumps({"schema_version": "1.0", "job_id": None, "events": []})
        ),
        "runtime-manifest.json": output_bytes(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "generated_at_utc": "2026-07-13T00:00:00Z",
                    "gateway_version": "test",
                    "dotnet_version": "8.0.0",
                    "operating_system": "test",
                    "assemblies": [],
                }
            )
        ),
    }


def sample_params() -> SimpleNamespace:
    return SimpleNamespace(
        project_id="sample-office",
        project_name="Sample Office",
        gross_floor_area_m2=500.0,
        takeoff_file=None,
        template_materials_file=None,
        takeoff_json=sample_text("takeoff.bhom.json"),
        template_materials_json=sample_text("template-materials.bhom.json"),
        prioritise_template_materials=True,
        modules=["A1", "A2", "A3"],
        chart_type="Stacked bar",
        group_by="Material",
    )


class TestGenericWorkerBoundary(unittest.TestCase):
    @mock_GenericAnalysis(get_output_file=mocked_outputs())
    def test_execute_worker_collects_all_declared_json_outputs(self) -> None:
        outputs = execute_worker(
            request_json=sample_text("analysis-request.json"),
            takeoff_json=sample_text("takeoff.bhom.json"),
            template_materials_json=sample_text("template-materials.bhom.json"),
            timeout_seconds=600,
            cache_version=CACHE_VERSION,
        )

        self.assertEqual(
            set(outputs),
            {
                "analysis-result.json",
                "bhom-results.json",
                "analysis-events.json",
                "runtime-manifest.json",
            },
        )
        self.assertEqual(
            json.loads(outputs["analysis-result.json"])["summary"]["total_kgco2e"],
            19365.0,
        )

    @mock_GenericAnalysis(get_output_file=mocked_outputs())
    def test_controller_button_returns_normalized_download(self) -> None:
        result = Controller().run_analysis(params=sample_params())

        self.assertIsInstance(result, vkt.DownloadResult)


if __name__ == "__main__":
    unittest.main()
