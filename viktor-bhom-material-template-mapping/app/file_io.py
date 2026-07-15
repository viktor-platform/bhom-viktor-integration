from __future__ import annotations

from contextlib import closing
from typing import Any


class FileReadError(ValueError):
    """Raised when a VIKTOR file-like value cannot be read."""


def to_bytes(value: Any) -> bytes:
    if value is None:
        raise FileReadError("No file value was provided.")
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")

    nested_file = getattr(value, "file", None)
    if nested_file is not None and nested_file is not value:
        return to_bytes(nested_file)

    getter = getattr(value, "getvalue", None)
    if callable(getter):
        data = getter()
        return data if isinstance(data, bytes) else str(data).encode("utf-8")

    for method_name in ("open_binary", "open"):
        opener = getattr(value, method_name, None)
        if callable(opener):
            resource = opener()
            with closing(resource) as stream:
                data = stream.read()
            return data if isinstance(data, bytes) else str(data).encode("utf-8")

    reader = getattr(value, "read", None)
    if callable(reader):
        data = reader()
        return data if isinstance(data, bytes) else str(data).encode("utf-8")

    raise FileReadError(f"Unsupported file value type: {type(value).__name__}")


def to_utf8_text(value: Any) -> str:
    return to_bytes(value).decode("utf-8-sig")
