from __future__ import annotations

import json
from typing import Final

import viktor as vkt
from viktor.external.generic import GenericAnalysis

from .contracts import GatewayResult, PullRequest, validate_gateway_outputs
from .sample_loader import OUTPUT_FILENAMES, load_bundled_sample

EXECUTABLE_KEY: Final[str] = "bhom_revit"
CACHE_VERSION: Final[str] = "revit-producer-contract-1.0-gateway-0.1"


def _file_to_text(value: object, *, label: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8")
    getter = getattr(value, "getvalue", None)
    if callable(getter):
        content = getter()
        if isinstance(content, bytes):
            return content.decode("utf-8")
        return str(content)
    reader = getattr(value, "read", None)
    if callable(reader):
        content = reader()
        if isinstance(content, bytes):
            return content.decode("utf-8")
        return str(content)
    raise RuntimeError(f"Could not read {label} as UTF-8 text.")


@vkt.memoize
def execute_worker(
    *,
    request_json: str,
    timeout_seconds: int,
    cache_version: str,
) -> dict[str, str]:
    """Run the fixed Windows gateway executable through VIKTOR Generic Worker."""
    if cache_version != CACHE_VERSION:
        raise ValueError(f"Unsupported cache version: {cache_version}")

    analysis = GenericAnalysis(
        files=[
            (
                "revit-pull-request.json",
                vkt.File.from_data(request_json.encode("utf-8")),
            )
        ],
        executable_key=EXECUTABLE_KEY,
        output_filenames=list(OUTPUT_FILENAMES),
    )
    analysis.execute(timeout=timeout_seconds)

    outputs: dict[str, str] = {}
    for filename in OUTPUT_FILENAMES:
        outputs[filename] = _file_to_text(
            analysis.get_output_file(filename),
            label=filename,
        )
        try:
            json.loads(outputs[filename])
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"Worker output '{filename}' is not valid JSON: {error.msg}"
            ) from error
    return outputs


def pull_model(
    *,
    request: PullRequest,
    timeout_seconds: int = 300,
) -> GatewayResult:
    outputs = execute_worker(
        request_json=request.to_json(),
        timeout_seconds=timeout_seconds,
        cache_version=CACHE_VERSION,
    )
    return validate_gateway_outputs(outputs)


__all__ = [
    "CACHE_VERSION",
    "EXECUTABLE_KEY",
    "OUTPUT_FILENAMES",
    "execute_worker",
    "load_bundled_sample",
    "pull_model",
]
