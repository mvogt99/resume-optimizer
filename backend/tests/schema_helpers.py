"""Test helper: assert_schema() for validating API responses against JSON schemas.

Usage in tests:
    from schema_helpers import assert_schema
    assert_schema("POST", "/api/register", 201, resp.get_json())
"""

import sys
from pathlib import Path

# Ensure backend/ is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schemas import SCHEMAS  # noqa: E402


def assert_schema(method, path, status_code, body):
    """Validate response against schema. AssertionError on mismatch.

    No-op if route has no schema defined yet (pass-through).
    """
    schema = SCHEMAS.get((method, path, status_code))
    if schema is None:
        return  # No schema for this route — pass-through

    if not isinstance(body, dict):
        raise AssertionError(
            f"Schema validation failed for {method} {path} {status_code}: "
            f"expected dict, got {type(body).__name__}"
        )

    # Check required fields
    for req in schema.get("required", []):
        if req not in body:
            raise AssertionError(
                f"Schema validation failed for {method} {path} {status_code}: "
                f"missing required field '{req}'"
            )

    # Check property types
    properties = schema.get("properties", {})
    for prop_name, prop_schema in properties.items():
        if prop_name not in body:
            continue

        value = body[prop_name]
        expected_type = prop_schema.get("type")
        if expected_type is None:
            continue

        if not _check_type(value, expected_type):
            raise AssertionError(
                f"Schema validation failed for {method} {path} {status_code}: "
                f"field '{prop_name}' expected type {expected_type}, "
                f"got {type(value).__name__} (value: {value!r})"
            )

    # Check additionalProperties
    if schema.get("additionalProperties") is False:
        allowed = set(properties.keys())
        extra = set(body.keys()) - allowed
        if extra:
            raise AssertionError(
                f"Schema validation failed for {method} {path} {status_code}: "
                f"unexpected fields {extra} (additionalProperties=false)"
            )


def _check_type(value, expected):
    """Check if value matches JSON Schema type(s)."""
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    if isinstance(expected, list):
        return any(isinstance(value, type_map.get(t, object)) for t in expected)

    return isinstance(value, type_map.get(expected, object))
