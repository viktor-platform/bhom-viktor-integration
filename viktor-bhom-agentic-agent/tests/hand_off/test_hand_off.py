"""Offline contract tests for the BHoM Revit-to-LCA handoffs."""

import asyncio
import json
from collections.abc import Callable, Coroutine
from types import SimpleNamespace
from typing import Any, cast

import pytest

from agent.tools.registry import get_tools
from agent.tools.viktor_tools.bhom import handoffs, run_apps
from agent.tools.viktor_tools.workflow import result_ops
from agent.tools.viktor_tools.workflow.entity_ops import WorkflowAppRegistry
from agent.tools.viktor_tools.workflow.param_ops import (
    ApplySetParamsMethodInNodeArgs,
    GetParamsInNodeArgs,
    SetParamsInNodeArgs,
    WorkflowNodeParamService,
)
from tests.helpers import FakeNodeService

REVIT_STORAGE_KEY = "bhom_revit_takeoff"
MAPPING_STORAGE_KEY = "bhom_material_template"


def _directory() -> SimpleNamespace:
    return SimpleNamespace(
        run_id="bhom-test-run",
        entities={
            "revit_connector": SimpleNamespace(
                node_id="revit_connector",
                workspace_id=3424,
                entity_id=14972,
                url="https://demo.viktor.ai/workspaces/3424/app/editor/14972",
                entity_mode="existing_entity",
                created_for_run=False,
                saved_params_are_shared=True,
                storage_key=REVIT_STORAGE_KEY,
                result_key="download",
            ),
            "material_template_mapping": SimpleNamespace(
                node_id="material_template_mapping",
                workspace_id=3425,
                entity_id=14969,
                url="https://demo.viktor.ai/workspaces/3425/app/editor/14969",
                entity_mode="existing_entity",
                created_for_run=False,
                saved_params_are_shared=True,
                storage_key=MAPPING_STORAGE_KEY,
                result_key="data",
            ),
            "lca_analysis": SimpleNamespace(
                node_id="lca_analysis",
                workspace_id=3423,
                entity_id=14973,
                url="https://demo.viktor.ai/workspaces/3423/app/editor/14973",
                entity_mode="existing_entity",
                created_for_run=False,
                saved_params_are_shared=True,
                storage_key="bhom_lca_result",
                result_key="download",
            ),
        },
    )


def _handoff(name: str) -> Callable[[Any, str], Coroutine[Any, Any, str]]:
    function = getattr(handoffs, name, None)
    assert function is not None, f"Missing BHoM handoff function: {name}"
    return cast(Callable[[Any, str], Coroutine[Any, Any, str]], function)


def test_registry_has_fixed_bhom_node_order_and_ids() -> None:
    registry = WorkflowAppRegistry.bhom_defaults()
    templates = registry.selected_templates(["lca_analysis"], include_dependencies=True)

    assert [
        (item.node_id, item.workspace_id, item.sibling_entity_id) for item in templates
    ] == [
        ("revit_connector", 3424, 14972),
        ("material_template_mapping", 3425, 14969),
        ("lca_analysis", 3423, 14973),
    ]


def test_agent_exposes_workflow_node_storage_run_and_handoff_tools() -> None:
    tool_names = {tool.name for tool in get_tools()}

    assert {
        "create_workflow_entity_directory",
        "get_workflow_entity_directory",
        "get_params_in_node",
        "set_params_in_node",
        "get_result_from_node",
        "run_revit_connector",
        "handoff_revit_connector_to_material_template_mapping",
        "run_material_template_mapping",
        "handoff_material_template_mapping_to_lca_analysis",
        "run_lca_analysis",
    } <= tool_names


