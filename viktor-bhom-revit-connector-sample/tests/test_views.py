from __future__ import annotations

import unittest
from copy import deepcopy
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import viktor as vkt

from app import Controller
from app.contracts import GatewayResult
from app.sample_loader import load_bundled_sample


def sample_params() -> SimpleNamespace:
    return SimpleNamespace(
        categories=["Walls", "Floors", "Structural Columns"],
        include_parameters=True,
        element_limit=2500,
    )


def sample_result_with_geometry() -> GatewayResult:
    result = load_bundled_sample()
    elements = deepcopy(result.elements)
    elements[0]["Location"] = {
        "_t": "BH.oM.Geometry.Line",
        "Start": {"_t": "BH.oM.Geometry.Point", "X": 0, "Y": 0, "Z": 0},
        "End": {"_t": "BH.oM.Geometry.Point", "X": 5, "Y": 0, "Z": 3},
    }
    return GatewayResult(
        metadata=result.metadata,
        elements=elements,
        takeoff=result.takeoff,
        artifacts=result.artifacts,
    )


def call_view(controller: Controller, name: str, params: Any) -> Any:
    """Call the registered view function without VIKTOR platform context."""
    decorated_method = Controller.__dict__[name]
    view = decorated_method.__self__
    return view._view_function(controller, params=params)


class TestViews(unittest.TestCase):
    def setUp(self) -> None:
        self.pull_patcher = patch(
            "app.app.pull_model",
            return_value=sample_result_with_geometry(),
        )
        self.pull_patcher.start()
        self.addCleanup(self.pull_patcher.stop)

    def test_requested_views_return_expected_results(self) -> None:
        controller = Controller()
        params = sample_params()

        geometry = call_view(controller, "geometry_view", params)
        lca_data = call_view(controller, "lca_data_view", params)
        metadata = call_view(controller, "metadata_view", params)
        contract = call_view(controller, "bhom_contract_view", params)

        self.assertIsInstance(geometry, vkt.GeometryResult)
        self.assertIsInstance(lca_data, vkt.DataResult)
        self.assertIsInstance(metadata, vkt.DataResult)
        self.assertIsInstance(contract, vkt.DataResult)


if __name__ == "__main__":
    unittest.main()
