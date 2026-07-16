from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from .catalog import catalogue_source
from .contracts import ContractError

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "material-mapping.html"


def build_mapping_html(
    inventory: list[dict[str, Any]],
    mappings: dict[str, str],
    lookup: dict[str, Any],
) -> str:
    bootstrap = {
        "inventory": inventory,
        "mappings": mappings,
        "searches": lookup.get("searches", []),
        "source": catalogue_source(lookup),
        "status": lookup.get("status", "not_searched"),
    }
    encoded = base64.b64encode(
        json.dumps(bootstrap, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")

    sdk_root = os.environ.get("VIKTOR_JS_SDK_PATH")
    if not sdk_root:
        raise ContractError(
            "VIKTOR_JS_SDK_PATH is unavailable. Open this view through VIKTOR."
        )

    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = html.replace("BOOTSTRAP_BASE64", encoded)
    return html.replace("VIKTOR_JS_SDK", sdk_root + "v1.js")
