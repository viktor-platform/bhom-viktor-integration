import json
import os
import re
import time
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

import requests
import viktor as vkt
from agents.tool_context import ToolContext
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.tools.viktor_tools.bhom.common import (
    LCA_ANALYSIS_STORAGE_KEY,
    MATERIAL_TEMPLATE_MAPPING_STORAGE_KEY,
    REVIT_CONNECTOR_STORAGE_KEY,
    STORAGE_SCOPE,
    WORKFLOW_HTML_STORAGE_KEY,
    delete_workflow_run_storage,
    workflow_storage_key,
)
from agent.tools.viktor_tools.sdk_compute import (
    get_optional_environment,
    get_required_token,
)
from agent.tools.viktor_tools.tool_feedback import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.types import AgentContext, EmptyToolArgs
from workflow_graph.models import Connection, Node, Workflow
from workflow_graph.state import build_canvas_state, save_canvas_state
from workflow_graph.viewer import WorkflowViewer

WORKFLOW_ENTITY_DIRECTORY_KEY = "workflow_entity_directory"
JOB_RESULT_KEYS = (
    "web",
    "ifc",
    "pdf",
    "geojson",
    "data",
    "image",
    "plotly",
    "geometry",
    "table",
    "download",
    "set_params",
)
FAILED_JOB_STATUSES = {
    "failed",
    "cancelled",
    "error",
    "error_user",
    "error_app_reloading",
    "error_timeout",
    "expired",
    "stopped",
}

WorkflowNodeId = Literal[
    "revit_connector",
    "material_template_mapping",
    "lca_analysis",
]
WorkflowEntityMode = Literal["clone_sibling", "existing_entity"]
WorkflowEntityResolution = Literal[
    "created_sibling",
    "configured_existing",
    "fallback_existing",
]


class WorkflowAppTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: WorkflowNodeId
    app_name: str
    label: str
    workspace_id: int
    sibling_entity_id: int
    method_name: str
    result_key: str
    storage_key: str
    icon: str
    icon_bg: str
    pre_run_method_name: str | None = None
    entity_mode: WorkflowEntityMode = "clone_sibling"
    depends_on: list[WorkflowNodeId] = Field(default_factory=list)


class WorkflowRunEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: WorkflowNodeId
    app_name: str
    label: str
    workspace_id: int
    sibling_entity_id: int
    entity_id: int
    entity_name: str
    url: str
    method_name: str
    result_key: str
    storage_key: str
    icon: str
    icon_bg: str
    pre_run_method_name: str | None = None
    entity_mode: WorkflowEntityMode = "clone_sibling"
    created_for_run: bool = True
    saved_params_are_shared: bool = False
    resolution: WorkflowEntityResolution = "created_sibling"
    resolution_warning: str | None = None
    depends_on: list[WorkflowNodeId] = Field(default_factory=list)


class WorkflowEntityDirectory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(default_factory=lambda: f"legacy-{uuid4().hex[:8]}")
    run_name: str
    created_at: str
    storage_key: str = WORKFLOW_ENTITY_DIRECTORY_KEY
    entities: dict[WorkflowNodeId, WorkflowRunEntity]


class CreateWorkflowEntityDirectoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_name: str | None = Field(
        default=None,
        description="Optional run name. Defaults to 'BHoM Revit-to-LCA Run - YYYY-MM-DD HH:MM'.",
    )
    include_nodes: list[WorkflowNodeId] = [
        "revit_connector",
        "material_template_mapping",
        "lca_analysis",
    ]
    include_dependencies: bool = Field(
        default=True,
        description="Automatically add upstream dependencies required by selected nodes.",
    )
    replace_existing: bool = Field(
        default=True,
        description="Replace the active workflow entity directory with a fresh run.",
    )


class ResetWorkflowEntityDirectoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = Field(
        default=False,
        description="Must be true to clear the active workflow entity directory.",
    )


class RestEntityResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    entity_type: int | str
    entity_type_name: str | None = None
    properties: dict[str, Any] | None = None
    params: dict[str, Any] | None = None
    last_saved_params: dict[str, Any] | None = None


class ViktorJobUserError(ValueError):
    pass


class WorkflowAlreadyExistsError(RuntimeError):
    def __init__(self, directory: WorkflowEntityDirectory) -> None:
        super().__init__("An active workflow entity directory already exists.")
        self.directory = directory


class WorkflowAppRegistry:
    def __init__(self, templates: dict[WorkflowNodeId, WorkflowAppTemplate]) -> None:
        self._templates = templates

    @classmethod
    def bhom_defaults(cls) -> "WorkflowAppRegistry":
        return cls(
            {
                "revit_connector": WorkflowAppTemplate(
                    node_id="revit_connector",
                    app_name="BHoM Revit Connector",
                    label="Get Revit Material Takeoff",
                    workspace_id=3424,
                    sibling_entity_id=14972,
                    method_name="download_takeoff",
                    result_key="download",
                    storage_key=REVIT_CONNECTOR_STORAGE_KEY,
                    icon="RVT",
                    icon_bg="#dbeafe",
                    entity_mode="existing_entity",
                    depends_on=[],
                ),
                "material_template_mapping": WorkflowAppTemplate(
                    node_id="material_template_mapping",
                    app_name="BHoM Material Template Mapping",
                    label="Review Material-to-EPD Mapping",
                    workspace_id=3425,
                    sibling_entity_id=14969,
                    method_name="workflow_handoff_view",
                    result_key="data",
                    storage_key=MATERIAL_TEMPLATE_MAPPING_STORAGE_KEY,
                    icon="MAP",
                    icon_bg="#dcfce7",
                    entity_mode="existing_entity",
                    depends_on=["revit_connector"],
                ),
                "lca_analysis": WorkflowAppTemplate(
                    node_id="lca_analysis",
                    app_name="BHoM LCA Analysis",
                    label="Run Life-Cycle Assessment",
                    workspace_id=3423,
                    sibling_entity_id=14973,
                    method_name="run_analysis",
                    result_key="download",
                    storage_key=LCA_ANALYSIS_STORAGE_KEY,
                    icon="LCA",
                    icon_bg="#ede9fe",
                    entity_mode="existing_entity",
                    depends_on=["material_template_mapping"],
                ),
            }
        )

    def get(self, node_id: WorkflowNodeId) -> WorkflowAppTemplate:
        return self._templates[node_id]

    def expand_node_ids(
        self,
        include_nodes: list[WorkflowNodeId],
        *,
        include_dependencies: bool,
    ) -> list[WorkflowNodeId]:
        ordered: list[WorkflowNodeId] = []

        def add(node_id: WorkflowNodeId) -> None:
            template = self.get(node_id)
            if include_dependencies:
                for dependency in template.depends_on:
                    add(dependency)
            if node_id not in ordered:
                ordered.append(node_id)

        for node_id in include_nodes:
            add(node_id)
        return ordered

    def selected_templates(
        self,
        include_nodes: list[WorkflowNodeId],
        *,
        include_dependencies: bool,
    ) -> list[WorkflowAppTemplate]:
        return [
            self.get(node_id)
            for node_id in self.expand_node_ids(
                include_nodes,
                include_dependencies=include_dependencies,
            )
        ]


class ViktorRestEntityClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        api_base: str | None = None,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
    ) -> None:
        self.api_base = (api_base or self.normalize_api_base()).strip().rstrip("/")
        self.timeout = (connect_timeout, read_timeout)
        self.auth_headers = {
            "Authorization": f"Bearer {(token or get_required_token()).strip()}"
        }

    @staticmethod
    def normalize_api_base() -> str:
        configured_base = os.getenv("VIKTOR_API_BASE")
        if configured_base and configured_base.strip():
            base = configured_base.strip().rstrip("/")
            if not base.startswith("https://"):
                raise ValueError("VIKTOR_API_BASE must be an absolute HTTPS URL.")
            return base if base.endswith("/api") else f"{base}/api"

        environment = get_optional_environment() or "demo.viktor.ai"
        host = environment.strip().rstrip("/")
        if host.startswith("https://"):
            host = host.removeprefix("https://")
        if "." not in host:
            host = f"{host}.viktor.ai"
        if "/" in host or not host.endswith(".viktor.ai"):
            raise ValueError("ENV_VKT must be host-only, for example demo.viktor.ai.")
        return f"https://{host}/api"

    @property
    def ui_base(self) -> str:
        return self.api_base.removesuffix("/api")

    def editor_url(self, *, workspace_id: int, entity_id: int) -> str:
        return f"{self.ui_base}/workspaces/{workspace_id}/app/editor/{entity_id}"

    def get_entity(
        self,
        *,
        workspace_id: int,
        entity_id: int,
        properties: bool = False,
        clean_params: bool = False,
        param_types: bool = False,
    ) -> RestEntityResponse:
        payload = self._request_json(
            "GET",
            f"workspaces/{workspace_id}/entities/{entity_id}/",
            params={
                "properties": str(properties).lower(),
                "clean_params": str(clean_params).lower(),
                "param_types": str(param_types).lower(),
            },
            action="Get entity",
        )
        return RestEntityResponse.model_validate(payload)

    def get_parent_entity(
        self, *, workspace_id: int, entity_id: int
    ) -> RestEntityResponse | None:
        payload = self._request_json(
            "GET",
            f"workspaces/{workspace_id}/entities/{entity_id}/parent/",
            action="Get parent entity",
            allow_not_found=True,
        )
        if not payload:
            return None
        return RestEntityResponse.model_validate(payload)

    def create_sibling_from_template(
        self,
        *,
        template: WorkflowAppTemplate,
        run_name: str,
    ) -> WorkflowRunEntity:
        sibling = self.get_entity(
            workspace_id=template.workspace_id,
            entity_id=template.sibling_entity_id,
        )
        parent = self.get_parent_entity(
            workspace_id=template.workspace_id,
            entity_id=template.sibling_entity_id,
        )
        entity_name = f"{run_name} - {template.app_name}"
        created = self._create_entity_with_fallback_type(
            workspace_id=template.workspace_id,
            entity_type=sibling.entity_type,
            fallback_entity_type=sibling.entity_type_name,
            name=entity_name,
            parent_entity_id=parent.id if parent else None,
        )
        return WorkflowRunEntity(
            node_id=template.node_id,
            app_name=template.app_name,
            label=template.label,
            workspace_id=template.workspace_id,
            sibling_entity_id=template.sibling_entity_id,
            entity_id=created.id,
            entity_name=created.name,
            url=self.editor_url(
                workspace_id=template.workspace_id, entity_id=created.id
            ),
            method_name=template.method_name,
            result_key=template.result_key,
            storage_key=template.storage_key,
            icon=template.icon,
            icon_bg=template.icon_bg,
            pre_run_method_name=template.pre_run_method_name,
            entity_mode=template.entity_mode,
            created_for_run=True,
            saved_params_are_shared=False,
            resolution="created_sibling",
            depends_on=template.depends_on,
        )

    def bind_existing_entity_from_template(
        self,
        *,
        template: WorkflowAppTemplate,
        resolution: WorkflowEntityResolution = "configured_existing",
        resolution_warning: str | None = None,
    ) -> WorkflowRunEntity:
        existing = self.get_entity(
            workspace_id=template.workspace_id,
            entity_id=template.sibling_entity_id,
        )
        return WorkflowRunEntity(
            node_id=template.node_id,
            app_name=template.app_name,
            label=template.label,
            workspace_id=template.workspace_id,
            sibling_entity_id=template.sibling_entity_id,
            entity_id=template.sibling_entity_id,
            entity_name=existing.name,
            url=self.editor_url(
                workspace_id=template.workspace_id, entity_id=template.sibling_entity_id
            ),
            method_name=template.method_name,
            result_key=template.result_key,
            storage_key=template.storage_key,
            icon=template.icon,
            icon_bg=template.icon_bg,
            pre_run_method_name=template.pre_run_method_name,
            entity_mode=template.entity_mode,
            created_for_run=False,
            saved_params_are_shared=True,
            resolution=resolution,
            resolution_warning=resolution_warning,
            depends_on=template.depends_on,
        )

    def resolve_entity_from_template(
        self,
        *,
        template: WorkflowAppTemplate,
        run_name: str,
    ) -> WorkflowRunEntity:
        if template.entity_mode == "existing_entity":
            return self.bind_existing_entity_from_template(template=template)

        try:
            return self.create_sibling_from_template(
                template=template, run_name=run_name
            )
        except RuntimeError as exc:
            return self.bind_existing_entity_from_template(
                template=template,
                resolution="fallback_existing",
                resolution_warning=(
                    "Could not create a fresh sibling entity, so this node was bound to the "
                    f"configured existing entity instead. Original error: {exc}"
                ),
            )

    def set_entity_params(
        self,
        *,
        workspace_id: int,
        entity_id: int,
        params: dict[str, Any],
        message: str,
    ) -> None:
        entity = self.get_entity(workspace_id=workspace_id, entity_id=entity_id)
        self._request_json(
            "PUT",
            f"workspaces/{workspace_id}/entities/{entity_id}/",
            json_body={"name": entity.name, "properties": params, "message": message},
            action="Set entity params",
        )

    def delete_entity(self, *, workspace_id: int, entity_id: int) -> None:
        self._request_json(
            "DELETE",
            f"workspaces/{workspace_id}/entities/{entity_id}/",
            action="Delete entity",
        )

    def create_editor_session(self, *, workspace_id: int, entity_id: int) -> str:
        payload = self._request_json(
            "POST",
            f"workspaces/{workspace_id}/entities/{entity_id}/session/",
            json_body={},
            action="Create editor session",
        )
        if not isinstance(payload, dict):
            raise TypeError("Create editor session did not return a JSON object.")
        session = (
            payload.get("editor_session")
            or payload.get("session")
            or payload.get("session_id")
            or payload.get("id")
        )
        if not isinstance(session, str) or not session:
            raise RuntimeError(
                "Create editor session response did not include a session id."
            )
        return session

    def create_job(
        self,
        *,
        workspace_id: int,
        entity_id: int,
        method_name: str,
        params: dict[str, Any] | None = None,
        poll_result: bool = False,
        method_type: str | None = None,
        editor_session: str | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "method_name": method_name,
            "params": params or {},
            "poll_result": poll_result,
        }
        if method_type:
            body["method_type"] = method_type
        if editor_session:
            body["editor_session"] = editor_session
        if timeout:
            body["timeout"] = timeout

        payload = self._request_json(
            "POST",
            f"workspaces/{workspace_id}/entities/{entity_id}/jobs/",
            json_body=body,
            action="Create job",
        )
        if not isinstance(payload, dict):
            raise TypeError("Create job did not return a JSON object.")
        return payload

    def read_job(self, job_url_or_id: str | int) -> dict[str, Any]:
        path = str(job_url_or_id)
        if path.isdigit():
            path = f"jobs/{path}/"
        payload = self._request_json("GET", path, action="Read job")
        if not isinstance(payload, dict):
            raise TypeError("Read job did not return a JSON object.")
        return payload

    def poll_job(
        self,
        job_url_or_id: str | int,
        *,
        max_poll_seconds: float = 120.0,
        initial_interval_seconds: float = 0.8,
        max_interval_seconds: float = 5.0,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + max_poll_seconds
        interval = initial_interval_seconds
        while time.monotonic() < deadline:
            payload = self.read_job(job_url_or_id)
            status = str(payload.get("status") or "").lower()
            if status == "success":
                return self._extract_job_result(payload)
            if status in FAILED_JOB_STATUSES:
                message = self._job_error_message(payload)
                if (
                    status == "error_user"
                    or self._job_error_type(payload) == "error_user"
                ):
                    raise ViktorJobUserError(message)
                raise RuntimeError(
                    f"VIKTOR job ended with status {status!r}: {message}"
                )
            time.sleep(interval)
            interval = min(interval * 1.5, max_interval_seconds)
        raise TimeoutError(f"Timed out polling VIKTOR job after {max_poll_seconds}s.")

    def run_entity_method(
        self,
        *,
        workspace_id: int,
        entity_id: int,
        method_name: str,
        params: dict[str, Any] | None = None,
        method_type: str | None = None,
        editor_session: str | None = None,
        timeout: int | None = None,
        max_poll_seconds: float = 120.0,
    ) -> dict[str, Any]:
        job = self.create_job(
            workspace_id=workspace_id,
            entity_id=entity_id,
            method_name=method_name,
            params=params,
            poll_result=False,
            method_type=method_type,
            editor_session=editor_session,
            timeout=timeout,
        )
        status = str(job.get("status") or "").lower()
        if status == "success":
            return self._extract_job_result(job)

        job_url = job.get("url")
        if isinstance(job_url, str) and job_url:
            return self.poll_job(job_url, max_poll_seconds=max_poll_seconds)

        job_id = job.get("uid") or job.get("id")
        if isinstance(job_id, (int, str)) and str(job_id):
            return self.poll_job(job_id, max_poll_seconds=max_poll_seconds)

        raise RuntimeError(
            f"Unexpected VIKTOR job creation response: {json.dumps(job, default=str)[:500]}"
        )

    @staticmethod
    def _extract_job_result(payload: dict[str, Any]) -> dict[str, Any]:
        for key in ("result", "content"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        if any(key in payload for key in JOB_RESULT_KEYS):
            return payload
        raise RuntimeError(
            "Successful VIKTOR job did not include a JSON result/content object. "
            f"Available keys: {', '.join(sorted(map(str, payload)))}."
        )

    @staticmethod
    def _job_error_message(payload: dict[str, Any]) -> str:
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            invalid_fields = error.get("invalid_fields")
            if message:
                if invalid_fields:
                    return f"{message} Invalid fields: {json.dumps(invalid_fields, default=str)[:300]}"
                return str(message)
        for key in ("error_message", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return json.dumps(payload, default=str)[:500]

    @staticmethod
    def _job_error_type(payload: dict[str, Any]) -> str | None:
        error = payload.get("error")
        if isinstance(error, dict):
            value = error.get("type")
            return str(value) if value else None
        return None

    def _create_entity_with_fallback_type(
        self,
        *,
        workspace_id: int,
        entity_type: int | str,
        fallback_entity_type: str | None,
        name: str,
        parent_entity_id: int | None,
    ) -> RestEntityResponse:
        try:
            return self._create_entity(
                workspace_id=workspace_id,
                entity_type=entity_type,
                name=name,
                parent_entity_id=parent_entity_id,
            )
        except RuntimeError:
            if not fallback_entity_type:
                raise
            return self._create_entity(
                workspace_id=workspace_id,
                entity_type=fallback_entity_type,
                name=name,
                parent_entity_id=parent_entity_id,
            )

    def _create_entity(
        self,
        *,
        workspace_id: int,
        entity_type: int | str,
        name: str,
        parent_entity_id: int | None,
    ) -> RestEntityResponse:
        body: dict[str, object] = {
            "entity_type": entity_type,
            "name": name,
            "properties": {},
        }
        path = (
            f"workspaces/{workspace_id}/entities/{parent_entity_id}/entities/"
            if parent_entity_id
            else f"workspaces/{workspace_id}/entities/"
        )
        payload = self._request_json(
            "POST", path, json_body=body, action="Create entity"
        )
        if isinstance(payload, list):
            if not payload:
                raise RuntimeError("Create entity returned an empty list.")
            payload = payload[0]
        return RestEntityResponse.model_validate(payload)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        action: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        allow_not_found: bool = False,
    ) -> Any | None:
        response = requests.request(
            method,
            self._url(path),
            headers={
                **self.auth_headers,
                **(
                    {"Content-Type": "application/json"}
                    if json_body is not None
                    else {}
                ),
            },
            params=params,
            json=json_body,
            timeout=self.timeout,
        )
        body = response.text[:500]
        if allow_not_found and response.status_code == 404:
            return None
        if (
            allow_not_found
            and response.status_code == 403
            and ("parent" in body.lower() or "tree" in body.lower())
        ):
            return None
        if response.ok:
            if not response.text.strip():
                return {}
            return response.json()
        raise RuntimeError(f"{action} failed (status={response.status_code}): {body}")

    def _url(self, path: str) -> str:
        if path.startswith(("https://", "http://")):
            return path
        normalized = path.lstrip("/")
        if normalized.startswith("api/"):
            normalized = normalized.removeprefix("api/")
        return f"{self.api_base}/{normalized}"


class WorkflowEntityStore:
    def __init__(self, *, storage_key: str = WORKFLOW_ENTITY_DIRECTORY_KEY) -> None:
        self.storage_key = storage_key

    def save(self, directory: WorkflowEntityDirectory) -> None:
        vkt.Storage().set(
            self.storage_key,
            data=vkt.File.from_data(directory.model_dump_json(indent=2)),
            scope=STORAGE_SCOPE,
        )

    def try_load(self) -> WorkflowEntityDirectory | None:
        try:
            stored_file = vkt.Storage().get(self.storage_key, scope=STORAGE_SCOPE)
            raw = stored_file.getvalue_binary().decode("utf-8")
            return WorkflowEntityDirectory.model_validate_json(raw)
        except (FileNotFoundError, RuntimeError, ValueError, TypeError, AttributeError):
            return None

    def load(self) -> WorkflowEntityDirectory:
        directory = self.try_load()
        if directory is None:
            raise FileNotFoundError(f"Missing VIKTOR Storage key '{self.storage_key}'.")
        return directory

    def delete(self) -> None:
        directory = self.try_load()
        if directory is not None:
            delete_workflow_run_storage(directory.run_id)
        try:
            vkt.Storage().delete(self.storage_key, scope=STORAGE_SCOPE)
        except (FileNotFoundError, RuntimeError, ValueError, AttributeError):
            return


class WorkflowGraphPublisher:
    def __init__(self, *, html_storage_key: str = WORKFLOW_HTML_STORAGE_KEY) -> None:
        self.html_storage_key = html_storage_key

    def publish(self, directory: WorkflowEntityDirectory) -> None:
        workflow = self._build_workflow(directory)
        state = build_canvas_state(directory.run_name, workflow)
        viewer = WorkflowViewer(lambda: state)
        save_canvas_state(state, run_id=directory.run_id)
        vkt.Storage().set(
            workflow_storage_key(self.html_storage_key, run_id=directory.run_id),
            data=vkt.File.from_data(
                json.dumps(
                    {
                        "workflow_name": directory.run_name,
                        "html": viewer.render_html(),
                    }
                )
            ),
            scope=STORAGE_SCOPE,
        )

    @staticmethod
    def _build_workflow(directory: WorkflowEntityDirectory) -> Workflow:
        included = set(directory.entities)
        return Workflow(
            nodes=[
                Node(
                    id=entity.node_id,
                    title=entity.label,
                    type=entity.node_id,
                    icon=entity.icon,
                    icon_bg=entity.icon_bg,
                    url=entity.url,
                    depends_on=[
                        Connection(node_id=dependency)
                        for dependency in entity.depends_on
                        if dependency in included
                    ],
                )
                for entity in directory.entities.values()
            ]
        )


class WorkflowEntityService:
    def __init__(
        self,
        *,
        registry: WorkflowAppRegistry | None = None,
        store: WorkflowEntityStore | None = None,
        client: ViktorRestEntityClient | None = None,
        graph_publisher: WorkflowGraphPublisher | None = None,
    ) -> None:
        self.registry = registry or DEFAULT_WORKFLOW_REGISTRY
        self.store = store or WorkflowEntityStore()
        self.client = client
        self.graph_publisher = graph_publisher or WorkflowGraphPublisher()

    def create_directory(
        self,
        *,
        run_name: str | None,
        include_nodes: list[WorkflowNodeId],
        include_dependencies: bool,
        replace_existing: bool,
    ) -> WorkflowEntityDirectory:
        existing = self.store.try_load()
        if existing and not replace_existing:
            raise WorkflowAlreadyExistsError(existing)

        resolved_run_name = self._resolve_run_name(run_name)
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        client = self.client or ViktorRestEntityClient()
        entities = {
            template.node_id: client.resolve_entity_from_template(
                template=template,
                run_name=resolved_run_name,
            )
            for template in self.registry.selected_templates(
                list(dict.fromkeys(include_nodes)),
                include_dependencies=include_dependencies,
            )
        }
        directory = WorkflowEntityDirectory(
            run_id=self._make_run_id(resolved_run_name),
            run_name=resolved_run_name,
            created_at=created_at,
            entities=entities,
        )
        if existing and replace_existing:
            delete_workflow_run_storage(existing.run_id)
        self.store.save(directory)
        self.graph_publisher.publish(directory)
        return directory

    def load_directory(self) -> WorkflowEntityDirectory:
        return self.store.load()

    def reset_directory(self) -> None:
        self.store.delete()

    def resolve_entity(self, node_id: WorkflowNodeId) -> WorkflowRunEntity:
        directory = self.load_directory()
        try:
            return directory.entities[node_id]
        except KeyError as exc:
            raise KeyError(
                f"Workflow run does not include node '{node_id}'. Create a new directory including this node."
            ) from exc

    def read_last_saved_params(self, target: WorkflowRunEntity) -> dict[str, Any]:
        entity = (self.client or ViktorRestEntityClient()).get_entity(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
            properties=True,
            clean_params=True,
            param_types=True,
        )
        for value in (entity.properties, entity.params, entity.last_saved_params):
            if isinstance(value, dict) and value:
                return value
        return {}

    def read_raw_saved_params(self, target: WorkflowRunEntity) -> dict[str, Any]:
        entity = (self.client or ViktorRestEntityClient()).get_entity(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
            properties=True,
            clean_params=False,
            param_types=False,
        )
        for value in (entity.properties, entity.params, entity.last_saved_params):
            if isinstance(value, dict):
                return value
        return {}

    def set_last_saved_params(
        self,
        target: WorkflowRunEntity,
        params: dict[str, Any],
        *,
        message: str,
    ) -> None:
        (self.client or ViktorRestEntityClient()).set_entity_params(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
            params=params,
            message=message,
        )

    @staticmethod
    def _resolve_run_name(value: str | None) -> str:
        return (value or default_run_name()).strip() or default_run_name()

    @staticmethod
    def _make_run_id(run_name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", run_name.lower()).strip("-")
        return f"{slug or 'workflow'}-{uuid4().hex[:8]}"


DEFAULT_WORKFLOW_REGISTRY = WorkflowAppRegistry.bhom_defaults()


def default_run_name() -> str:
    return f"BHoM Revit-to-LCA Run - {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}"


def get_workflow_entity_service() -> WorkflowEntityService:
    return WorkflowEntityService()


def try_load_entity_directory() -> WorkflowEntityDirectory | None:
    return WorkflowEntityStore().try_load()


def needs_workflow_run_response(*, tool: str, node_id: WorkflowNodeId) -> str:
    return tool_response(
        "needs_workflow_run",
        tool=tool,
        node_id=node_id,
        message=(
            "No active workflow entity directory includes this node. "
            "Create a workflow run first so the tool can resolve created entities and existing editor-service nodes."
        ),
        retry_action={
            "tool": "create_workflow_entity_directory",
            "reason": "Resolve entities for the required BHoM workflow nodes.",
        },
    )


async def create_workflow_entity_directory_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    try:
        payload = CreateWorkflowEntityDirectoryArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="create_workflow_entity_directory",
            message="Invalid workflow entity directory arguments.",
            error=exc,
            retry_tool="create_workflow_entity_directory",
            retry_reason="Retry with include_nodes containing known BHoM workflow node ids.",
        )

    try:
        directory = get_workflow_entity_service().create_directory(
            run_name=payload.run_name,
            include_nodes=payload.include_nodes,
            include_dependencies=payload.include_dependencies,
            replace_existing=payload.replace_existing,
        )
    except WorkflowAlreadyExistsError as exc:
        return tool_response(
            "workflow_exists",
            message=str(exc),
            run_name=exc.directory.run_name,
            directory_storage_key=WORKFLOW_ENTITY_DIRECTORY_KEY,
            retry_action={
                "tool": "create_workflow_entity_directory",
                "reason": "Retry with replace_existing=true to create a fresh workflow run.",
            },
        )
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return execution_error_response(
            tool="create_workflow_entity_directory",
            message="Could not resolve BHoM workflow entities.",
            error=exc,
        )

    created_nodes = [
        entity.node_id
        for entity in directory.entities.values()
        if entity.created_for_run
    ]
    service_nodes = [
        entity.node_id
        for entity in directory.entities.values()
        if entity.resolution == "configured_existing"
    ]
    fallback_nodes = [
        {
            "node_id": entity.node_id,
            "entity_id": entity.entity_id,
            "url": entity.url,
            "warning": entity.resolution_warning,
        }
        for entity in directory.entities.values()
        if entity.resolution == "fallback_existing"
    ]
    shared_param_nodes = [
        entity.node_id
        for entity in directory.entities.values()
        if entity.saved_params_are_shared
    ]
    return tool_response(
        "completed",
        message=(
            "Resolved the three deployed BHoM workflow entities. The node URLs are "
            "available so the user can open an app, save manual inputs or approvals, "
            "and tell the agent to read the node before continuing."
        ),
        run_name=directory.run_name,
        directory_storage_key=WORKFLOW_ENTITY_DIRECTORY_KEY,
        created_nodes=created_nodes,
        service_nodes=service_nodes,
        fallback_nodes=fallback_nodes,
        shared_param_nodes=shared_param_nodes,
        nodes=[entity.model_dump() for entity in directory.entities.values()],
    )


async def get_workflow_entity_directory_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    try:
        EmptyToolArgs.model_validate_json(args or "{}")
        directory = get_workflow_entity_service().load_directory()
    except FileNotFoundError:
        return tool_response(
            "needs_workflow_run",
            message="No active BHoM workflow entity directory exists.",
            retry_action={
                "tool": "create_workflow_entity_directory",
                "reason": "Resolve entities for the required BHoM workflow nodes.",
            },
        )
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return execution_error_response(
            tool="get_workflow_entity_directory",
            message="Could not read the BHoM workflow entity directory.",
            error=exc,
        )

    return tool_response(
        "completed",
        run_name=directory.run_name,
        directory_storage_key=WORKFLOW_ENTITY_DIRECTORY_KEY,
        nodes=[entity.model_dump() for entity in directory.entities.values()],
    )


async def reset_workflow_entity_directory_func(
    context: ToolContext[AgentContext], args: str
) -> str:
    try:
        payload = ResetWorkflowEntityDirectoryArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="reset_workflow_entity_directory",
            message="Invalid reset arguments.",
            error=exc,
            retry_tool="reset_workflow_entity_directory",
            retry_reason="Retry with confirm=true.",
        )

    if not payload.confirm:
        return tool_response(
            "confirmation_required",
            message="Set confirm=true to clear the active BHoM workflow entity directory.",
        )

    get_workflow_entity_service().reset_directory()
    return tool_response(
        "completed",
        message="BHoM workflow entity directory cleared.",
        cleared_storage_key=WORKFLOW_ENTITY_DIRECTORY_KEY,
    )
