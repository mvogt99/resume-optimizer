#!/usr/bin/env python3
"""Schema Gate — Route schema coverage checker and validator.

Implements the Schema Gate from Section 3.2 of the Quality Roadmap.

Usage:
    python scripts/schema_guard.py coverage   # show coverage % + missing routes
    python scripts/schema_guard.py validate   # validate all schemas are parseable
    python scripts/schema_guard.py --report   # write roadmap/SCHEMA_COVERAGE_REPORT.md
    python scripts/schema_guard.py --gate     # exit 1 if coverage < threshold
"""

import importlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROADMAP_DIR = BACKEND_DIR.parent / "roadmap"

# Ensure backend/ is importable
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


def load_schemas():
    """Load the SCHEMAS dict from the schemas package."""
    import schemas

    importlib.reload(schemas)
    return schemas.SCHEMAS


# ---------------------------------------------------------------------------
# Route inventory — parse Flask blueprints
# ---------------------------------------------------------------------------


def get_route_inventory():
    """Parse route files to discover all API routes. Returns list of (method, path)."""
    routes = []

    # Parse all route files in routes/ directory
    routes_dir = BACKEND_DIR / "routes"
    if routes_dir.exists():
        for route_file in routes_dir.glob("*_routes.py"):
            routes.extend(_parse_route_file(route_file))

    # Parse agents_routes.py
    agents_file = BACKEND_DIR / "agents_routes.py"
    if agents_file.exists():
        routes.extend(_parse_route_file(agents_file))

    return sorted(set(routes))


def _parse_route_file(filepath):
    """Parse a Flask route file and extract (method, path) tuples."""
    source = filepath.read_text(encoding="utf-8")
    routes = []

    # Match @blueprint.route("/api/...", methods=["GET", "POST"])
    pattern = re.compile(
        r'@\w+\.route\(\s*["\']([^"\']+)["\']\s*' r"(?:,\s*methods\s*=\s*\[([^\]]+)\])?\s*\)",
        re.MULTILINE,
    )

    for match in pattern.finditer(source):
        path = match.group(1)
        methods_str = match.group(2)
        if methods_str:
            methods = [m.strip().strip('"').strip("'") for m in methods_str.split(",")]
        else:
            methods = ["GET"]
        for method in methods:
            routes.append((method.upper(), path))

    return routes


# ---------------------------------------------------------------------------
# Coverage analysis
# ---------------------------------------------------------------------------


def check_coverage():
    """Check schema coverage against route inventory.

    Returns dict with {covered, total, missing, coverage_pct}.
    """
    schemas = load_schemas()
    routes = get_route_inventory()

    # Schema keys are (method, path, status_code) — extract (method, path) for coverage
    schema_routes = {(m, p) for m, p, _ in schemas.keys()}

    covered = []
    missing = []

    for method, path in routes:
        # Normalize path for comparison (Flask uses <int:id> syntax)
        normalized = _normalize_path(path)
        if (method, normalized) in schema_routes or (method, path) in schema_routes:
            covered.append((method, path))
        else:
            missing.append((method, path))

    total = len(routes)
    return {
        "covered": len(covered),
        "total": total,
        "missing": [(m, p) for m, p in missing],
        "covered_routes": [(m, p) for m, p in covered],
        "coverage_pct": round((len(covered) / max(total, 1)) * 100, 1),
    }


def _normalize_path(path):
    """Normalize Flask path params for schema lookup.

    Converts /api/x/<int:id> to /api/x/<id> for matching.
    """
    return re.sub(r"<(?:int|string):(\w+)>", r"<\1>", path)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def validate_response(method, path, status_code, body):
    """Validate a response body against its schema. Returns list of errors.

    Returns empty list if valid or if no schema is defined (pass-through).
    """
    schemas = load_schemas()

    # Try exact match first
    schema = schemas.get((method, path, status_code))
    if schema is None:
        # Try normalized path
        normalized = _normalize_path(path)
        schema = schemas.get((method, normalized, status_code))

    if schema is None:
        return []  # No schema defined — pass-through

    return _validate_against_schema(body, schema, path_prefix="")


