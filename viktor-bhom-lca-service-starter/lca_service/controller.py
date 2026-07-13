from __future__ import annotations

import json

import pandas as pd
import viktor as vkt

from .parametrization import Parametrization
from .service import ContractError, FileReadError, ServiceResult, run_service
from .visualization import build_figure, records_to_dataframe


class Controller(vkt.Controller):
    label = "BHoM LCA Service"
    parametrization = Parametrization

    @staticmethod
    def _calculate(params) -> ServiceResult:
        try:
            return run_service(params)
        except (ContractError, FileReadError, ValueError) as error:
            raise vkt.UserError(str(error)) from error
        except RuntimeError as error:
            raise vkt.UserError(
                f"The LCA worker returned an invalid result. Details: {error}"
            ) from error

    @vkt.DataView("Summary", duration_guess=30)
    def summary_view(self, params, **kwargs):
        result = self._calculate(params).normalized
        summary = result["summary"]

        items = [
            vkt.DataItem(
                "Climate Change Total",
                round(summary["total_kgco2e"], 3),
                suffix="kgCO2e",
            ),
            vkt.DataItem(
                "Climate Change Total",
                round(summary["total_tco2e"], 6),
                suffix="tCO2e",
            ),
            vkt.DataItem(
                "Result records",
                summary["record_count"],
            ),
            vkt.DataItem(
                "Unmatched materials",
                summary["unmatched_material_count"],
            ),
        ]

        intensity = summary.get("carbon_intensity_kgco2e_m2")
        if intensity is not None:
            items.append(
                vkt.DataItem(
                    "Carbon intensity",
                    round(intensity, 3),
                    suffix="kgCO2e/m²",
                )
            )

        return vkt.DataResult(vkt.DataGroup(*items))

    @vkt.PlotlyView("Analysis chart", duration_guess=30)
    def analysis_chart(self, params, **kwargs):
        result = self._calculate(params).normalized
        try:
            figure = build_figure(
                result,
                chart_type=str(params.chart_type),
                group_by=str(params.group_by),
            )
        except ValueError as error:
            raise vkt.UserError(str(error)) from error
        return vkt.PlotlyResult(figure)

    @vkt.TableView("Detailed records", duration_guess=30)
    def detail_table(self, params, **kwargs):
        result = self._calculate(params).normalized
        frame = records_to_dataframe(result)
        if frame.empty:
            frame = pd.DataFrame(
                {
                    "material": pd.Series(dtype="object"),
                    "environmental_product_declaration": pd.Series(dtype="object"),
                    "metric": pd.Series(dtype="object"),
                    "module": pd.Series(dtype="object"),
                    "value": pd.Series(dtype="float64"),
                    "unit": pd.Series(dtype="object"),
                }
            )
        return vkt.TableResult(frame)

    def run_analysis(self, params, **kwargs):
        """Callable DownloadButton method for users and remote computations."""
        service_result = self._calculate(params)
        return vkt.DownloadResult(
            file_content=json.dumps(
                service_result.normalized,
                indent=2,
                ensure_ascii=False,
            ),
            file_name="analysis-result.json",
        )

    def download_raw_bhom(self, params, **kwargs):
        service_result = self._calculate(params)
        return vkt.DownloadResult(
            file_content=service_result.artifacts["bhom-results.json"],
            file_name="bhom-results.json",
        )

    def download_events(self, params, **kwargs):
        service_result = self._calculate(params)
        return vkt.DownloadResult(
            file_content=service_result.artifacts["analysis-events.json"],
            file_name="analysis-events.json",
        )

    def download_runtime_manifest(self, params, **kwargs):
        service_result = self._calculate(params)
        return vkt.DownloadResult(
            file_content=service_result.artifacts["runtime-manifest.json"],
            file_name="runtime-manifest.json",
        )
