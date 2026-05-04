"""Integration tests — campaign lifecycle with actual data."""

from test_helpers import query_db


def test_campaign_interview_to_creation(client, auth_headers):
    """Start campaign interview → send messages through stages → create campaign."""
    # 1. Start interview
    resp = client.post(
        "/api/campaigns/interview/start",
        headers=auth_headers,
        json={"theme": "Enterprise Architecture Leadership"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "session_id" in data
    session_id = data["session_id"]

    # 2. Send message (advance through stages)
    resp = client.post(
        "/api/campaigns/interview/message",
        headers=auth_headers,
        json={
            "session_id": session_id,
            "message": "Target audience is CTOs and engineering leaders " "at mid-size companies.",
        },
    )
    assert resp.status_code == 200
    msg_data = resp.get_json()
    assert "stage" in msg_data or "message" in msg_data

    # 3. Get interview state
    resp = client.get(f"/api/campaigns/interview/{session_id}/state", headers=auth_headers)
    assert resp.status_code == 200
    state = resp.get_json()
    assert "stage" in state

    # 4. Try to create campaign (may fail if interview not fully complete)
    resp = client.post(
        "/api/campaigns/create",
        headers=auth_headers,
        json={"session_id": session_id},
    )
    # 201 if interview was finalized, 400 if not yet complete
    assert resp.status_code in (201, 400)
    data = resp.get_json()
    assert isinstance(data, dict)
    if resp.status_code == 201:
        assert "campaign_id" in data
    else:
        assert "error" in data, "400 campaign create must include error"


def test_campaign_crud_lifecycle(client, auth_headers):
    """Create campaign directly (via SQL) → list → update → delete."""
    # Insert campaign via interview shortcut — start + finalize manually
    resp = client.post(
        "/api/campaigns/interview/start",
        headers=auth_headers,
        json={"theme": "AI in Healthcare"},
    )
    session_id = resp.get_json()["session_id"]

    # Advance through all stages to make it finalizable
    for msg in [
        "Target CTOs and VPs of Engineering",
        "Professional and authoritative tone",
        "How AI transforms patient outcomes",
        "5 posts over 2 weeks",
        "Focus on real case studies",
        "Looks good, let's finalize",
    ]:
        client.post(
            "/api/campaigns/interview/message",
            headers=auth_headers,
            json={"session_id": session_id, "message": msg},
        )

    resp = client.post(
        "/api/campaigns/create",
        headers=auth_headers,
        json={"session_id": session_id},
    )
    assert (
        resp.status_code == 201
    ), f"Campaign creation failed (status {resp.status_code}): {resp.get_json()}"

    campaign_id = resp.get_json()["campaign_id"]

    # DB: verify campaign row exists
    rows = query_db("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
    assert len(rows) == 1, f"No campaigns row for {campaign_id}"

    # List should contain our campaign
    resp = client.get("/api/campaigns", headers=auth_headers)
    assert resp.status_code == 200
    campaigns = resp.get_json()["campaigns"]
    assert any(c["id"] == campaign_id for c in campaigns)

    # Get single campaign
    resp = client.get(f"/api/campaigns/{campaign_id}", headers=auth_headers)
    assert resp.status_code == 200

    # Update campaign
    resp = client.put(
        f"/api/campaigns/{campaign_id}",
        headers=auth_headers,
        json={"tone": "conversational"},
    )
    assert resp.status_code == 200

    # Delete campaign
    resp = client.delete(f"/api/campaigns/{campaign_id}", headers=auth_headers)
    assert resp.status_code == 200

    # Verify deleted
    resp = client.get(f"/api/campaigns/{campaign_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_campaign_posts_crud(client, auth_headers):
    """Create campaign → add post → edit → reorder → delete → export."""
    # Create campaign via interview
    resp = client.post(
        "/api/campaigns/interview/start",
        headers=auth_headers,
        json={"theme": "Cloud Migration"},
    )
    session_id = resp.get_json()["session_id"]
    for msg in [
        "DevOps engineers and cloud architects",
        "Technical and practical",
        "Step by step cloud migration guide",
        "3 posts",
        "AWS, Azure, GCP comparisons",
        "Finalize",
    ]:
        client.post(
            "/api/campaigns/interview/message",
            headers=auth_headers,
            json={"session_id": session_id, "message": msg},
        )
    resp = client.post(
        "/api/campaigns/create",
        headers=auth_headers,
        json={"session_id": session_id},
    )
    assert (
        resp.status_code == 201
    ), f"Campaign creation failed (status {resp.status_code}): {resp.get_json()}"
    campaign_id = resp.get_json()["campaign_id"]

    # Count existing posts (interview seeds may have created some)
    resp = client.get(f"/api/campaigns/{campaign_id}/posts", headers=auth_headers)
    assert resp.status_code == 200
    initial_count = len(resp.get_json()["posts"])

    # Add manual posts
    resp = client.post(
        f"/api/campaigns/{campaign_id}/posts",
        headers=auth_headers,
        json={
            "title": "Why Migrate to the Cloud?",
            "content": "Cloud migration reduces costs and improves scalability...",
        },
    )
    assert resp.status_code == 201
    post1_id = resp.get_json()["post_id"]

    resp = client.post(
        f"/api/campaigns/{campaign_id}/posts",
        headers=auth_headers,
        json={
            "title": "Choosing Your Cloud Provider",
            "content": "AWS vs Azure vs GCP — here's what matters...",
        },
    )
    assert resp.status_code == 201
    post2_id = resp.get_json()["post_id"]

    # List posts — should have initial + 2 manually added
    resp = client.get(f"/api/campaigns/{campaign_id}/posts", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.get_json()["posts"]) == initial_count + 2

    # Edit post
    resp = client.put(
        f"/api/campaigns/{campaign_id}/posts/{post1_id}",
        headers=auth_headers,
        json={"content": "Updated: Cloud migration is essential for modern enterprises..."},
    )
    assert resp.status_code == 200

    # Reorder posts (just the 2 manual posts)
    resp = client.put(
        f"/api/campaigns/{campaign_id}/posts/reorder",
        headers=auth_headers,
        json={"order": [post2_id, post1_id]},
    )
    assert resp.status_code == 200

    # Export campaign
    resp = client.get(f"/api/campaigns/{campaign_id}/export", headers=auth_headers)
    assert resp.status_code == 200
    export = resp.get_json()
    assert "text" in export
    assert export["post_count"] >= 2

    # DB: verify posts in DB
    rows = query_db("SELECT * FROM campaign_posts WHERE campaign_id = ?", (campaign_id,))
    assert len(rows) >= 2

    # Delete a post
    resp = client.delete(
        f"/api/campaigns/{campaign_id}/posts/{post1_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # Verify one fewer post
    resp = client.get(f"/api/campaigns/{campaign_id}/posts", headers=auth_headers)
    assert len(resp.get_json()["posts"]) == initial_count + 1


def test_campaign_isolation(client, auth_headers, second_user_headers):
    """User B cannot see or modify User A's campaigns."""
    resp = client.post(
        "/api/campaigns/interview/start",
        headers=auth_headers,
        json={"theme": "Private Campaign"},
    )
    session_id = resp.get_json()["session_id"]
    for msg in ["Audience", "Tone", "Story", "3 posts", "Seeds", "Done"]:
        client.post(
            "/api/campaigns/interview/message",
            headers=auth_headers,
            json={"session_id": session_id, "message": msg},
        )
    resp = client.post(
        "/api/campaigns/create",
        headers=auth_headers,
        json={"session_id": session_id},
    )
    assert (
        resp.status_code == 201
    ), f"Campaign creation failed (status {resp.status_code}): {resp.get_json()}"
    campaign_id = resp.get_json()["campaign_id"]

    # User B cannot see it
    resp = client.get(f"/api/campaigns/{campaign_id}", headers=second_user_headers)
    assert resp.status_code == 404

    # User B cannot delete it
    resp = client.delete(f"/api/campaigns/{campaign_id}", headers=second_user_headers)
    assert resp.status_code == 404

    # User B's list is empty
    resp = client.get("/api/campaigns", headers=second_user_headers)
    assert resp.status_code == 200
    assert len(resp.get_json()["campaigns"]) == 0
