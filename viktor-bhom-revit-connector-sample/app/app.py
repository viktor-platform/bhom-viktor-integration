from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import viktor as vkt

from .bhom_formatter import (
    build_lca_handoff,
    summarize_bhom_contract,
    summarize_snapshot,
)
from .contracts import ContractError, GatewayResult, build_pull_request
from .gateway_client import pull_model
from .parametrization import Parametrization
from .webview import build_model_explorer

ROOT = Path(__file__).resolve().parents[1]


def _section_value(params: Any, section: str, name: str, default: Any = None) -> Any:
    if isinstance(params, dict):
        parent = params.get(section, {})
    else:
        parent = getattr(params, section, None)
    if isinstance(parent, dict):
        return parent.get(name, default)
    return getattr(parent, name, default)


def _uploaded_text(value: Any) -> str | None:
    if value is None:
        return None
    getter = getattr(value, "getvalue", None)
    if callable(getter):
        content = getter()
    else:
        reader = getattr(value, "read", None)
        if not callable(reader):
            raise ContractError("Could not read the uploaded template-material file.")
        content = reader()
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return str(content)


class Controller(vkt.Controller):
    label = "BHoM Revit 2025 Connector"
    parametrization = Parametrization

    @staticmethod
    def _pull(params: Any) -> GatewayResult:
        try:
            request = build_pull_request(
                document_name=str(
                    _section_value(params, "source", "document_name", "") or ""
                ),
                categories=list(
                    _section_value(params, "source", "categories", []) or []
                ),
                include_parameters=bool(
                    _section_value(params, "source", "include_parameters", True)
                ),
                element_limit=int(
                    _section_value(params, "source", "element_limit", 2500)
                ),
            )
            return pull_model(
                connection_mode=str(
                    _section_value(
                        params, "source", "connection_mode", "Bundled sample"
                    )
                ),
                request=request,
            )
        except (ContractError, UnicodeDecodeError, ValueError) as error:
            raise vkt.UserError(str(error)) from error
        except RuntimeError as error:
            raise vkt.UserError(
                f"The Revit gateway returned an invalid snapshot. Details: {error}"
            ) from error

    @vkt.WebView("Model explorer", duration_guess=20)
    def model_explorer(self, params: Any, **kwargs: Any):
        result = self._pull(params)
        return vkt.WebResult(html=build_model_explorer(result.metadata))

    @vkt.DataView("Model metadata", duration_guess=20)
    def metadata_view(self, params: Any, **kwargs: Any):
        result = self._pull(params)
        summary = summarize_snapshot(result)
        source = result.metadata["source"]
        extraction = result.metadata["extraction"]

        group = vkt.DataGroup(
            vkt.DataItem(
                "Source model",
                source["document_name"],
                subgroup=vkt.DataGroup(
                    vkt.DataItem("Revit version", source["revit_version"]),
                    vkt.DataItem("BHoM version", source["bhom_version"]),
                    vkt.DataItem("Gateway mode", source["mode"]),
                ),
            ),
            vkt.DataItem(
                "Snapshot",
                summary["element_count"],
                suffix=" elements",
                subgroup=vkt.DataGroup(
                    vkt.DataItem("Categories", summary["category_count"]),
                    vkt.DataItem("Pulled parameters", summary["parameter_count"]),
                    vkt.DataItem("Filter", ", ".join(extraction["categories"])),
                ),
            ),
            vkt.DataItem(
                "LCA-ready takeoff",
                summary["material_count"],
                suffix=" materials",
                status=vkt.DataStatus.SUCCESS,
                status_message="GeneralMaterialTakeoff is ready for carbon-analysis.",
                subgroup=vkt.DataGroup(
                    vkt.DataItem(
                        "Total material mass",
                        summary["total_mass_kg"],
                        suffix=" kg",
                        number_of_decimals=1,
                    ),
                    vkt.DataItem(
                        "Total material volume",
                        summary["total_volume_m3"],
                        suffix=" m³",
                        number_of_decimals=3,
                    ),
                ),
            ),
        )
        return vkt.DataResult(group)

    @vkt.DataView("BHoM contract", duration_guess=20)
    def bhom_contract_view(self, params: Any, **kwargs: Any):
        result = self._pull(params)
        contract = summarize_bhom_contract(result)
        status = vkt.DataStatus.SUCCESS if contract["valid"] else vkt.DataStatus.WARNING
        status_message = (
            "Every exposed element has a BHoM GUID and Revit identifier."
            if contract["valid"]
            else "One or more element/material contract links are incomplete."
        )

        group = vkt.DataGroup(
            vkt.DataItem(
                "Contract status",
                "Valid" if contract["valid"] else "Incomplete",
                status=status,
                status_message=status_message,
                subgroup=vkt.DataGroup(
                    vkt.DataItem("Schema version", contract["schema_version"]),
                    vkt.DataItem("BHoM schema commit", contract["schema_commit"]),
                ),
            ),
            vkt.DataItem(
                "Element contract",
                contract["element_count"],
                suffix=" elements",
                subgroup=vkt.DataGroup(
                    vkt.DataItem("BHoM type", contract["element_contract"]),
                    vkt.DataItem(
                        "Mapped Revit elements",
                        contract["mapped_element_count"],
                    ),
                    vkt.DataItem(
                        "Concrete BHoM types",
                        ", ".join(contract["element_types"]),
                    ),
                ),
            ),
            vkt.DataItem(
                "Material contract",
                contract["material_link_count"],
                suffix=" element-material links",
                subgroup=vkt.DataGroup(
                    vkt.DataItem(
                        "Element fragment",
                        contract["material_fragment_contract"],
                    ),
                    vkt.DataItem(
                        "Aggregated takeoff",
                        contract["takeoff_contract"],
                    ),
                    vkt.DataItem(
                        "Takeoff items",
                        contract["takeoff_item_count"],
                    ),
                ),
            ),
        )
        return vkt.DataResult(group)

    def download_takeoff(self, params: Any, **kwargs: Any):
        result = self._pull(params)
        return vkt.DownloadResult(
            file_content=json.dumps(result.takeoff, indent=2, ensure_ascii=False),
            file_name="takeoff.bhom.json",
        )

    def download_snapshot(self, params: Any, **kwargs: Any):
        result = self._pull(params)
        return vkt.DownloadResult(
            file_content=json.dumps(result.elements, indent=2, ensure_ascii=False),
            file_name="revit-elements.bhom.json",
        )

    def download_lca_handoff(self, params: Any, **kwargs: Any):
        result = self._pull(params)
        uploaded_templates = _uploaded_text(
            _section_value(params, "project", "template_materials_file")
        )
        if uploaded_templates is None:
            uploaded_templates = (
                ROOT / "samples" / "template-materials.bhom.json"
            ).read_text(encoding="utf-8")

        try:
            handoff = build_lca_handoff(
                result=result,
                project_id=str(
                    _section_value(params, "project", "project_id", "") or ""
                ),
                project_name=str(
                    _section_value(params, "project", "project_name", "") or ""
                ),
                gross_floor_area_m2=float(
                    _section_value(params, "project", "gross_floor_area_m2", 0.0) or 0.0
                ),
                modules=list(_section_value(params, "project", "modules", []) or []),
                template_materials_json=uploaded_templates,
            )
        except (ContractError, UnicodeDecodeError, ValueError) as error:
            raise vkt.UserError(str(error)) from error

        return vkt.DownloadResult(
            file_content=json.dumps(handoff, indent=2, ensure_ascii=False),
            file_name="lca-handoff.json",
        )