def _validate_against_schema(data, schema, path_prefix=""):
    """Simple JSON Schema validation (no external dependency required).

    For full validation, use jsonschema library. This provides basic checks.
    """
    errors = []
    schema_type = schema.get("type")

    if schema_type == "object":
        if not isinstance(data, dict):
            errors.append(f"{path_prefix}: expected object, got {type(data).__name__}")
            return errors

        # Check required fields
        for req in schema.get("required", []):
            if req not in data:
                errors.append(f"{path_prefix}.{req}: required field missing")

        # Check property types
        for prop_name, prop_schema in schema.get("properties", {}).items():
            if prop_name in data:
                prop_errors = _validate_type(
                    data[prop_name], prop_schema, f"{path_prefix}.{prop_name}"
                )
                errors.extend(prop_errors)

    elif schema_type == "array" and not isinstance(data, list):
        errors.append(f"{path_prefix}: expected array, got {type(data).__name__}")

    return errors


def _validate_type(value, schema, path):
    """Validate a value against a type schema."""
    errors = []
    expected = schema.get("type")
    if expected is None:
        return errors

    if isinstance(expected, list):
        # Union type e.g. ["string", "integer"]
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        valid = any(isinstance(value, type_map.get(t, object)) for t in expected)
        if not valid:
            errors.append(f"{path}: expected one of {expected}, got {type(value).__name__}")
    else:
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        expected_type = type_map.get(expected)
        if expected_type and not isinstance(value, expected_type):
            # Allow int for number
            if expected == "number" and isinstance(value, (int, float)):
                pass
            else:
                errors.append(f"{path}: expected {expected}, got {type(value).__name__}")

    return errors


def validate_all_schemas():
    """Validate that all schema definitions are well-formed."""
    schemas = load_schemas()
    issues = []

    for key, schema in schemas.items():
        method, path, code = key
        if not isinstance(schema, dict):
            issues.append(f"({method}, {path}, {code}): schema is not a dict")
            continue
        if "type" not in schema:
            issues.append(f"({method}, {path}, {code}): missing 'type' field")

    return issues


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def write_report(output_path=None):
    """Write SCHEMA_COVERAGE_REPORT.md."""
    output_path = Path(output_path) if output_path else ROADMAP_DIR / "SCHEMA_COVERAGE_REPORT.md"
    coverage = check_coverage()
    issues = validate_all_schemas()

    lines = [
        "# Schema Coverage Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Coverage:** {coverage['coverage_pct']}%"
        f" ({coverage['covered']}/{coverage['total']} routes)",
        "",
        "## Covered Routes",
        "",
        "| Method | Path |",
        "|--------|------|",
    ]

    for method, path in sorted(coverage["covered_routes"]):
        lines.append(f"| {method} | {path} |")

    if coverage["missing"]:
        lines.extend(
            [
                "",
                "## Missing Schemas",
                "",
                "| Method | Path |",
                "|--------|------|",
            ]
        )
        for method, path in sorted(coverage["missing"]):
            lines.append(f"| {method} | {path} |")

    if issues:
        lines.extend(
            [
                "",
                "## Schema Validation Issues",
                "",
            ]
        )
        for issue in issues:
            lines.append(f"- {issue}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    args = sys.argv[1:]

    if not args or "coverage" in args:
        coverage = check_coverage()
        print("\n=== Schema Coverage ===")
        print(
            f"Coverage: {coverage['coverage_pct']}%"
            f" ({coverage['covered']}/{coverage['total']} routes)"
        )

        if coverage["missing"]:
            print(f"\nMissing schemas ({len(coverage['missing'])}):")
            for method, path in sorted(coverage["missing"]):
                print(f"  {method:6} {path}")
        else:
            print("\nAll routes have schemas!")

        if "--report" in args:
            path = write_report()
            print(f"\nReport written to {path}")

    elif "validate" in args:
        issues = validate_all_schemas()
        if issues:
            print("Schema validation issues:")
            for issue in issues:
                print(f"  {issue}")
            sys.exit(1)
        else:
            print("All schemas valid.")

    if "--gate" in args:
        coverage = check_coverage()
        if coverage["coverage_pct"] < 50:
            print(f"Schema Gate: FAIL — coverage {coverage['coverage_pct']}% < 50%")
            sys.exit(1)
        else:
            print(f"Schema Gate: PASS — coverage {coverage['coverage_pct']}%")
            sys.exit(0)


if __name__ == "__main__":
    main()
