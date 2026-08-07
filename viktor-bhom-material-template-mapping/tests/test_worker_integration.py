from __future__ import annotations

import json
import unittest
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import viktor as vkt
from viktor.testing import mock_GenericAnalysis

from app import Controller
from app.worker_client import CACHE_VERSION, execute_worker

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
        "lookup-result.json": output_bytes(sample_text("lookup-result.sample.json")),
        "lookup-events.json": output_bytes(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "job_id": "11111111-1111-1111-1111-111111111111",
                    "events": [],
                }
            )
        ),
        "runtime-manifest.json": output_bytes(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "generated_at_utc": "2026-07-15T00:00:00Z",
                    "gateway_version": "test",
                    "dotnet_version": "8.0.0",
                    "operating_system": "Windows",
                    "dataset_root": (
                        "C:\\ProgramData\\BHoM\\Datasets\\LifeCycleAssessment"
                    ),
                    "dataset_files": 81,
                    "assemblies": ["Library_Engine:9.0.0.0"],
                }
            )
        ),
    }


def sample_params() -> SimpleNamespace:
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
            )
        ],
        lookup_results_json="",
        mapping_state_json='{"schema_version":"1.0","mappings":{}}',
        template_materials_json="[]",
        gross_floor_area_m2=1000.0,
    )


class TestGenericWorkerBoundary(unittest.TestCase):
    @mock_GenericAnalysis(get_output_file=mocked_outputs())
    def test_execute_worker_collects_declared_json_outputs(self) -> None:
        outputs = execute_worker(
            request_json=sample_text("lookup-request.json"),
            timeout_seconds=180,
            cache_version=CACHE_VERSION,
        )

        self.assertEqual(
            set(outputs),
            {
                "lookup-result.json",
                "lookup-events.json",
                "runtime-manifest.json",
            },
        )
        self.assertEqual(
            json.loads(outputs["lookup-result.json"])["status"],
            "completed",
        )

    @mock_GenericAnalysis(get_output_file=mocked_outputs())
    def test_search_action_populates_hidden_worker_result_param(self) -> None:
        result = Controller().search_bhom_database(params=sample_params())

        self.assertIsInstance(result, vkt.SetParamsResult)


if __name__ == "__main__":
    unittest.main()
