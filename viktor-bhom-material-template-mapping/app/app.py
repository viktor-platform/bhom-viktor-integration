from __future__ import annotations

import json
import uuid
from typing import Any

import viktor as vkt

from .catalog import (
    build_template_materials,
    candidates_for_material,
    catalogue_source,
    climate_change_a1toa3,
    parse_lookup_results,
    record_by_id,
    template_json,
)
from .contracts import (
    ContractError,
    parse_mapping_state,
    resolve_inputs,
    value_of,
)
from .parametrization import Parametrization
from .webview import build_mapping_html
from .worker_client import CACHE_VERSION, execute_worker


class Controller(vkt.Controller):
    label = "BHoM Material Template Mapping"
    parametrization = Parametrization

    @staticmethod
    def _context(
        params: Any,
    ) -> tuple[
        list[dict[str, Any]],
        dict[str, Any],
        dict[str, str],
        dict[str, Any],
    ]:
        try:
            inventory, takeoff = resolve_inputs(params)
            mappings = parse_mapping_state(value_of(params, "mapping_state_json", ""))
            lookup = parse_lookup_results(value_of(params, "lookup_results_json", ""))
            return inventory, takeoff, mappings, lookup
        except (ContractError, UnicodeDecodeError, ValueError) as error:
            raise vkt.UserError(str(error)) from error

    @staticmethod
    def _complete_templates(
        inventory: list[dict[str, Any]],
        mappings: dict[str, str],
        lookup: dict[str, Any],
    ) -> list[dict[str, Any]]:
        missing = [
            str(row["material_name"])
            for row in inventory
            if not mappings.get(str(row["material_name"]))
        ]
        if missing:
            preview = ", ".join(missing[:5])
            if len(missing) > 5:
                preview += f", and {len(missing) - 5} more"
            raise vkt.UserError(
                "Map every source material before exporting the BHoM template. "
                f"Still unmapped: {preview}."
            )
        try:
            return build_template_materials(inventory, mappings, lookup)
        except ContractError as error:
            raise vkt.UserError(str(error)) from error

    @staticmethod
    def _search_queries(
        params: Any,
        inventory: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        configured: dict[str, str] = {}
        for row in value_of(params, "material_inventory", []) or []:
            name = str(value_of(row, "material_name", "") or "").strip()
            query = str(value_of(row, "search_query", "") or "").strip()
            if name:
                configured[name.casefold()] = query
        return [
            {
                "source_material": str(row["material_name"]),
                "query": configured.get(str(row["material_name"]).casefold())
                or str(row["material_name"]),
                "count": 8,
            }
            for row in inventory
        ]

    def search_bhom_database(self, params: Any, **kwargs: Any):
        inventory, _, _, _ = self._context(params)
        request = {
            "schema_version": "1.0",
            "job_id": str(uuid.uuid4()),
            "dataset_scope": str(
                value_of(params, "dataset_scope", "All installed LCA datasets")
            ),
            "searches": self._search_queries(params, inventory),
        }
        try:
            outputs = execute_worker(
                request_json=json.dumps(request, separators=(",", ":")),
                timeout_seconds=180,
                cache_version=CACHE_VERSION,
            )
            lookup = parse_lookup_results(outputs["lookup-result.json"])
        except Exception as error:
            raise vkt.UserError(
                f"Installed BHoM dataset search failed: {error}"
            ) from error
        if lookup.get("status") != "completed":
            raise vkt.UserError("The BHoM dataset worker did not complete the search.")
        return vkt.SetParamsResult(
            {
                "lookup_results_json": outputs["lookup-result.json"],
                "mapping_state_json": '{"schema_version":"1.0","mappings":{}}',
                "template_materials_json": "[]",
            }
        )

    @vkt.WebView(
        "Mapping",
        duration_guess=1,
        description="Approve one installed BHoM dataset result per material.",
    )
    def mapping_view(self, params: Any, **kwargs: Any):
        inventory, _, mappings, lookup = self._context(params)
        try:
            return vkt.WebResult(html=build_mapping_html(inventory, mappings, lookup))
        except ContractError as error:
            raise vkt.UserError(str(error)) from error

    @vkt.DataView(
        "Validated template",
        duration_guess=1,
        description="Review worker search results and the selected BHoM EPD contract.",
    )
    def template_view(self, params: Any, **kwargs: Any):
        inventory, _, mappings, lookup = self._context(params)
        source = catalogue_source(lookup)
        mapped_count = sum(
            bool(mappings.get(str(row["material_name"]))) for row in inventory
        )
        candidate_count = sum(
            len(candidates_for_material(lookup, str(row["material_name"])))
            for row in inventory
        )
        unmapped_count = len(inventory) - mapped_count
        complete = bool(inventory) and unmapped_count == 0

        items: list[vkt.DataItem] = [
            vkt.DataItem(
                "BHoM material template",
                "Ready" if complete else "Mapping required",
                status=vkt.DataStatus.SUCCESS if complete else vkt.DataStatus.WARNING,
                status_message=(
                    "Every source material has one approved installed BHoM EPD."
                    if complete
                    else f"{unmapped_count} source materials still require a mapping."
                ),
                subgroup=vkt.DataGroup(
                    vkt.DataItem("Source materials", len(inventory)),
                    vkt.DataItem("Worker candidates", candidate_count),
                    vkt.DataItem("Approved mappings", mapped_count),
                    vkt.DataItem("Unmapped materials", unmapped_count),
                ),
            ),
            vkt.DataItem(
                "BHoM database",
                source.get("dataset", "All installed LCA datasets"),
                subgroup=vkt.DataGroup(
                    vkt.DataItem(
                        "BHoM component",
                        source.get("toolkit", "BHoM Library_Engine"),
                    ),
                    vkt.DataItem(
                        "Library path",
                        source.get("library_path", "LifeCycleAssessment"),
                    ),
                    vkt.DataItem("Available datasets", source.get("dataset_count", 0)),
                    vkt.DataItem("Available EPDs", source.get("epd_count", 0)),
                    vkt.DataItem("Contract", "BHoM Material[]"),
                    vkt.DataItem("Climate module", "A1–A3 combined"),
                ),
            ),
        ]

        for row in inventory[:90]:
            material_name = str(row["material_name"])
            record = record_by_id(lookup, mappings.get(material_name, ""))
            if record is None:
                items.append(
                    vkt.DataItem(
                        material_name,
                        "Not mapped",
                        status=vkt.DataStatus.WARNING,
                        status_message=(
                            "Search the installed BHoM datasets and approve an EPD "
                            "in Mapping."
                        ),
                        subgroup=vkt.DataGroup(
                            vkt.DataItem(
                                "Returned candidates",
                                len(candidates_for_material(lookup, material_name)),
                            ),
                            vkt.DataItem(
                                "Volume",
                                float(row["volume_m3"]),
                                suffix=" m³",
                                number_of_decimals=3,
                            ),
                        ),
                    )
                )
                continue

            impact = climate_change_a1toa3(record)
            items.append(
                vkt.DataItem(
                    material_name,
                    record["name"],
                    status=vkt.DataStatus.SUCCESS,
                    status_message="Selected from the installed BHoM dataset response.",
                    subgroup=vkt.DataGroup(
                        vkt.DataItem(
                            "Manufacturer", record.get("manufacturer") or "Unavailable"
                        ),
                        vkt.DataItem(
                            "Quantity type", record.get("quantity_type", "Undefined")
                        ),
                        vkt.DataItem(
                            "Climate change A1–A3",
                            impact if impact is not None else "Unavailable",
                            **(
                                {
                                    "suffix": " kgCO₂e/declared unit",
                                    "number_of_decimals": 4,
                                }
                                if impact is not None
                                else {}
                            ),
                        ),
                        vkt.DataItem(
                            "Dataset", record.get("dataset_name", "Unavailable")
                        ),
                        vkt.DataItem("BHoM GUID", record["catalog_id"]),
                    ),
                )
            )

        return vkt.DataResult(vkt.DataGroup(*items))

    def download_template(self, params: Any, **kwargs: Any):
        inventory, _, mappings, lookup = self._context(params)
        self._complete_templates(inventory, mappings, lookup)
        return vkt.DownloadResult(
            file_content=template_json(inventory, mappings, lookup),
            file_name="template-materials.bhom.json",
        )

    def download_takeoff(self, params: Any, **kwargs: Any):
        _, takeoff, _, _ = self._context(params)
        return vkt.DownloadResult(
            file_content=json.dumps(takeoff, indent=2, ensure_ascii=False),
            file_name="takeoff.bhom.json",
        )

    def download_handoff(self, params: Any, **kwargs: Any):
        inventory, takeoff, mappings, lookup = self._context(params)
        templates = self._complete_templates(inventory, mappings, lookup)
        area = float(value_of(params, "gross_floor_area_m2", 0) or 0)
        handoff = {
            "schema_version": "1.0",
            "target": {
                "app": "bhom-lca-carbon-analysis",
                "method_name": "run_analysis",
            },
            "source": {
                "app": "bhom-material-template-mapping",
                "catalogue": catalogue_source(lookup),
            },
            "params": {
                "takeoff_json": json.dumps(
                    takeoff, separators=(",", ":"), ensure_ascii=False
                ),
                "template_materials_json": json.dumps(
                    templates, separators=(",", ":"), ensure_ascii=False
                ),
                "gross_floor_area_m2": area,
                "modules": ["A1toA3"],
                "prioritise_template_materials": True,
            },
        }
        return vkt.DownloadResult(
            file_content=json.dumps(handoff, indent=2, ensure_ascii=False),
            file_name="lca-handoff.json",
        )
