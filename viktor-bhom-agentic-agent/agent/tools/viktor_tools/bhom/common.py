import copy
import json
from typing import Any

import viktor as vkt

STORAGE_SCOPE = "entity"
WORKFLOW_RUNS_STORAGE_PREFIX = "workflow_runs"

REVIT_CONNECTOR_STORAGE_KEY = "bhom_revit_takeoff"
MATERIAL_TEMPLATE_MAPPING_STORAGE_KEY = "bhom_material_template"
LCA_ANALYSIS_STORAGE_KEY = "bhom_lca_result"
WORKFLOW_HTML_STORAGE_KEY = "workflow_html"
WORKFLOW_GRAPH_STATE_STORAGE_KEY = "workflow_graph_state"
WORKFLOW_RUN_STORAGE_KEYS = (
    REVIT_CONNECTOR_STORAGE_KEY,
    MATERIAL_TEMPLATE_MAPPING_STORAGE_KEY,
    LCA_ANALYSIS_STORAGE_KEY,
    WORKFLOW_HTML_STORAGE_KEY,
    WORKFLOW_GRAPH_STATE_STORAGE_KEY,
)


def active_workflow_run_id() -> str | None:
    try:
        from agent.tools.viktor_tools.workflow.entity_ops import (
            try_load_entity_directory,
        )

        directory = try_load_entity_directory()
    except (FileNotFoundError, RuntimeError, ValueError, TypeError, AttributeError):
        return None
    if not directory:
        return None
    return directory.run_id


def workflow_storage_key(key: str, *, run_id: str | None = None) -> str:
    if key.startswith(f"{WORKFLOW_RUNS_STORAGE_PREFIX}/"):
        return key
    resolved_run_id = run_id or active_workflow_run_id() or "current"
    return f"{WORKFLOW_RUNS_STORAGE_PREFIX}/{resolved_run_id}/{key}"


def write_json_to_storage(
    key: str,
    payload: Any,
    *,
    run_id: str | None = None,
    namespace_active_run: bool = True,
) -> str:
    storage_key = (
        workflow_storage_key(key, run_id=run_id) if namespace_active_run else key
    )
    vkt.Storage().set(
        storage_key,
        data=vkt.File.from_data(json.dumps(payload, indent=2, default=str)),
        scope=STORAGE_SCOPE,
    )
    return storage_key


def read_json_from_storage(
    key: str,
    *,
    run_id: str | None = None,
    namespace_active_run: bool = True,
) -> Any:
    storage_key = (
        workflow_storage_key(key, run_id=run_id) if namespace_active_run else key
    )
    candidate_keys = [storage_key]
    if storage_key != key:
        candidate_keys.append(key)

    for candidate_key in candidate_keys:
        try:
            stored_file = vkt.Storage().get(candidate_key, scope=STORAGE_SCOPE)
        except (FileNotFoundError, RuntimeError, ValueError, AttributeError):
            stored_file = None
        if stored_file:
            return json.loads(stored_file.getvalue_binary().decode("utf-8"))
    raise FileNotFoundError(f"Missing VIKTOR Storage key '{storage_key}'.")


def try_read_json_from_storage(key: str) -> Any | None:
    try:
        return read_json_from_storage(key)
    except (
        FileNotFoundError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        json.JSONDecodeError,
    ):
        return None


def delete_storage_key(
    key: str,
    *,
    run_id: str | None = None,
    namespace_active_run: bool = True,
) -> None:
    storage_key = (
        workflow_storage_key(key, run_id=run_id) if namespace_active_run else key
    )
    candidate_keys = [storage_key]
    if storage_key != key:
        candidate_keys.append(key)
    for candidate_key in candidate_keys:
        _try_delete(candidate_key)


def _try_delete(key: str) -> bool:
    try:
        vkt.Storage().delete(key, scope=STORAGE_SCOPE)
    except (FileNotFoundError, RuntimeError, ValueError, AttributeError):
        return False
    return True


def delete_workflow_run_storage(run_id: str | None) -> None:
    if run_id:
        prefix = f"{WORKFLOW_RUNS_STORAGE_PREFIX}/{run_id}/"
        deleted_listed_keys = False
        try:
            for item in vkt.Storage().list(prefix=prefix, scope=STORAGE_SCOPE):
                key = getattr(item, "key", None)
                if key is None and isinstance(item, dict):
                    key = item.get("key") or item.get("name")
                if key:
                    vkt.Storage().delete(str(key), scope=STORAGE_SCOPE)
                    deleted_listed_keys = True
        except (FileNotFoundError, RuntimeError, ValueError, AttributeError):
            deleted_listed_keys = False
        if not deleted_listed_keys:
            for key in WORKFLOW_RUN_STORAGE_KEYS:
                delete_storage_key(key, run_id=run_id)

    for key in WORKFLOW_RUN_STORAGE_KEYS:
        delete_storage_key(key, namespace_active_run=False)


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def paths_for_patch(payload: Any, prefix: str = "") -> list[str]:
    if isinstance(payload, dict):
        paths: list[str] = []
        for key, value in payload.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(paths_for_patch(value, child_prefix))
        return paths
    return [prefix]


def leaf_value(item: Any) -> Any:
    if isinstance(item, dict):
        if "value" in item:
            return item.get("value")
        if "display_value" in item:
            return item.get("display_value")
    return item


def normalize_header(header: Any) -> str:
    title = header.get("title") if isinstance(header, dict) else header
    return str(title or "").split("[", 1)[0].strip().lower().replace(" ", "_")


def parse_table_rows(table: Any) -> list[dict[str, Any]]:
    if isinstance(table, list):
        return [dict(row) for row in table if isinstance(row, dict)]
    if not isinstance(table, dict):
        return []

    headers = table.get("column_headers") or table.get("headers") or []
    data_rows = table.get("data") or table.get("rows") or []
    normalized_headers = [normalize_header(header) for header in headers]
    rows: list[dict[str, Any]] = []
    for data_row in data_rows:
        if isinstance(data_row, dict):
            rows.append(dict(data_row))
            continue
        if not isinstance(data_row, list):
            continue
        rows.append(
            {
                normalized_headers[index] or f"col_{index}": leaf_value(cell)
                for index, cell in enumerate(data_row)
                if index < len(normalized_headers)
            }
        )
    return rows


def as_number(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return default
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def first_number_in_payload(
    payload: Any, candidate_keys: tuple[str, ...]
) -> float | None:
    if isinstance(payload, dict):
        for key in candidate_keys:
            if key in payload:
                number = as_number(payload[key])
                if number is not None:
                    return number
        for value in payload.values():
            number = first_number_in_payload(value, candidate_keys)
            if number is not None:
                return number
    elif isinstance(payload, list):
        for item in payload:
            number = first_number_in_payload(item, candidate_keys)
            if number is not None:
                return number
    return None
