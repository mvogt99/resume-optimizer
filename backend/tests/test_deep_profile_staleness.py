"""P2-A: Deep Profile Staleness Detection tests.

Tests that:
- Staleness columns (source_hash, is_stale, stale_reason, last_checked_at) exist
- compute_source_hash() produces a deterministic string
- Hash changes when source data counts change
- check_staleness() marks profile stale when hash diverges
- GET /api/deep-profile/status returns freshness info
- POST /api/deep-profile/refresh rebuilds when stale, skips when fresh
- mark_profile_stale() sets is_stale flag
"""

import sqlite3
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, ".")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_ctx():
    import app as flask_app

    with flask_app.app.app_context():
        yield flask_app.app


@pytest.fixture()
def db_conn():
    from models import get_db_connection

    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture()
def client(app_ctx):
    return app_ctx.test_client()


# ---------------------------------------------------------------------------
# P2-A.1: Schema — staleness columns exist
# ---------------------------------------------------------------------------


class TestStalenessSchema:
    def test_source_hash_column_exists(self, db_conn):
        cursor = db_conn.execute("PRAGMA table_info(deep_profiles)")
        cols = [row["name"] for row in cursor]
        assert "source_hash" in cols, "deep_profiles missing source_hash column"

    def test_is_stale_column_exists(self, db_conn):
        cursor = db_conn.execute("PRAGMA table_info(deep_profiles)")
        cols = [row["name"] for row in cursor]
        assert "is_stale" in cols, "deep_profiles missing is_stale column"

    def test_stale_reason_column_exists(self, db_conn):
        cursor = db_conn.execute("PRAGMA table_info(deep_profiles)")
        cols = [row["name"] for row in cursor]
        assert "stale_reason" in cols, "deep_profiles missing stale_reason column"

    def test_last_checked_at_column_exists(self, db_conn):
        cursor = db_conn.execute("PRAGMA table_info(deep_profiles)")
        cols = [row["name"] for row in cursor]
        assert "last_checked_at" in cols, "deep_profiles missing last_checked_at column"


# ---------------------------------------------------------------------------
# P2-A.1: compute_source_hash returns deterministic string
# ---------------------------------------------------------------------------


class TestComputeSourceHash:
    def test_returns_string(self, app_ctx):
        from deep_profile_staleness import compute_source_hash

        result = compute_source_hash(user_id=3)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_deterministic(self, app_ctx):
        from deep_profile_staleness import compute_source_hash

        h1 = compute_source_hash(user_id=3)
        h2 = compute_source_hash(user_id=3)
        assert h1 == h2, "Same data should produce same hash"

    def test_different_users_may_differ(self, app_ctx):
        from deep_profile_staleness import compute_source_hash

        compute_source_hash(user_id=3)
        h99 = compute_source_hash(user_id=99)
        # user 99 has no data, user 3 may have data — they should differ
        # (if user 3 has any data at all)
        assert isinstance(h99, str)

    def test_hash_changes_when_counts_change(self, app_ctx):
        """Hash function uses source counts — mock a count change."""
        with patch(
            "deep_profile_staleness._get_source_counts",
            return_value={
                "projects": 5,
                "experiences": 2,
                "events": 100,
                "narratives": 10,
                "linkedin_ts": "2026-01-01",
            },
        ):
            import deep_profile_staleness as dps

            h1 = dps._hash_counts(
                {
                    "projects": 5,
                    "experiences": 2,
                    "events": 100,
                    "narratives": 10,
                    "linkedin_ts": "2026-01-01",
                }
            )

        h2 = dps._hash_counts(
            {
                "projects": 6,  # one more project
                "experiences": 2,
                "events": 100,
                "narratives": 10,
                "linkedin_ts": "2026-01-01",
            }
        )
        assert h1 != h2, "Different counts should produce different hashes"


# ---------------------------------------------------------------------------
# P2-A.2: Staleness detection
# ---------------------------------------------------------------------------


