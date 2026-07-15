from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

RECORD_COLUMNS = [
    "material",
    "environmental_product_declaration",
    "metric",
    "module",
    "value",
    "unit",
]

GROUP_COLUMNS = {
    "Material": "material",
    "EPD": "environmental_product_declaration",
    "Module": "module",
}


def records_to_dataframe(result: dict[str, Any]) -> pd.DataFrame:
    records = result.get("records", [])
    if not isinstance(records, list):
        raise ValueError("The result records value must be an array.")

    frame = pd.DataFrame(records)
    for column in RECORD_COLUMNS:
        if column not in frame.columns:
            frame[column] = None

    if not frame.empty:
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        frame = frame.dropna(subset=["value"])
    return frame


def aggregate_records(
    result: dict[str, Any],
    *,
    group_by: str,
) -> pd.DataFrame:
    frame = records_to_dataframe(result)
    if frame.empty:
        return pd.DataFrame(
            {
                "group": pd.Series(dtype="object"),
                "module": pd.Series(dtype="object"),
                "value": pd.Series(dtype="float64"),
                "unit": pd.Series(dtype="object"),
            }
        )

    group_column = GROUP_COLUMNS.get(group_by)
    if group_column is None:
        raise ValueError(
            f"Unsupported grouping '{group_by}'. "
            f"Choose one of: {', '.join(GROUP_COLUMNS)}."
        )

    frame[group_column] = frame[group_column].fillna("Unspecified")
    frame["module"] = frame["module"].fillna("Unspecified")
    frame["unit"] = frame["unit"].fillna("")
    grouped = (
        frame.groupby([group_column, "module", "unit"], dropna=False)["value"]
        .sum()
        .reset_index()
        .rename(columns={group_column: "group"})
    )
    return grouped


def _empty_figure(message: str) -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
    )
    figure.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return figure


def build_figure(
    result: dict[str, Any],
    *,
    chart_type: str,
    group_by: str,
) -> go.Figure:
    frame = aggregate_records(result, group_by=group_by)
    if frame.empty:
        return _empty_figure("No calculated records are available.")

    unit_values = [value for value in frame["unit"].dropna().unique() if value]
    unit = unit_values[0] if len(unit_values) == 1 else "result units"

    if chart_type == "Bar":
        totals = (
            frame.groupby("group", dropna=False)["value"]
            .sum()
            .reset_index()
            .sort_values("value", ascending=False)
        )
        figure = px.bar(
            totals,
            x="group",
            y="value",
            labels={"group": group_by, "value": unit},
        )
    elif chart_type == "Stacked bar":
        figure = px.bar(
            frame,
            x="group",
            y="value",
            color="module",
            barmode="stack",
            labels={
                "group": group_by,
                "value": unit,
                "module": "Module",
            },
        )
    elif chart_type == "Treemap":
        figure = px.treemap(
            frame,
            path=["group", "module"],
            values="value",
        )
    elif chart_type == "Sunburst":
        figure = px.sunburst(
            frame,
            path=["group", "module"],
            values="value",
        )
    else:
        raise ValueError(
            "Unsupported chart type. Choose Bar, Stacked bar, Treemap or Sunburst."
        )

    figure.update_layout(
        title=f"Life-cycle assessment by {group_by.lower()}",
    )
    return figure
