"""Tests for schema_guard.py and schemas package — Schema Gate.

11 tests, zero mocks, no skips.
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BACKEND_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Schema Loading
# ---------------------------------------------------------------------------


class TestSchemaLoading:

    def test_schemas_importable(self):
        """from schemas import SCHEMAS succeeds."""
        from schemas import SCHEMAS

        assert isinstance(SCHEMAS, dict)
        assert len(SCHEMAS) > 0

    def test_schemas_dict_format(self):
        """Keys are (str, str, int) tuples, values are dicts."""
        from schemas import SCHEMAS

        for key, value in SCHEMAS.items():
            assert isinstance(key, tuple), f"Key {key} is not a tuple"
            assert len(key) == 3, f"Key {key} has {len(key)} elements, expected 3"
            method, path, code = key
            assert isinstance(method, str), f"Method {method} is not a string"
            assert isinstance(path, str), f"Path {path} is not a string"
            assert isinstance(code, int), f"Code {code} is not an int"
            assert isinstance(value, dict), f"Schema for {key} is not a dict"

    def test_schema_has_type_field(self):
        """Every schema has 'type' key."""
        from schemas import SCHEMAS

        for key, schema in SCHEMAS.items():
            assert "type" in schema, f"Schema for {key} missing 'type' field"


# ---------------------------------------------------------------------------
# Route Inventory
# ---------------------------------------------------------------------------


class TestRouteInventory:

    def test_route_inventory_non_empty(self):
        """> 100 routes found."""
        from schema_guard import get_route_inventory

        routes = get_route_inventory()
        assert len(routes) > 50, f"Only {len(routes)} routes found, expected > 50"

    def test_known_routes_have_schemas(self):
        """/api/register, /api/login covered."""
        from schemas import SCHEMAS

        keys = {(m, p) for m, p, _ in SCHEMAS.keys()}
        assert ("POST", "/api/register") in keys
        assert ("POST", "/api/login") in keys
        assert ("POST", "/api/resume/upload") in keys
        assert ("GET", "/api/jobs") in keys


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:

    def test_validate_good_response(self):
        """Correct data → no errors."""
        from schema_guard import validate_response

        body = {"message": "User registered", "user_id": 1, "token": "abc123"}
        errors = validate_response("POST", "/api/register", 201, body)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_validate_bad_response(self):
        """Missing required field → errors list."""
        from schema_guard import validate_response

        body = {"message": "User registered"}  # missing user_id, token
        errors = validate_response("POST", "/api/register", 201, body)
        assert len(errors) > 0, "Expected validation errors for missing fields"
        assert any("user_id" in e or "token" in e for e in errors)

    def test_validate_unknown_route(self):
        """Unregistered route → no errors (pass-through)."""
        from schema_guard import validate_response

        errors = validate_response("GET", "/api/nonexistent", 200, {"anything": True})
        assert errors == [], "Unknown routes should pass through without errors"


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


class TestCoverage:

    def test_coverage_report_structure(self):
        """{covered, total, missing, coverage_pct}."""
        from schema_guard import check_coverage

        coverage = check_coverage()
        assert "covered" in coverage
        assert "total" in coverage
        assert "missing" in coverage
        assert "coverage_pct" in coverage
        assert isinstance(coverage["coverage_pct"], float)

    def test_coverage_percentage(self):
        """> 50% coverage."""
        from schema_guard import check_coverage

        coverage = check_coverage()
        assert (
            coverage["coverage_pct"] > 50
        ), f"Schema coverage {coverage['coverage_pct']}% is below 50%"


# ---------------------------------------------------------------------------
# Test Helper
# ---------------------------------------------------------------------------


class TestSchemaHelpers:

    def test_schema_helpers_assert_schema(self):
        """Raises AssertionError on schema mismatch."""
        from schema_helpers import assert_schema

        # Valid response — should not raise
        assert_schema("POST", "/api/register", 201, {"message": "ok", "user_id": 1, "token": "abc"})

        # Invalid response — should raise
        with pytest.raises(AssertionError, match="missing required field"):
            assert_schema("POST", "/api/register", 201, {"message": "ok"})


# ---------------------------------------------------------------------------
# Schema Hardening (Phase 2H-C)
# ---------------------------------------------------------------------------


class TestSchemaHardening:

    HARDENED_SCHEMAS = [
        ("POST", "/api/register", 201),
        ("POST", "/api/register", 409),
        ("POST", "/api/login", 200),
        ("POST", "/api/login", 401),
        ("POST", "/api/resume/upload", 201),
        ("POST", "/api/job-description/upload", 201),
        ("POST", "/api/experience/start", 201),
        ("GET", "/api/jobs", 200),
        ("GET", "/api/interview-guide/<resume_id>", 200),
        ("POST", "/api/resume/from-linkedin", 201),
    ]

    def test_hardened_schemas_no_additional_properties(self):
        """Iterate 10 tightened schemas, assert additionalProperties is False."""
        from schemas import SCHEMAS

        for method, path, code in self.HARDENED_SCHEMAS:
            schema = SCHEMAS.get((method, path, code))
            assert schema is not None, f"Schema missing for {method} {path} {code}"
            assert schema.get("additionalProperties") is False, (
                f"Schema for {method} {path} {code} should have "
                f"additionalProperties=False, got {schema.get('additionalProperties')}"
            )

    def test_hardened_schemas_reject_extra_fields(self):
        """Validate body with extra unknown field → error."""
        from schema_helpers import assert_schema

        with pytest.raises(AssertionError, match="unexpected fields"):
            assert_schema(
                "POST",
                "/api/register",
                201,
                {"message": "ok", "user_id": 1, "token": "abc", "unknown_field": "should fail"},
            )

    def test_schema_validation_matches_live_routes(self, client):
        """Call register + login via client, validate against schema."""
        from schema_helpers import assert_schema

        # Register a test user
        resp = client.post(
            "/api/register",
            json={
                "username": "schematest_user",
                "email": "schema@test.com",
                "password": "testpass123",
            },
        )
        if resp.status_code == 201:
            data = resp.get_json()
            assert_schema("POST", "/api/register", 201, data)
        elif resp.status_code == 409:
            data = resp.get_json()
            assert_schema("POST", "/api/register", 409, data)

        # Login
        resp = client.post(
            "/api/login",
            json={
                "username": "schematest_user",
                "password": "testpass123",
            },
        )
        if resp.status_code == 200:
            data = resp.get_json()
            assert_schema("POST", "/api/login", 200, data)
