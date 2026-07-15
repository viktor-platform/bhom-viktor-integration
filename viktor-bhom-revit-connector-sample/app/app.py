from __future__ import annotations

import json
from typing import Any

import viktor as vkt

from .bhom_formatter import (
    summarize_bhom_contract,
    summarize_material_inputs,
    summarize_snapshot,
)
from .contracts import ContractError, GatewayResult, build_pull_request
from .gateway_client import pull_model
from .geometry import build_geometry, gross_floor_area_m2
from .parametrization import Parametrization


def _param_value(params: Any, name: str, default: Any = None) -> Any:
    if isinstance(params, dict):
        return params.get(name, default)
    return getattr(params, name, default)


class Controller(vkt.Controller):
    label = "BHoM Revit 2025 Connector"
    parametrization = Parametrization

    @staticmethod
    def _pull(params: Any) -> GatewayResult:
        try:
            request = build_pull_request(
                document_name="",
                categories=list(_param_value(params, "categories", []) or []),
                include_parameters=bool(
                    _param_value(params, "include_parameters", True)
                ),
                element_limit=int(_param_value(params, "element_limit", 2500)),
            )
            return pull_model(request=request)
        except (ContractError, UnicodeDecodeError, ValueError) as error:
            raise vkt.UserError(str(error)) from error
        except RuntimeError as error:
            raise vkt.UserError(
                f"The Revit gateway returned an invalid snapshot. Details: {error}"
            ) from error

    @vkt.GeometryView("Geometry", duration_guess=20, x_axis_to_right=True)
    def geometry_view(self, params: Any, **kwargs: Any):
        result = self._pull(params)
        geometry = build_geometry(result)
        if not geometry:
            raise vkt.UserError(
                "The selected BHoM elements do not expose supported Location geometry."
            )
        return vkt.GeometryResult(geometry)

    @vkt.DataView("LCA data", duration_guess=20)
    def lca_data_view(self, params: Any, **kwargs: Any):
        result = self._pull(params)
        material_rows = summarize_material_inputs(result, [])
        missing_density_count = sum(
            not bool(row["density_complete"]) for row in material_rows
        )
        calculated_mass = sum(float(row["calculated_mass_kg"]) for row in material_rows)
        total_volume = sum(float(row["volume_m3"]) for row in material_rows)
        source = result.metadata["source"]

        items: list[vkt.DataItem] = [
            vkt.DataItem(
                "Material inputs",
                len(material_rows),
                suffix=" materials",
                subgroup=vkt.DataGroup(
                    vkt.DataItem("Source document", source["document_name"]),
                    vkt.DataItem(
                        "Gross floor area",
                        gross_floor_area_m2(result),
                        suffix=" m²",
                        number_of_decimals=2,
                    ),
                    vkt.DataItem(
                        "Total volume",
                        total_volume,
                        suffix=" m³",
                        number_of_decimals=3,
                    ),
                    vkt.DataItem(
                        "Available calculated mass",
                        calculated_mass,
                        suffix=" kg",
                        number_of_decimals=1,
                    ),
                    vkt.DataItem("Materials missing density", missing_density_count),
                ),
            )
        ]

        for row in material_rows[:90]:
            density = row["density_kg_m3"]
            density_item = (
                vkt.DataItem(
                    "Density",
                    float(density),
                    suffix=" kg/m³",
                    number_of_decimals=1,
                )
                if density is not None
                else vkt.DataItem("Density", "Unavailable")
            )
            items.append(
                vkt.DataItem(
                    str(row["name"]),
                    float(row["volume_m3"]),
                    suffix=" m³",
                    number_of_decimals=3,
                    subgroup=vkt.DataGroup(
                        density_item,
                        vkt.DataItem("Density source", row["density_source"]),
                        vkt.DataItem(
                            "Calculated mass",
                            float(row["calculated_mass_kg"]),
                            suffix=" kg",
                            number_of_decimals=1,
                        ),
                        vkt.DataItem(
                            "BHoM reported mass",
                            float(row["reported_mass_kg"]),
                            suffix=" kg",
                            number_of_decimals=1,
                        ),
                        vkt.DataItem("Revit material uses", row["number_items"]),
                    ),
                )
            )

        if len(material_rows) > 90:
            items.append(vkt.DataItem("Additional materials", len(material_rows) - 90))

        return vkt.DataResult(vkt.DataGroup(*items))

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
                status_message="GeneralMaterialTakeoff is ready for carbon analysis.",
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
