from __future__ import annotations

import json
from typing import Final

import viktor as vkt
from viktor.external.generic import GenericAnalysis

from .file_io import to_utf8_text

OUTPUT_FILENAMES: Final[tuple[str, ...]] = (
    "analysis-result.json",
    "bhom-results.json",
    "analysis-events.json",
    "runtime-manifest.json",
)
EXECUTABLE_KEY: Final[str] = "bhom_lca"
CACHE_VERSION: Final[str] = "lca-service-contract-1.0-gateway-1.0"


@vkt.memoize
def execute_worker(
    *,
    request_json: str,
    takeoff_json: str,
    template_materials_json: str,
    timeout_seconds: int,
    cache_version: str,
) -> dict[str, str]:
    """Execute one deterministic gateway job and return UTF-8 output text."""
    if cache_version != CACHE_VERSION:
        raise ValueError(f"Unsupported cache version: {cache_version}")

    analysis = GenericAnalysis(
        files=[
            (
                "analysis-request.json",
                vkt.File.from_data(request_json.encode("utf-8")),
            ),
            (
                "takeoff.bhom.json",
                vkt.File.from_data(takeoff_json.encode("utf-8")),
            ),
            (
                "template-materials.bhom.json",
                vkt.File.from_data(template_materials_json.encode("utf-8")),
            ),
        ],
        executable_key=EXECUTABLE_KEY,
        output_filenames=list(OUTPUT_FILENAMES),
    )
    analysis.execute(timeout=timeout_seconds)

    outputs: dict[str, str] = {}
    for filename in OUTPUT_FILENAMES:
        outputs[filename] = to_utf8_text(analysis.get_output_file(filename))

    # Parse every declared output now so malformed output fails at the boundary.
    for filename, text in outputs.items():
        try:
            json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"Worker output '{filename}' is not valid JSON: {error.msg}"
            ) from error

    return outputs
