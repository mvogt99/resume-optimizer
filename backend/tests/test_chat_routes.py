"""Tests for chat_context.py and routes/chat_routes.py — Q&A assistant and ticket proxy."""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests


_EMPTY_CONTEXT = {
    "resume_text": None, "resume_filename": None, "ats_score": None,
    "matching_keywords": [], "missing_keywords": [], "job_description": None,
    "linkedin_headline": None, "linkedin_summary": None, "linkedin_skills": [],
}


def _make_conn_mock(resume_row=None, job_row=None):
    """Return a MagicMock conn where execute().fetchone() returns resume_row then job_row."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [resume_row, job_row]
    return conn


class TestChatContextAssembly:
    @patch("chat_context.get_db")
    @patch("linkedin_cache.get_profile")
    @patch("linkedin_cache.get_raw")
    def test_context_empty_db_returns_all_keys(self, mock_raw, mock_profile, mock_db):
        conn = _make_conn_mock(None, None)
        mock_db.return_value.__enter__.return_value = conn
        mock_profile.return_value = None
        mock_raw.return_value = None

        from chat_context import get_chat_context
        ctx = get_chat_context(1)

        for key in ("resume_text", "resume_filename", "ats_score", "matching_keywords",
                    "missing_keywords", "job_description", "linkedin_headline",
                    "linkedin_summary", "linkedin_skills"):
            assert key in ctx
        assert ctx["resume_text"] is None
        assert ctx["matching_keywords"] == []
        assert ctx["missing_keywords"] == []
        assert ctx["linkedin_skills"] == []

    @patch("chat_context.get_db")
    @patch("linkedin_cache.get_profile")
    @patch("linkedin_cache.get_raw")
    def test_context_with_resume_data(self, mock_raw, mock_profile, mock_db):
        resume_row = {"parsed_text": "Resume content", "file_name": "test.pdf"}
        conn = _make_conn_mock(resume_row, None)
        mock_db.return_value.__enter__.return_value = conn
        mock_profile.return_value = {"headline": "Software Engineer", "summary": "Experienced dev"}
        mock_raw.return_value = {
            "skills_and_endorsements": [
                {"name": "Python", "endorsement_count": 10},
                {"name": "Java", "endorsement_count": 5},
            ]
        }

        from chat_context import get_chat_context
        ctx = get_chat_context(1)

        assert ctx["resume_text"] == "Resume content"
        assert ctx["resume_filename"] == "test.pdf"
        assert ctx["linkedin_headline"] == "Software Engineer"
        assert ctx["linkedin_skills"] == ["Python", "Java"]

    @patch("chat_context.get_db")
    @patch("linkedin_cache.get_profile")
    @patch("linkedin_cache.get_raw")
    def test_context_linkedin_skills_sorted_by_endorsements(self, mock_raw, mock_profile, mock_db):
        conn = _make_conn_mock(None, None)
        mock_db.return_value.__enter__.return_value = conn
        mock_profile.return_value = None
        mock_raw.return_value = {
            "skills_and_endorsements": [
                {"name": "Python", "endorsement_count": 30},
                {"name": "Java", "endorsement_count": 50},
                {"name": "Docker", "endorsement_count": 20},
            ]
        }

        from chat_context import get_chat_context
        ctx = get_chat_context(1)

        assert ctx["linkedin_skills"] == ["Java", "Python", "Docker"]
        assert len(ctx["linkedin_skills"]) <= 10


class TestChatMessageEndpoint:
    def test_message_no_auth_returns_401(self, client):
        resp = client.post("/api/chat/message", json={"message": "hello"})
        assert resp.status_code == 401

    def test_message_empty_message_returns_400(self, client, auth_headers):
        resp = client.post("/api/chat/message", headers=auth_headers, json={"message": ""})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_message_missing_message_returns_400(self, client, auth_headers):
        resp = client.post("/api/chat/message", headers=auth_headers, json={})
        assert resp.status_code == 400

    @patch("routes.chat_routes.get_chat_context", return_value=_EMPTY_CONTEXT)
    @patch("routes.chat_routes.call_harness", return_value="Mocked LLM response")
    def test_message_returns_response(self, _harness, _ctx, client, auth_headers):
        resp = client.post("/api/chat/message", headers=auth_headers,
                           json={"message": "What is my ATS score?"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["response"] == "Mocked LLM response"
        assert "context_used" in data

    @patch("routes.chat_routes.get_chat_context", return_value=_EMPTY_CONTEXT)
    @patch("routes.chat_routes.call_harness", return_value=None)
    @patch("routes.chat_routes.call_direct", return_value="Fallback response")
    def test_message_fallback_when_harness_none(self, _direct, _harness, _ctx, client, auth_headers):
        resp = client.post("/api/chat/message", headers=auth_headers, json={"message": "hello"})
        assert resp.status_code == 200
        assert resp.get_json()["response"] == "Fallback response"


class TestChatTicketEndpoint:
    def test_ticket_no_auth_returns_401(self, client):
        resp = client.post("/api/chat/ticket",
                           json={"title": "Test", "description": "Test issue", "ticket_type": "bug"})
        assert resp.status_code == 401

    def test_ticket_short_title_returns_400(self, client, auth_headers):
        resp = client.post("/api/chat/ticket", headers=auth_headers,
                           json={"title": "Hi", "description": "Valid description here", "ticket_type": "bug"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_ticket_short_description_returns_400(self, client, auth_headers):
        resp = client.post("/api/chat/ticket", headers=auth_headers,
                           json={"title": "Valid title", "description": "Short", "ticket_type": "bug"})
        assert resp.status_code == 400

    def test_ticket_invalid_type_returns_400(self, client, auth_headers):
        resp = client.post("/api/chat/ticket", headers=auth_headers,
                           json={"title": "Valid title", "description": "This is a valid description", "ticket_type": "other"})
        assert resp.status_code == 400

    @patch.dict(os.environ, {"SUPPORT_GATEWAY_TOKEN": "fake-token"})
    @patch("routes.chat_routes.requests.post", side_effect=requests.RequestException("down"))
    def test_ticket_gateway_unavailable_returns_queued(self, _post, client, auth_headers):
        resp = client.post("/api/chat/ticket", headers=auth_headers,
                           json={"title": "Test ticket", "description": "This is a test description for the ticket", "ticket_type": "bug"})
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "queued"

    @patch.dict(os.environ, {"SUPPORT_GATEWAY_TOKEN": "fake-token"})
    @patch("routes.chat_routes.requests.post",
           return_value=MagicMock(status_code=201, json=lambda: {"id": "ticket-123"}))
    def test_ticket_created_successfully(self, _post, client, auth_headers):
        resp = client.post("/api/chat/ticket", headers=auth_headers,
                           json={"title": "Test ticket", "description": "This is a test description for the ticket", "ticket_type": "bug"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "created"
        assert data["ticket_id"] == "ticket-123"
