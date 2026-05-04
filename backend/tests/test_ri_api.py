"""
Regression tests — Resume Interview API endpoints.

Covers: start, message, state, preview, finalize routes.
RTX 5090 LLM at port 8021 is live; no mocking of LLM calls.
"""

import time


def register_and_login(client):
    ts = int(time.time() * 1000)
    resp = client.post(
        "/api/register",
        json={
            "username": f"ri_user_{ts}",
            "email": f"ri_{ts}@test.com",
            "password": "TestPass123!",
        },
    )
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    return str(data["user_id"]), data.get("token", "")


def auth_headers(token, user_id):
    return {"Authorization": f"Bearer {token}", "user-id": user_id}


def start_session(client, user_id, token):
    resp = client.post("/api/resume-interview/start", headers=auth_headers(token, user_id))
    assert resp.status_code in (200, 201)
    return resp.get_json()["session_id"]


def send_msg(client, session_id, message, user_id, token):
    resp = client.post(
        "/api/resume-interview/message",
        json={"session_id": session_id, "message": message},
        headers=auth_headers(token, user_id),
    )
    assert resp.status_code == 200
    return resp.get_json()


# ── /api/resume-interview/start ───────────────────────────────────────────────


class TestStart:
    def test_returns_session_id_and_welcome(self, client):
        uid, tok = register_and_login(client)
        resp = client.post("/api/resume-interview/start", headers=auth_headers(tok, uid))
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert "session_id" in data
        assert data["stage"] == "welcome"
        assert len(data["message"]) > 20
        assert "progress" in data

    def test_requires_auth(self, client):
        resp = client.post("/api/resume-interview/start")
        assert resp.status_code == 401

    def test_progress_has_8_stages(self, client):
        uid, tok = register_and_login(client)
        resp = client.post("/api/resume-interview/start", headers=auth_headers(tok, uid))
        prog = resp.get_json()["progress"]
        assert prog["total_stages"] == 8
        assert prog["stage_index"] == 0

    def test_welcome_message_in_history(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        state = client.get(
            f"/api/resume-interview/state/{sid}",
            headers=auth_headers(tok, uid),
        ).get_json()
        assert len(state["messages"]) >= 1
        assert state["messages"][0]["role"] == "assistant"


# ── /api/resume-interview/message ─────────────────────────────────────────────


class TestMessage:
    def test_send_name_extracts_into_context(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        data = send_msg(client, sid, "Jane Doe", uid, tok)
        assert data["context"]["name"] == "Jane Doe"
        assert data["stage"] == "welcome"

    def test_advances_stage_after_confirm(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        send_msg(client, sid, "Jane Doe", uid, tok)
        data = send_msg(client, sid, "yes", uid, tok)
        assert data["stage"] == "contact"

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/resume-interview/message",
            json={"session_id": "fake", "message": "hi"},
        )
        assert resp.status_code == 401

    def test_invalid_session_returns_error(self, client):
        uid, tok = register_and_login(client)
        resp = client.post(
            "/api/resume-interview/message",
            json={"session_id": "nonexistent-id", "message": "hello"},
            headers=auth_headers(tok, uid),
        )
        assert "error" in resp.get_json()

    def test_llm_or_template_response_non_empty(self, client):
        """RTX 5090 provides response; template is silent fallback."""
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        data = send_msg(client, sid, "Maria Gonzalez", uid, tok)
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 10

    def test_messages_saved_in_history(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        send_msg(client, sid, "John Smith", uid, tok)
        state = client.get(
            f"/api/resume-interview/state/{sid}",
            headers=auth_headers(tok, uid),
        ).get_json()
        roles = [m["role"] for m in state["messages"]]
        assert "user" in roles
        assert "assistant" in roles

    def test_finalized_session_rejects_messages(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        client.post(
            f"/api/resume-interview/finalize/{sid}",
            json={},
            headers=auth_headers(tok, uid),
        )
        resp = client.post(
            "/api/resume-interview/message",
            json={"session_id": sid, "message": "hello"},
            headers=auth_headers(tok, uid),
        )
        assert "error" in resp.get_json()


# ── /api/resume-interview/state ───────────────────────────────────────────────


class TestState:
    def test_returns_messages_and_context(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        send_msg(client, sid, "Mary Johnson", uid, tok)
        state = client.get(
            f"/api/resume-interview/state/{sid}",
            headers=auth_headers(tok, uid),
        ).get_json()
        assert len(state["messages"]) >= 2
        assert "context" in state
        assert isinstance(state["context"], dict)

    def test_requires_auth(self, client):
        resp = client.get("/api/resume-interview/state/fake-id")
        assert resp.status_code == 401

    def test_wrong_user_returns_error(self, client):
        uid, tok = register_and_login(client)
        uid2, tok2 = register_and_login(client)
        sid = start_session(client, uid, tok)
        state = client.get(
            f"/api/resume-interview/state/{sid}",
            headers=auth_headers(tok2, uid2),
        ).get_json()
        assert "error" in state

    def test_not_finalized_initially(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        state = client.get(
            f"/api/resume-interview/state/{sid}",
            headers=auth_headers(tok, uid),
        ).get_json()
        assert state["is_finalized"] is False


# ── /api/resume-interview/preview ─────────────────────────────────────────────


class TestPreview:
    def test_returns_compiled_text(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        resp = client.get(
            f"/api/resume-interview/preview/{sid}",
            headers=auth_headers(tok, uid),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "compiled_text" in data
        assert isinstance(data["compiled_text"], str)

    def test_wrong_user_returns_error(self, client):
        uid, tok = register_and_login(client)
        uid2, tok2 = register_and_login(client)
        sid = start_session(client, uid, tok)
        data = client.get(
            f"/api/resume-interview/preview/{sid}",
            headers=auth_headers(tok2, uid2),
        ).get_json()
        assert "error" in data


# ── /api/resume-interview/finalize ────────────────────────────────────────────


class TestFinalize:
    def test_creates_resume_version(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        fin = client.post(
            f"/api/resume-interview/finalize/{sid}",
            json={},
            headers=auth_headers(tok, uid),
        )
        assert fin.status_code in (200, 201)
        data = fin.get_json()
        assert data["status"] == "saved"
        assert "version_id" in data
        assert "resume_id" in data
        assert len(data["compiled_text"]) > 0

    def test_marks_session_finalized(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        client.post(
            f"/api/resume-interview/finalize/{sid}",
            json={},
            headers=auth_headers(tok, uid),
        )
        state = client.get(
            f"/api/resume-interview/state/{sid}",
            headers=auth_headers(tok, uid),
        ).get_json()
        assert state["is_finalized"] is True

    def test_version_appears_in_versions_list(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        fin = client.post(
            f"/api/resume-interview/finalize/{sid}",
            json={},
            headers=auth_headers(tok, uid),
        ).get_json()
        version_id = fin["version_id"]
        resp = client.get("/api/resumes/versions", headers=auth_headers(tok, uid)).get_json()
        versions = resp.get("versions", resp) if isinstance(resp, dict) else resp
        ids = [v["id"] for v in versions]
        assert version_id in ids

    def test_edits_override_context(self, client):
        uid, tok = register_and_login(client)
        sid = start_session(client, uid, tok)
        # Edits must be nested under "edits" key per the finalize route
        fin = client.post(
            f"/api/resume-interview/finalize/{sid}",
            json={
                "edits": {"name": "Edited Name Override", "preferred_name": "Edited Name Override"}
            },
            headers=auth_headers(tok, uid),
        ).get_json()
        assert "Edited Name Override" in fin["compiled_text"]

    def test_requires_auth(self, client):
        resp = client.post("/api/resume-interview/finalize/fake-sid", json={})
        assert resp.status_code == 401