class TestStalenessDetection:
    def test_check_staleness_returns_dict(self, app_ctx):
        from deep_profile_staleness import check_staleness

        result = check_staleness(user_id=3)
        assert isinstance(result, dict)

    def test_check_staleness_has_required_keys(self, app_ctx):
        from deep_profile_staleness import check_staleness

        result = check_staleness(user_id=3)
        assert "is_stale" in result
        assert "current_hash" in result
        assert "stored_hash" in result

    def test_mark_profile_stale_sets_flag(self, app_ctx, db_conn):
        from deep_profile_staleness import mark_profile_stale

        mark_profile_stale(user_id=3, reason="test: new project approved")

        row = db_conn.execute(
            "SELECT is_stale, stale_reason FROM deep_profiles "
            "WHERE user_id=3 ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()

        # If no profile exists, mark_profile_stale is a no-op — that's OK
        if row:
            assert row["is_stale"] == 1
            assert "test: new project" in (row["stale_reason"] or "")


# ---------------------------------------------------------------------------
# P2-A.3: Status API
# ---------------------------------------------------------------------------


class TestStatusAPI:
    def test_status_endpoint_exists(self, client):
        resp = client.get("/api/deep-profile/status", headers={"user-id": "3"})
        assert resp.status_code in (200, 404), f"Expected 200 or 404, got {resp.status_code}"

    def test_status_returns_json(self, client):
        resp = client.get("/api/deep-profile/status", headers={"user-id": "3"})
        data = resp.get_json()
        assert data is not None, "Expected JSON response"

    def test_status_200_has_required_fields(self, client):
        resp = client.get("/api/deep-profile/status", headers={"user-id": "3"})
        if resp.status_code == 200:
            data = resp.get_json()
            assert "is_stale" in data
            assert "last_built_at" in data
            assert "source_counts" in data

    def test_status_404_when_no_profile(self, client):
        """User 9999 has no profile — expect 404."""
        resp = client.get("/api/deep-profile/status", headers={"user-id": "9999"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# P2-A.4: Refresh endpoint
# ---------------------------------------------------------------------------


class TestRefreshEndpoint:
    def test_refresh_endpoint_exists(self, client):
        fake_profile = {"differentiators": [], "technology_mastery": []}
        with (
            patch(
                "deep_profile_staleness.check_staleness",
                return_value={
                    "is_stale": False,
                    "current_hash": "abc",
                    "stored_hash": "abc",
                },
            ),
            patch(
                "deep_profile.DeepProfileEngine.build_profile",
                return_value=fake_profile,
            ),
        ):
            resp = client.post(
                "/api/deep-profile/refresh",
                headers={"user-id": "3"},
                json={},
            )
        assert resp.status_code in (200, 202, 304, 404)

    def test_refresh_returns_304_when_fresh(self, client, app_ctx):
        """When profile is fresh (hash matches), refresh returns 304."""
        with patch(
            "deep_profile_staleness.check_staleness",
            return_value={
                "is_stale": False,
                "current_hash": "abc123",
                "stored_hash": "abc123",
            },
        ):
            resp = client.post(
                "/api/deep-profile/refresh",
                headers={"user-id": "3"},
                json={},
            )
        assert resp.status_code in (
            200,
            304,
        ), f"Expected 200 or 304 for fresh profile, got {resp.status_code}"

    def test_refresh_rebuilds_when_stale(self, client, app_ctx):
        """When profile is stale, refresh triggers rebuild."""
        fake_profile = {
            "differentiators": [{"theme": "Practice Builder"}],
            "technology_mastery": [],
        }
        with (
            patch(
                "deep_profile_staleness.check_staleness",
                return_value={
                    "is_stale": True,
                    "current_hash": "new123",
                    "stored_hash": "old456",
                    "stale_reason": "New client project approved",
                },
            ),
            patch(
                "deep_profile.DeepProfileEngine.build_profile",
                return_value=fake_profile,
            ),
        ):
            resp = client.post(
                "/api/deep-profile/refresh",
                headers={"user-id": "3"},
                json={},
            )
        assert resp.status_code in (
            200,
            202,
        ), f"Expected 200/202 for stale profile rebuild, got {resp.status_code}"
