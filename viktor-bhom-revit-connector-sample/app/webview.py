from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Final

TEMPLATE: Final[Path] = Path(__file__).resolve().parent / "templates" / "model-explorer.html"


def build_model_explorer(metadata: dict[str, Any]) -> str:
    encoded = base64.b64encode(
        json.dumps(metadata, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    return TEMPLATE.read_text(encoding="utf-8").replace("MODEL_DATA_BASE64", encoded)
