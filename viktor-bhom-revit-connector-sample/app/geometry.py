from __future__ import annotations

from collections.abc import Iterable
from math import sqrt
from typing import Any

import viktor as vkt

from .contracts import GatewayResult

Point3D = tuple[float, float, float]
Segment = tuple[Point3D, Point3D]

TYPE_COLORS = {
    "BH.oM.Physical.Elements.Wall": vkt.Color(55, 118, 171),
    "BH.oM.Physical.Elements.Floor": vkt.Color(76, 175, 80),
    "BH.oM.Physical.Elements.Column": vkt.Color(245, 166, 35),
}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        wrapped = value.get("_v")
        if isinstance(wrapped, list):
            return wrapped
    return []


def _point(value: Any) -> Point3D | None:
    if not isinstance(value, dict):
        return None
    try:
        return (
            float(value["X"]),
            float(value["Y"]),
            float(value.get("Z", 0.0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def geometry_segments(value: Any) -> list[Segment]:
    """Extract renderable line segments from supported BHoM geometry contracts."""
    if not isinstance(value, dict):
        return []

    geometry_type = str(value.get("_t", ""))
    if geometry_type == "BH.oM.Geometry.Line":
        start = _point(value.get("Start"))
        end = _point(value.get("End"))
        if start is not None and end is not None and start != end:
            return [(start, end)]
        return []

    if geometry_type in {
        "BH.oM.Geometry.Polyline",
        "BH.oM.Geometry.NurbsCurve",
    }:
        points = [
            point
            for item in _sequence(value.get("ControlPoints"))
            if (point := _point(item)) is not None
        ]
        return [
            (start, end)
            for start, end in zip(points, points[1:], strict=False)
            if start != end
        ]

    if geometry_type == "BH.oM.Geometry.PolyCurve":
        return [
            segment
            for curve in _sequence(value.get("Curves"))
            for segment in geometry_segments(curve)
        ]

    if geometry_type == "BH.oM.Geometry.PlanarSurface":
        boundaries: list[Any] = [value.get("ExternalBoundary")]
        boundaries.extend(_sequence(value.get("InternalBoundaries")))
        return [
            segment
            for boundary in boundaries
            for segment in geometry_segments(boundary)
        ]

    return []


def _identifier(element: dict[str, Any], index: int) -> str:
    name = str(element.get("Name") or element.get("_t") or "BHoM element")
    guid = str(element.get("BHoM_Guid") or index)
    return f"{name} · {guid}"


def build_geometry(result: GatewayResult) -> list[vkt.Line]:
    lines: list[vkt.Line] = []
    for element_index, element in enumerate(result.elements):
        element_type = str(element.get("_t", ""))
        color = TYPE_COLORS.get(element_type, vkt.Color(110, 110, 110))
        identifier = _identifier(element, element_index)
        for segment_index, (start, end) in enumerate(
            geometry_segments(element.get("Location"))
        ):
            lines.append(
                vkt.Line(
                    start,
                    end,
                    color=color,
                    identifier=f"{identifier} · edge {segment_index + 1}",
                )
            )
    return lines


def _polygon_area(points: Iterable[Point3D]) -> float:
    vertices = list(points)
    if len(vertices) < 3:
        return 0.0

    x = y = z = 0.0
    for current, following in zip(vertices, vertices[1:] + vertices[:1], strict=True):
        x += (current[1] - following[1]) * (current[2] + following[2])
        y += (current[2] - following[2]) * (current[0] + following[0])
        z += (current[0] - following[0]) * (current[1] + following[1])
    return 0.5 * sqrt(x * x + y * y + z * z)


def gross_floor_area_m2(result: GatewayResult) -> float:
    """Derive floor area from BHoM floor surface boundaries."""
    total = 0.0
    for element in result.elements:
        if element.get("_t") != "BH.oM.Physical.Elements.Floor":
            continue
        location = element.get("Location")
        if not isinstance(location, dict):
            continue
        segments = geometry_segments(location.get("ExternalBoundary"))
        if segments:
            total += _polygon_area(start for start, _ in segments)
    return total
