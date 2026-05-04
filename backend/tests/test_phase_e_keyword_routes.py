"""Integration + unit tests for keyword grouping and equivalency routes (Phase E).

Endpoints:
  POST /api/keywords/group
  POST /api/keywords/equivalency/interview
  POST /api/keywords/equivalency/rewrite
  POST /api/keywords/equivalencies   (save)
  GET  /api/keywords/equivalencies   (list)
  DELETE /api/keywords/equivalencies/<keyword>

Mutation targets:
  MK1: 401 when unauthenticated (group)
  MK2: 400 when >100 keywords (DoS guard)
  MK3: 400 when confidence out of range (save)
  MK4: 401 when unauthenticated (interview)
  MK5: 400 when current_question missing (interview)
  MK6: 400 when user_answer missing (interview)
  MK7: 404 when deleting non-existent equivalency
"""

import io
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

_RESUME_TEXT = (
    "Jane Doe\nSoftware Engineer\n\nEXPERIENCE\n"
    "Engineer — Acme (2020-Present)\n"
    "- Built Python services processing 1M events/day.\n"
    "SKILLS\nPython, AWS, Kafka"
)

_STUB_GROUPS = {
    "groups": [
        {
            "name": "Streaming Technologies",
            "keywords": ["Kafka", "Kinesis"],
            "description": "Event streaming platforms",
        }
    ]
}

_STUB_TURN = {
    "next_question": "Do you have experience with event streaming systems?",
    "resolved": [
        {"keyword": "Kafka", "equivalent": "event streaming", "confidence": 0.8, "status": "equivalent"}
    ],
    "finished": False,
}

_STUB_REWRITES = {
    "rewrites": [
        {
            "section": "EXPERIENCE",
            "original_text": "Built Python services processing 1M events/day.",
            "proposed_text": "Built Python services processing 1M events/day using Kafka streaming.",
            "keywords_addressed": ["Kafka"],
        }
    ]
}

_GROUP_URL = "/api/keywords/group"
_INTERVIEW_URL = "/api/keywords/equivalency/interview"
_REWRITE_URL = "/api/keywords/equivalency/rewrite"
_SAVE_URL = "/api/keywords/equivalencies"
_GET_URL = "/api/keywords/equivalencies"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _upload_resume(client, headers) -> int:
    data = {"file": (io.BytesIO(_RESUME_TEXT.encode()), "resume.txt")}
    resp = client.post(
        "/api/resume/upload",
        data=data,
        headers={k: v for k, v in headers.items() if k != "Content-Type"},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 201), f"Upload failed: {resp.get_data(as_text=True)}"
    return int(resp.get_json()["resume_id"])


# ---------------------------------------------------------------------------
# Tests: POST /api/keywords/group
# ---------------------------------------------------------------------------


