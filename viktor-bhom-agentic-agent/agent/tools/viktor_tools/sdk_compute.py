"""Execute VIKTOR app methods through the Python SDK compute adapter"""

import os
from typing import Any

import viktor as vkt
from dotenv import load_dotenv

load_dotenv()


def get_required_token() -> str:
    token = os.getenv("TOKEN_VK_APP") or os.getenv("VIKTOR_TOKEN")
    if not token or not token.strip():
        raise ValueError("Missing VIKTOR token. Set TOKEN_VK_APP or VIKTOR_TOKEN.")
    return token.strip()


def normalize_sdk_environment(value: str) -> str:
    environment = value.strip().rstrip("/").lower()
    if not environment:
        raise ValueError("Missing VIKTOR environment.")
    if environment.startswith(("http://", "https://")) or "/" in environment:
        raise ValueError("ENV_VKT must be the host only, for example demo.viktor.ai.")
    if not environment.endswith(".viktor.ai"):
        raise ValueError(
            "ENV_VKT must end with .viktor.ai, for example demo.viktor.ai."
        )
    return environment


def get_optional_environment() -> str | None:
    environment = os.getenv("ENV_VKT") or os.getenv("VIKTOR_ENVIRONMENT")
    if environment and environment.strip():
        return normalize_sdk_environment(environment)
    return None


class ViktorSdkComputeClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        environment: str | None = None,
    ) -> None:
        resolved_token = (token or get_required_token()).strip()
        resolved_environment = (
            normalize_sdk_environment(environment)
            if environment and environment.strip()
            else get_optional_environment()
        )

        if resolved_environment:
            self.api = vkt.api_v1.API(
                token=resolved_token,
                environment=resolved_environment,
            )
        else:
            self.api = vkt.api_v1.API(token=resolved_token)

    def compute_method(
        self,
        *,
        workspace_id: int,
        entity_id: int,
        method_name: str,
        params: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        workspace = self.api.get_workspace(workspace_id)
        entity = workspace.get_entity(entity_id)
        result = entity.compute(method_name, params=params, timeout=timeout)
        if not isinstance(result, dict):
            raise TypeError(
                f"VIKTOR SDK compute did not return a JSON object: {result}"
            )
        return result


def select_result_key(result: dict[str, Any], result_key: str) -> Any:
    if result_key not in result:
        keys = ", ".join(sorted(result.keys())) or "<none>"
        raise KeyError(
            f"Result does not contain key '{result_key}'. Available keys: {keys}."
        )
    return result[result_key]
