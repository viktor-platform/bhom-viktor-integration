from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Final

SCHEMA_VERSION: Final[str] = "1.0"
ALLOWED_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "Walls",
        "Floors",
        "Structural Columns",
        "Structural Framing",
        "Roofs",
    }
)
ALLOWED_MODULES: Final[frozenset[str]] = frozenset({"A1", "A2", "A3", "A1toA3"})


class ContractError(ValueError):
    """Raised when a producer/gateway contract is invalid."""


@dataclass(frozen=True)
class PullRequest:
    payload: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(self.payload, indent=2, ensure_ascii=False)


@dataclass(frozen=True)
class GatewayResult:
    metadata: dict[str, Any]
    elements: list[dict[str, Any]]
    takeoff: dict[str, Any]
    artifacts: dict[str, str]


def build_pull_request(
    *,
    document_name: str,
    categories: list[str],
    include_parameters: bool,
    element_limit: int,
) -> PullRequest:
    clean_document_name = document_name.strip()
    clean_categories = sorted(set(categories))
    unknown = set(clean_categories) - ALLOWED_CATEGORIES
    if unknown:
        raise ContractError(
            f"Unsupported Revit categories: {', '.join(sorted(unknown))}"
        )
    if not clean_categories:
        raise ContractError("Select at least one Revit category.")
    if not 1 <= element_limit <= 10000:
        raise ContractError("Maximum elements must be between 1 and 10,000.")

    identity = json.dumps(
        [clean_document_name, clean_categories, include_parameters, element_limit]
    )
    job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"viktor-bhom-revit:{identity}"))
    return PullRequest(
        {
            "schema_version": SCHEMA_VERSION,
            "job_id": job_id,
            "operation": "pull_model_snapshot",
            "revit_version": "2025",
            "expected_document_name": clean_document_name or None,
            "filters": {"categories": clean_categories},
            "options": {
                "include_parameters": include_parameters,
                "include_material_takeoff": True,
                "include_geometry": False,
                "element_limit": element_limit,
            },
        }
    )


def parse_json(text: str, *, label: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ContractError(f"{label} is not valid JSON: {error.msg}") from error


def validate_gateway_outputs(outputs: dict[str, str]) -> GatewayResult:
    metadata = parse_json(outputs["revit-metadata.json"], label="revit-metadata.json")
    elements = parse_json(
        outputs["revit-elements.bhom.json"], label="revit-elements.bhom.json"
    )
    takeoff = parse_json(outputs["takeoff.bhom.json"], label="takeoff.bhom.json")

    if (
        not isinstance(metadata, dict)
        or metadata.get("schema_version") != SCHEMA_VERSION
    ):
        raise ContractError("revit-metadata.json must use schema_version 1.0.")
    if not isinstance(metadata.get("elements"), list):
        raise ContractError("revit-metadata.json must contain an elements array.")
    if not isinstance(elements, list):
        raise ContractError("revit-elements.bhom.json must be a BHoM JSON array.")
    if takeoff.get("_t") != "BH.oM.Physical.Materials.GeneralMaterialTakeoff":
        raise ContractError("takeoff.bhom.json must be a GeneralMaterialTakeoff.")
    if not isinstance(takeoff.get("MaterialTakeoffItems"), list):
        raise ContractError("GeneralMaterialTakeoff requires MaterialTakeoffItems.")

    return GatewayResult(
        metadata=metadata,
        elements=elements,
        takeoff=takeoff,
        artifacts=outputs,
    )


def validate_modules(modules: list[str]) -> list[str]:
    clean_modules = list(dict.fromkeys(modules))
    unknown = set(clean_modules) - ALLOWED_MODULES
    if unknown:
        raise ContractError(f"Unsupported LCA modules: {', '.join(sorted(unknown))}")
    if not clean_modules:
        raise ContractError("Select at least one LCA module.")
    if "A1toA3" in clean_modules and set(clean_modules) & {"A1", "A2", "A3"}:
        raise ContractError("A1toA3 cannot be combined with A1, A2, or A3.")
    return clean_modules
