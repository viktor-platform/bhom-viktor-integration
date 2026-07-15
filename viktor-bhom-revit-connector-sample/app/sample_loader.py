from __future__ import annotations

from pathlib import Path
from typing import Final

from .contracts import GatewayResult, validate_gateway_outputs

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SAMPLES: Final[Path] = ROOT / "samples"
OUTPUT_FILENAMES: Final[tuple[str, ...]] = (
    "revit-metadata.json",
    "revit-elements.bhom.json",
    "takeoff.bhom.json",
    "revit-events.json",
    "runtime-manifest.json",
)


def load_bundled_sample() -> GatewayResult:
    outputs = {
        filename: (SAMPLES / filename).read_text(encoding="utf-8")
        for filename in OUTPUT_FILENAMES
    }
    return validate_gateway_outputs(outputs)