def test_revit_stored_takeoff_is_handed_to_mapping(
    monkeypatch: pytest.MonkeyPatch,
    sample_takeoff: dict[str, Any],
) -> None:
    takeoff_json = json.dumps(sample_takeoff)
    service = FakeNodeService(
        _directory(),
        {
            "revit_connector": {},
            "material_template_mapping": {
                "dataset_scope": "All installed LCA datasets",
                "gross_floor_area_m2": 750.0,
                "lookup_results_json": "stale lookup",
                "mapping_state_json": '{"schema_version":"1.0","mappings":{"old":"epd"}}',
                "template_materials_json": "[{}]",
            },
            "lca_analysis": {},
        },
    )
    storage = {
        REVIT_STORAGE_KEY: {
            "takeoff_json": takeoff_json,
        }
    }
    monkeypatch.setattr(handoffs, "get_workflow_entity_service", lambda: service)
    monkeypatch.setattr(
        handoffs, "try_read_json_from_storage", lambda key: storage.get(key)
    )

    result = asyncio.run(
        _handoff("handoff_revit_connector_to_material_template_mapping_func")(
            None, "{}"
        )
    )

    assert json.loads(result)["status"] == "completed"
    assert service.params_by_node["material_template_mapping"] == {
        "dataset_scope": "All installed LCA datasets",
        "gross_floor_area_m2": 750.0,
        "material_inventory": [
            {
                "material_name": "Concrete C30/37",
                "search_query": "Concrete C30/37",
                "volume_m3": 12.5,
                "density_kg_m3": 2400.0,
            }
        ],
        "lookup_results_json": "",
        "mapping_state_json": '{"schema_version":"1.0","mappings":{}}',
        "template_materials_json": "[]",
    }


def test_approved_mapping_is_handed_to_lca(
    monkeypatch: pytest.MonkeyPatch,
    sample_takeoff: dict[str, Any],
    sample_templates: list[dict[str, Any]],
) -> None:
    takeoff_json = json.dumps(sample_takeoff)
    template_materials_json = json.dumps(sample_templates)
    service = FakeNodeService(
        _directory(),
        {
            "revit_connector": {},
            "material_template_mapping": {},
            "lca_analysis": {"chart_type": "Stacked bar"},
        },
    )
    storage = {
        REVIT_STORAGE_KEY: {
            "takeoff_json": takeoff_json,
        },
        MAPPING_STORAGE_KEY: {
            "approved": True,
            "template_materials_json": template_materials_json,
            "project_id": "sample-office",
            "project_name": "Sample Office",
            "gross_floor_area_m2": 500.0,
        },
    }
    monkeypatch.setattr(handoffs, "get_workflow_entity_service", lambda: service)
    monkeypatch.setattr(
        handoffs, "try_read_json_from_storage", lambda key: storage.get(key)
    )

    result = asyncio.run(
        _handoff("handoff_material_template_mapping_to_lca_analysis_func")(None, "{}")
    )

    assert json.loads(result)["status"] == "completed"
    assert service.params_by_node["lca_analysis"] == {
        "chart_type": "Stacked bar",
        "takeoff_json": takeoff_json,
        "template_materials_json": template_materials_json,
        "project_id": "sample-office",
        "project_name": "Sample Office",
        "gross_floor_area_m2": 500.0,
        "modules": ["A1", "A2", "A3"],
    }


def test_mapping_to_lca_requires_saved_approved_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeNodeService(
        _directory(),
        {
            "revit_connector": {},
            "material_template_mapping": {},
            "lca_analysis": {},
        },
    )
    monkeypatch.setattr(handoffs, "get_workflow_entity_service", lambda: service)
    monkeypatch.setattr(handoffs, "try_read_json_from_storage", lambda _key: None)

    result = asyncio.run(
        _handoff("handoff_material_template_mapping_to_lca_analysis_func")(None, "{}")
    )
    response = json.loads(result)

    assert response["status"] == "needs_prerequisite"
    assert response["missing_storage_key"] == MAPPING_STORAGE_KEY
    assert service.params_by_node["lca_analysis"] == {}


