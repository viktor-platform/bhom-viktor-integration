from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate BHoM LCA service samples against a local BHoM_JSONSchema clone."
        )
    )
    parser.add_argument(
        "--schema-root",
        type=Path,
        required=True,
        help="Path to the root of the cloned BHoM_JSONSchema repository.",
    )
    parser.add_argument(
        "--takeoff",
        type=Path,
        required=True,
        help="Path to one GeneralMaterialTakeoff JSON object.",
    )
    parser.add_argument(
        "--materials",
        type=Path,
        required=True,
        help="Path to an array of Material JSON objects.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "contracts"
        / "bhom-schema-manifest.json",
        help="Path to the service BHoM schema manifest.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError(f"File not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {path} at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error


def local_uri(path: Path) -> str:
    return "file:///" + quote(path.resolve().as_posix().lstrip("/"))


def build_registry(schema_root: Path) -> tuple[Registry, dict[str, dict[str, Any]]]:
    if not schema_root.is_dir():
        raise ValueError(f"Schema root is not a directory: {schema_root}")

    registry = Registry()
    documents: dict[str, dict[str, Any]] = {}
    schema_files = sorted(schema_root.rglob("*.json"))
    if not schema_files:
        raise ValueError(f"No JSON schemas were found under {schema_root}")

    for schema_path in schema_files:
        document = read_json(schema_path)
        if not isinstance(document, dict):
            continue
        resource = Resource.from_contents(document)
        uri = document.get("$id")
        if isinstance(uri, str) and uri:
            registry = registry.with_resource(uri, resource)
            documents[uri] = document
        registry = registry.with_resource(local_uri(schema_path), resource)

    return registry, documents


def json_path(parts: list[Any]) -> str:
    value = "$"
    for part in parts:
        value += f"[{part}]" if isinstance(part, int) else f".{part}"
    return value


def validate_instance(
    *,
    label: str,
    instance: Any,
    schema_path: Path,
    registry: Registry,
) -> list[str]:
    schema = read_json(schema_path)
    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(
        validator.iter_errors(instance), key=lambda item: list(item.absolute_path)
    )
    return [
        f"{label} {json_path(list(error.absolute_path))}: {error.message}"
        for error in errors
    ]


def main() -> int:
    args = parse_arguments()
    try:
        schema_root = args.schema_root.resolve()
        manifest = read_json(args.manifest)
        schema_paths = manifest["schemas"]
        registry, _ = build_registry(schema_root)
        takeoff = read_json(args.takeoff)
        materials = read_json(args.materials)

        errors: list[str] = []
        errors.extend(
            validate_instance(
                label="takeoff",
                instance=takeoff,
                schema_path=schema_root / schema_paths["takeoff"],
                registry=registry,
            )
        )

        if not isinstance(materials, list):
            errors.append("materials $: expected a JSON array")
        else:
            material_schema = schema_root / schema_paths["material"]
            for index, material in enumerate(materials):
                errors.extend(
                    validate_instance(
                        label=f"materials[{index}]",
                        instance=material,
                        schema_path=material_schema,
                        registry=registry,
                    )
                )

        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1

        print(f"Validated takeoff: {args.takeoff}")
        print(f"Validated material templates: {args.materials}")
        print(f"Schema repository: {schema_root}")
        return 0
    except (KeyError, TypeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
