from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import (
    ContractError,
    build_request,
    parse_json,
    validate_normalized_result,
)
from .file_io import FileReadError, read_uploaded_or_inline
from .worker_client import CACHE_VERSION, execute_worker


@dataclass(frozen=True)
class ServiceResult:
    request: dict[str, Any]
    normalized: dict[str, Any]
    artifacts: dict[str, str]


def _value(params: Any, name: str, default: Any = None) -> Any:
    if isinstance(params, dict):
        return params.get(name, default)
    return getattr(params, name, default)


def resolve_input_text(params: Any) -> tuple[str, str]:
    takeoff = read_uploaded_or_inline(
        uploaded_value=_value(params, "takeoff_file"),
        inline_value=_value(params, "takeoff_json"),
        label="a BHoM GeneralMaterialTakeoff",
    )
    templates = read_uploaded_or_inline(
        uploaded_value=_value(params, "template_materials_file"),
        inline_value=_value(params, "template_materials_json"),
        label="a BHoM material-template array",
    )
    return takeoff, templates


def run_service(params: Any, *, timeout_seconds: int = 600) -> ServiceResult:
    takeoff_json, template_json = resolve_input_text(params)

    request = build_request(
        takeoff_json=takeoff_json,
        template_materials_json=template_json,
        project_id=str(_value(params, "project_id", "") or ""),
        project_name=str(_value(params, "project_name", "") or ""),
        gross_floor_area_m2=_value(params, "gross_floor_area_m2"),
        modules=list(_value(params, "modules", []) or []),
        prioritise_template_materials=bool(
            _value(params, "prioritise_template_materials", True)
        ),
    )

    outputs = execute_worker(
        request_json=request.to_json(),
        takeoff_json=takeoff_json,
        template_materials_json=template_json,
        timeout_seconds=int(timeout_seconds),
        cache_version=CACHE_VERSION,
    )

    normalized = validate_normalized_result(
        parse_json(
            outputs["analysis-result.json"],
            label="analysis-result.json",
        )
    )
    return ServiceResult(
        request=request.to_dict(),
        normalized=normalized,
        artifacts=outputs,
    )


__all__ = [
    "ContractError",
    "FileReadError",
    "ServiceResult",
    "run_service",
]