def test_set_and_get_node_params_deep_merge_with_readback() -> None:
    service = FakeNodeService(
        _directory(),
        {
            "revit_connector": {},
            "material_template_mapping": {},
            "lca_analysis": {"chart_type": "Stacked bar"},
        },
    )
    params = WorkflowNodeParamService(entity_service=service)

    written = params.set_params(
        SetParamsInNodeArgs(
            node_id="lca_analysis",
            params={"modules": ["A1", "A2", "A3"]},
        )
    )
    read = params.get_params(GetParamsInNodeArgs(node_id="lca_analysis"))

    assert written["readback_verified"] is True
    assert read["params"] == {
        "chart_type": "Stacked bar",
        "modules": ["A1", "A2", "A3"],
    }


def test_worker_search_uses_set_params_button_method_type() -> None:
    class RestClient:
        def __init__(self) -> None:
            self.method_type: str | None = None
            self.input_keys: list[str] = []

        def create_editor_session(self, **kwargs: Any) -> str:
            return "editor-session"

        def run_entity_method(self, **kwargs: Any) -> dict[str, Any]:
            self.method_type = kwargs.get("method_type")
            self.input_keys = sorted(kwargs.get("params", {}))
            return {
                "set_params": {
                    "lookup_results_json": '{"status":"completed"}',
                }
            }

    service = FakeNodeService(
        _directory(),
        {
            "revit_connector": {},
            "material_template_mapping": {
                "dataset_scope": "All installed LCA datasets",
                "material_inventory": [
                    {
                        "material_name": "Steel",
                        "search_query": "Steel",
                        "volume_m3": 1.0,
                        "density_kg_m3": None,
                    }
                ],
                "takeoff_json": "hidden Revit JSON",
                "mapping_state_json": "saved mapping state",
            },
            "lca_analysis": {},
        },
    )
    client = RestClient()
    service.client = client

    result = WorkflowNodeParamService(entity_service=service).apply_set_params_method(
        ApplySetParamsMethodInNodeArgs(
            node_id="material_template_mapping",
            method_name="search_bhom_database",
            confirm=True,
        )
    )

    assert client.method_type == "set-params-button"
    assert client.input_keys == ["dataset_scope", "material_inventory"]
    assert result["readback_verified"] is True


def test_get_result_from_node_reads_workflow_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeNodeService(
        _directory(),
        {"revit_connector": {}, "material_template_mapping": {}, "lca_analysis": {}},
    )
    stored_result = {"project_id": "sample-office", "total_kgco2e": 1234.5}
    monkeypatch.setattr(result_ops, "get_workflow_entity_service", lambda: service)
    monkeypatch.setattr(
        result_ops,
        "read_json_from_storage",
        lambda key, run_id: stored_result,
    )
    monkeypatch.setattr(
        result_ops,
        "workflow_storage_key",
        lambda key, run_id: f"workflow_runs/{run_id}/{key}",
    )

    response = json.loads(
        asyncio.run(
            result_ops.get_result_from_node_func(
                cast(Any, None), '{"node_id":"lca_analysis"}'
            )
        )
    )

    assert response["status"] == "completed"
    assert response["result"] == stored_result


def test_presigned_download_does_not_receive_viktor_bearer_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_headers: dict[str, str] = {}

    class Response:
        text = '{"status":"ok"}'

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"status": "ok"}

    def get(
        url: str,
        *,
        headers: dict[str, str],
        timeout: tuple[float, float],
    ) -> Response:
        observed_headers.update(headers)
        assert url.startswith("https://viktor-storage-eu1.s3.amazonaws.com/")
        assert timeout == (5.0, 60.0)
        return Response()

    monkeypatch.setattr(
        "agent.tools.viktor_tools.bhom.run_apps.requests.get",
        get,
    )
    client = SimpleNamespace(
        api_base="https://demo.viktor.ai/api",
        auth_headers={"Authorization": "Bearer secret"},
    )

    result = run_apps._download_json(
        {"url": "https://viktor-storage-eu1.s3.amazonaws.com/tmp/result.json"},
        cast(Any, client),
    )

    assert result == {"status": "ok"}
    assert observed_headers == {}
