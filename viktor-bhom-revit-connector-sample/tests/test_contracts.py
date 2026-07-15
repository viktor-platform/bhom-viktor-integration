from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from app.contracts import build_pull_request

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> object:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_pull_request_matches_local_schema() -> None:
    request = build_pull_request(
        document_name="Sample Office 2025.rvt",
        categories=["Walls", "Floors"],
        include_parameters=True,
        element_limit=2500,
    ).payload
    schema = load_json("app/schemas/revit-pull-request.schema.json")

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(request)
    assert request["operation"] == "pull_model_snapshot"
    assert request["revit_version"] == "2025"
    assert request["options"]["include_material_takeoff"] is True
    assert request["options"]["include_geometry"] is False


def test_metadata_fixture_matches_local_schema() -> None:
    metadata = load_json("samples/revit-metadata.json")
    schema = load_json("app/schemas/revit-metadata.schema.json")

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(metadata)
