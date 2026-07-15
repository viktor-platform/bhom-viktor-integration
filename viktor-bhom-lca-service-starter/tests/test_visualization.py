from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.visualization import (
    aggregate_records,
    build_figure,
    records_to_dataframe,
)

SAMPLE = (
    Path(__file__).resolve().parents[1] / "samples" / "normalized-result.sample.json"
)


def load_result() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_material_aggregation_matches_total() -> None:
    frame = aggregate_records(load_result(), group_by="Material")
    assert frame["value"].sum() == pytest.approx(19365.0)
    assert set(frame["group"]) == {"Concrete C30/37", "Structural Steel"}


@pytest.mark.parametrize("chart_type", ["Bar", "Stacked bar", "Treemap", "Sunburst"])
def test_each_chart_type_returns_figure(chart_type: str) -> None:
    figure = build_figure(load_result(), chart_type=chart_type, group_by="Material")
    assert len(figure.data) >= 1


def test_empty_records_return_empty_dataframe() -> None:
    frame = records_to_dataframe({"records": []})
    assert frame.empty


def test_unknown_group_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported grouping"):
        aggregate_records(load_result(), group_by="Category")