class TestGroupKeywords:
    def _post(self, client, headers, body):
        return client.post(_GROUP_URL, json=body, headers=headers)

    # MK1: auth guard
    def test_unauthenticated_returns_401(self, client):
        """No auth → 401 (MK1). Mutation: remove guard → non-401."""
        resp = self._post(client, {}, {"keywords": ["Python"]})
        assert resp.status_code == 401

    def test_empty_keywords_returns_empty_groups(self, client, auth_headers):
        """Empty keywords list → 200 with empty groups."""
        resp = self._post(client, auth_headers, {"keywords": []})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["groups"] == []
        assert data["auto_resolved"] == []

    # MK2: DoS guard
    def test_too_many_keywords_returns_400(self, client, auth_headers):
        """More than 100 keywords → 400 (MK2)."""
        resp = self._post(client, auth_headers, {"keywords": [f"kw{i}" for i in range(101)]})
        assert resp.status_code == 400
        assert "100" in resp.get_json().get("error", "")

    def test_exactly_100_keywords_is_allowed(self, client, auth_headers):
        """Exactly 100 keywords → not rejected (boundary check)."""
        with patch("routes.keyword_routes.group_keywords", return_value={**_STUB_GROUPS, "auto_resolved": []}), \
             patch("routes.keyword_routes.apply_persisted_equivalencies", return_value=([f"kw{i}" for i in range(100)], [])), \
             patch("routes.keyword_routes.get_equivalencies", return_value=[]):
            resp = self._post(client, auth_headers, {"keywords": [f"kw{i}" for i in range(100)]})
        assert resp.status_code == 200

    def test_happy_path_returns_groups(self, client, auth_headers):
        """Valid keywords → 200 with groups list."""
        with patch("routes.keyword_routes.group_keywords", return_value={**_STUB_GROUPS, "auto_resolved": []}), \
             patch("routes.keyword_routes.apply_persisted_equivalencies", return_value=(["Kafka"], [])), \
             patch("routes.keyword_routes.get_equivalencies", return_value=[]):
            resp = self._post(client, auth_headers, {"keywords": ["Kafka", "Kinesis"]})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "groups" in data
        assert "auto_resolved" in data

    def test_groups_have_required_keys(self, client, auth_headers):
        """Each group has name, keywords, description."""
        with patch("routes.keyword_routes.group_keywords", return_value={**_STUB_GROUPS, "auto_resolved": []}), \
             patch("routes.keyword_routes.apply_persisted_equivalencies", return_value=(["Kafka"], [])), \
             patch("routes.keyword_routes.get_equivalencies", return_value=[]):
            resp = self._post(client, auth_headers, {"keywords": ["Kafka"]})
        groups = resp.get_json()["groups"]
        if groups:
            for g in groups:
                for key in ("name", "keywords", "description"):
                    assert key in g, f"Group missing key: {key}"


# ---------------------------------------------------------------------------
# Tests: POST /api/keywords/equivalency/interview
# ---------------------------------------------------------------------------


class TestEquivalencyInterview:
    def _post(self, client, headers, body):
        return client.post(_INTERVIEW_URL, json=body, headers=headers)

    # MK4: auth guard
    def test_unauthenticated_returns_401(self, client):
        """No auth → 401 (MK4)."""
        resp = self._post(client, {}, {
            "current_question": "Do you know Kafka?",
            "user_answer": "Yes",
        })
        assert resp.status_code == 401

    # MK5: current_question required
    def test_missing_question_returns_400(self, client, auth_headers):
        """No current_question → 400 (MK5)."""
        resp = self._post(client, auth_headers, {"user_answer": "Yes"})
        assert resp.status_code == 400
        assert "current_question" in resp.get_json().get("error", "").lower()

    # MK6: user_answer required
    def test_missing_answer_returns_400(self, client, auth_headers):
        """No user_answer → 400 (MK6)."""
        resp = self._post(client, auth_headers, {"current_question": "Do you know Kafka?"})
        assert resp.status_code == 400
        assert "user_answer" in resp.get_json().get("error", "").lower()

    def test_happy_path_returns_turn_result(self, client, auth_headers):
        """Valid request → 200 with turn result."""
        with patch("routes.keyword_routes.run_equivalency_turn", return_value=_STUB_TURN):
            resp = self._post(client, auth_headers, {
                "current_question": "Do you know Kafka?",
                "user_answer": "Yes I use it for streaming.",
            })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "next_question" in data or "finished" in data

    def test_turn_result_has_resolved_list(self, client, auth_headers):
        """Turn result includes resolved list."""
        with patch("routes.keyword_routes.run_equivalency_turn", return_value=_STUB_TURN):
            resp = self._post(client, auth_headers, {
                "current_question": "Do you know Kafka?",
                "user_answer": "Yes I use it for streaming.",
            })
        assert "resolved" in resp.get_json()


# ---------------------------------------------------------------------------
# Tests: POST /api/keywords/equivalency/rewrite
# ---------------------------------------------------------------------------


