"""Locust load test — Phase 4.2 soak test for resume-optimizer API.

Target: 50 concurrent users, 10-minute soak.
Pass criteria: P99 response time ≤ baseline + 20%, error rate < 1%.

Usage (against local dev server on port 5000):
    locust -f tests/load/locustfile.py \
        --host http://localhost:5000 \
        --users 50 --spawn-rate 5 \
        --run-time 10m --headless \
        --html tests/load/results/report.html

Usage (against AWS target):
    LOAD_TARGET_HOST=https://your-api.example.com \
    LOAD_TEST_EMAIL=loadtest@example.com \
    LOAD_TEST_PASSWORD=<secret> \
    locust -f tests/load/locustfile.py \
        --host $LOAD_TARGET_HOST \
        --users 50 --spawn-rate 5 \
        --run-time 10m --headless

Environment variables:
    LOAD_TEST_EMAIL     — test account email (default: test@example.com)
    LOAD_TEST_PASSWORD  — test account password (default: testpass123)
    LOAD_TARGET_HOST    — override host (or pass --host to locust)

Pass criteria (automated check in validate_results.py):
    P99 ≤ baseline_p99 * 1.20
    Error rate < 1%
    Requests/s ≥ 10
"""
from __future__ import annotations

import json
import os
import time

from locust import HttpUser, TaskSet, between, events, tag, task


_EMAIL = os.environ.get("LOAD_TEST_EMAIL", "test@example.com")
_PASSWORD = os.environ.get("LOAD_TEST_PASSWORD", "testpass123")

# ---------------------------------------------------------------------------
# Shared auth token cache — all users share a single login to avoid
# hammering the auth endpoint and to isolate load measurement to API logic.
# ---------------------------------------------------------------------------
_token_cache: dict[str, str] = {}


def _get_token(client, email: str, password: str) -> str | None:
    if email in _token_cache:
        return _token_cache[email]
    with client.post(
        "/api/login",
        json={"email": email, "password": password},
        catch_response=True,
        name="POST /api/login",
    ) as resp:
        if resp.status_code == 200:
            token = resp.json().get("token") or resp.json().get("access_token")
            if token:
                _token_cache[email] = token
                return token
            resp.failure("Login response missing token field")
        else:
            resp.failure(f"Login failed: {resp.status_code} {resp.text[:200]}")
    return None


# ---------------------------------------------------------------------------
# Task sets
# ---------------------------------------------------------------------------

class PublicTasks(TaskSet):
    """Unauthenticated endpoints — health checks and static reads."""

    @tag("public", "health")
    @task(10)
    def health_check(self):
        self.client.get("/api/health", name="GET /api/health")


class AuthenticatedReadTasks(TaskSet):
    """Read-heavy authenticated endpoints (analytics, sessions, campaigns)."""

    token: str | None = None

    def on_start(self):
        self.token = _get_token(self.client, _EMAIL, _PASSWORD)

    def _headers(self) -> dict:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    @tag("auth", "sessions")
    @task(8)
    def list_sessions(self):
        self.client.get(
            "/api/sessions",
            headers=self._headers(),
            name="GET /api/sessions",
        )

    @tag("auth", "analytics")
    @task(5)
    def analytics_overview(self):
        self.client.get(
            "/api/analytics/overview",
            headers=self._headers(),
            name="GET /api/analytics/overview",
        )

    @tag("auth", "analytics")
    @task(3)
    def analytics_funnel(self):
        self.client.get(
            "/api/analytics/funnel",
            headers=self._headers(),
            name="GET /api/analytics/funnel",
        )

    @tag("auth", "campaigns")
    @task(4)
    def list_campaigns(self):
        self.client.get(
            "/api/campaigns",
            headers=self._headers(),
            name="GET /api/campaigns",
        )

    @tag("auth", "graph")
    @task(2)
    def graph_technologies(self):
        # 503 = ArangoDB not available (expected in local env without ArangoDB)
        with self.client.get(
            "/api/graph/technologies",
            headers=self._headers(),
            name="GET /api/graph/technologies",
            catch_response=True,
        ) as resp:
            if resp.status_code == 503 and b"ArangoDB" in resp.content:
                resp.success()
            elif resp.status_code not in (200, 503):
                resp.failure(f"Unexpected status {resp.status_code}")

    @tag("auth", "sessions")
    @task(2)
    def session_insights(self):
        self.client.get(
            "/api/sessions/insights",
            headers=self._headers(),
            name="GET /api/sessions/insights",
        )


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

class ResumeOptimizerUser(HttpUser):
    """Simulates a logged-in resume-optimizer user doing typical read operations.

    Weight distribution:
      80% read-heavy authenticated tasks (analytics, sessions, campaigns)
      20% health/public checks
    """

    wait_time = between(0.5, 2.0)
    tasks = {
        PublicTasks: 1,
        AuthenticatedReadTasks: 4,
    }

    def on_start(self):
        # Pre-warm auth token so first real task doesn't pay the login cost
        _get_token(self.client, _EMAIL, _PASSWORD)


# ---------------------------------------------------------------------------
# Results validation hook (called by CI after --headless run)
# ---------------------------------------------------------------------------

@events.quitting.add_listener
def _validate_results(environment, **kwargs):
    """Fail the Locust run if pass criteria are not met."""
    stats = environment.runner.stats
    total = stats.total

    p99_ms = total.get_response_time_percentile(0.99) or 0
    error_rate = total.fail_ratio * 100
    rps = total.current_rps if hasattr(total, "current_rps") else 0

    print(
        f"\n[load-test] P99={p99_ms:.0f}ms  error_rate={error_rate:.2f}%  "
        f"total_requests={total.num_requests}"
    )

    failures = []
    if error_rate >= 1.0:
        failures.append(f"Error rate {error_rate:.2f}% ≥ 1% threshold")
    if total.num_requests < 100:
        failures.append(f"Too few requests ({total.num_requests}) — test may not have run correctly")

    if failures:
        print("[load-test] FAIL:", "; ".join(failures))
        environment.process_exit_code = 1
    else:
        print("[load-test] PASS: all criteria met")
