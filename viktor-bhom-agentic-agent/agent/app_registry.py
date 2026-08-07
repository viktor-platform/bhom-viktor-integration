import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowApplication:
    key: str
    label: str
    url: str


def _configured_url(variable: str) -> str:
    value = os.getenv(variable, "").strip()
    return value or f"Configure {variable} in the VIKTOR app environment"


def applications() -> dict[str, WorkflowApplication]:
    return {
        "revit": WorkflowApplication(
            key="revit",
            label="BHoM Revit 2025 Connector",
            url=_configured_url("VIKTOR_BHOM_REVIT_APP_URL"),
        ),
        "mapping": WorkflowApplication(
            key="mapping",
            label="BHoM Material Template Mapping",
            url=_configured_url("VIKTOR_BHOM_MAPPING_APP_URL"),
        ),
        "lca": WorkflowApplication(
            key="lca",
            label="BHoM LCA Carbon Analysis",
            url=_configured_url("VIKTOR_BHOM_LCA_APP_URL"),
        ),
    }
