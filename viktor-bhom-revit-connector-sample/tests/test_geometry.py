from __future__ import annotations

import pytest

from app.contracts import GatewayResult
from app.geometry import build_geometry, geometry_segments, gross_floor_area_m2


def _surface() -> dict[str, object]:
    points = [
        {"_t": "BH.oM.Geometry.Point", "X": 0, "Y": 0, "Z": 0},
        {"_t": "BH.oM.Geometry.Point", "X": 4, "Y": 0, "Z": 0},
        {"_t": "BH.oM.Geometry.Point", "X": 4, "Y": 3, "Z": 0},
        {"_t": "BH.oM.Geometry.Point", "X": 0, "Y": 3, "Z": 0},
        {"_t": "BH.oM.Geometry.Point", "X": 0, "Y": 0, "Z": 0},
    ]
    return {
        "_t": "BH.oM.Geometry.PlanarSurface",
        "ExternalBoundary": {
            "_t": "BH.oM.Geometry.Polyline",
            "ControlPoints": points,
        },
        "InternalBoundaries": [],
    }


def _result() -> GatewayResult:
    return GatewayResult(
        metadata={},
        elements=[
            {
                "_t": "BH.oM.Physical.Elements.Floor",
                "BHoM_Guid": "floor-guid",
                "Name": "Floor",
                "Location": _surface(),
            }
        ],
        takeoff={},
        artifacts={},
    )


def test_planar_surface_contract_becomes_four_edges() -> None:
    assert len(geometry_segments(_surface())) == 4
    assert len(build_geometry(_result())) == 4


def test_floor_area_is_derived_from_bhom_surface() -> None:
    assert gross_floor_area_m2(_result()) == pytest.approx(12.0)