class TestGenerateRewrites:
    def _post(self, client, headers, body):
        return client.post(_REWRITE_URL, json=body, headers=headers)

    def test_unauthenticated_returns_401(self, client):
        """No auth → 401."""
        resp = self._post(client, {}, {"resolved_keywords": [], "resume_text": "text"})
        assert resp.status_code == 401

    def test_empty_resolved_returns_empty_rewrites(self, client, auth_headers):
        """No resolved keywords → 200 with empty rewrites."""
        resp = self._post(client, auth_headers, {"resolved_keywords": [], "resume_text": "text"})
        assert resp.status_code == 200
        assert resp.get_json()["rewrites"] == []

    def test_missing_resume_text_returns_400(self, client, auth_headers):
        """No resume_text → 400."""
        resp = self._post(client, auth_headers, {
            "resolved_keywords": [{"keyword": "Kafka", "equivalent": "streaming"}]
        })
        assert resp.status_code == 400

    def test_happy_path_returns_rewrites(self, client, auth_headers):
        """Valid request → 200 with rewrites list."""
        with patch("routes.keyword_routes.generate_rewrites", return_value=_STUB_REWRITES):
            resp = self._post(client, auth_headers, {
                "resolved_keywords": [{"keyword": "Kafka", "equivalent": "event streaming", "confidence": 0.8}],
                "resume_text": _RESUME_TEXT,
            })
        assert resp.status_code == 200
        assert "rewrites" in resp.get_json()


# ---------------------------------------------------------------------------
# Tests: Save / Get / Delete equivalencies
# ---------------------------------------------------------------------------


class TestEquivalencyCRUD:
    # MK3: confidence validation
    def test_invalid_confidence_returns_400(self, client, auth_headers):
        """confidence > 1.0 → 400 (MK3)."""
        resp = client.post(_SAVE_URL, json={
            "resolved": [{"keyword": "Kafka", "equivalent": "streaming", "confidence": 2.5}]
        }, headers=auth_headers)
        assert resp.status_code == 400
        assert "confidence" in resp.get_json().get("error", "").lower()

    def test_negative_confidence_returns_400(self, client, auth_headers):
        """confidence < 0 → 400 (MK3 variant)."""
        resp = client.post(_SAVE_URL, json={
            "resolved": [{"keyword": "Kafka", "equivalent": "streaming", "confidence": -0.1}]
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_valid_confidence_range_accepted(self, client, auth_headers):
        """confidence in [0.0, 1.0] → 200."""
        with patch("routes.keyword_routes.save_equivalencies", return_value=1):
            resp = client.post(_SAVE_URL, json={
                "resolved": [{"keyword": "Kafka", "equivalent": "streaming", "confidence": 0.8}]
            }, headers=auth_headers)
        assert resp.status_code == 200

    def test_save_returns_saved_count(self, client, auth_headers):
        """Successful save returns {saved: N}."""
        with patch("routes.keyword_routes.save_equivalencies", return_value=2):
            resp = client.post(_SAVE_URL, json={
                "resolved": [
                    {"keyword": "Kafka", "equivalent": "streaming", "confidence": 0.8},
                    {"keyword": "Kinesis", "equivalent": "streaming", "confidence": 0.7},
                ]
            }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["saved"] == 2

    def test_get_returns_equivalencies_list(self, client, auth_headers):
        """GET → 200 with equivalencies list."""
        with patch("routes.keyword_routes.get_equivalencies", return_value=[
            {"keyword": "Kafka", "equivalent": "event streaming", "confidence": 0.8}
        ]):
            resp = client.get(_GET_URL, headers=auth_headers)
        assert resp.status_code == 200
        assert "equivalencies" in resp.get_json()

    def test_unauthenticated_get_returns_401(self, client):
        """No auth on GET → 401."""
        resp = client.get(_GET_URL)
        assert resp.status_code == 401

    # MK7: delete non-existent
    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        """Deleting a keyword that doesn't exist → 404 (MK7)."""
        with patch("keyword_equivalency.delete_equivalency", return_value=False):
            resp = client.delete("/api/keywords/equivalencies/NonExistentKeyword",
                                 headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_existing_returns_200(self, client, auth_headers):
        """Successful delete → 200 with deleted:True."""
        with patch("routes.keyword_routes.delete_equivalency", return_value=True):
            resp = client.delete("/api/keywords/equivalencies/Kafka", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["deleted"] is True

    def test_unauthenticated_save_returns_401(self, client):
        """No auth on save → 401."""
        resp = client.post(_SAVE_URL, json={"resolved": []})
        assert resp.status_code == 401
