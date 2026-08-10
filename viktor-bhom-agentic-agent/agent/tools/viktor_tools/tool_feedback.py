import json
from typing import Any

from pydantic import ValidationError


def tool_response(status: str, **payload: Any) -> str:
    return json.dumps({"status": status, **payload}, indent=2)


def validation_error_response(
    *,
    tool: str,
    message: str,
    error: Exception,
    retry_tool: str | None = None,
    retry_reason: str | None = None,
) -> str:
    details: Any
    if isinstance(error, ValidationError):
        details = error.errors()
    else:
        details = str(error)

    payload: dict[str, Any] = {
        "tool": tool,
        "message": message,
        "details": details,
    }
    if retry_tool:
        payload["retry_action"] = {
            "tool": retry_tool,
            "reason": retry_reason or "Correct the arguments and retry.",
        }
    return tool_response("validation_error", **payload)


def needs_prerequisite_response(
    *,
    tool: str,
    message: str,
    missing_storage_key: str,
    retry_tool: str,
    retry_reason: str,
) -> str:
    return tool_response(
        "needs_prerequisite",
        tool=tool,
        message=message,
        missing_storage_key=missing_storage_key,
        retry_action={
            "tool": retry_tool,
            "reason": retry_reason,
        },
    )


def execution_error_response(*, tool: str, message: str, error: Exception) -> str:
    return tool_response(
        "execution_error",
        tool=tool,
        message=message,
        error_type=type(error).__name__,
        details=str(error),
    )
