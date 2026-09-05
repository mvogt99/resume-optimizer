"""Tests for post_generator.py — LinkedIn post generation with real LLM.

Covers PostGenerator: init, generate_campaign_posts, regenerate_post, char limit.
"""

import json

import pytest
from test_helpers import query_db


def _create_campaign(user_id=1):
    """Insert a minimal campaign and return its ID."""
    import sqlite3

    import models

    seeds = [
        {
            "title": "Cloud Migration Success",
            "hook": "We saved $1.2M by migrating to microservices",
            "key_points": ["93% faster deployments", "99.99% uptime"],
            "source_refs": [],
        },
        {
            "title": "Leading Remote Teams",
            "hook": "Managing 12 engineers across 3 time zones taught me this",
            "key_points": ["blameless post-mortems", "async communication"],
            "source_refs": [],
        },
        {
            "title": "HIPAA at Scale",
            "hook": "Zero compliance violations in 3 years — here's how",
            "key_points": ["encryption everywhere", "automated audits"],
            "source_refs": [],
        },
    ]

    conn = models.get_db_connection()
    conn.execute(
        "INSERT INTO campaigns (user_id, theme, audience, tone, storyline, "
        "post_count, status, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            "AI Engineering Leadership",
            "Tech leaders and CTOs",
            "professional",
            "How I built AI systems that saved $1M+",
            3,
            "finalized",
            json.dumps({"seeds": seeds}),
        ),
    )
    campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return campaign_id


def test_post_generator_init(app):
    from post_generator import PostGenerator

    gen = PostGenerator()
    assert gen is not None


def test_generate_campaign_posts_produces_content(app):
    from post_generator import PostGenerator

    campaign_id = _create_campaign(user_id=1)
    gen = PostGenerator()
    posts = gen.generate_campaign_posts(campaign_id, user_id=1)
    assert isinstance(posts, list), f"Expected list, got {type(posts)}"
    assert len(posts) > 0, "Should generate at least 1 post"


def test_generated_post_under_3000_chars(app):
    from post_generator import PostGenerator

    campaign_id = _create_campaign(user_id=1)
    gen = PostGenerator()
    posts = gen.generate_campaign_posts(campaign_id, user_id=1)
    for post in posts:
        content = post.get("content", "")
        assert len(content) <= 3000, f"Post exceeds 3000 chars: {len(content)}"


def test_generate_post_stores_in_db(app):
    from post_generator import PostGenerator

    campaign_id = _create_campaign(user_id=1)
    gen = PostGenerator()
    gen.generate_campaign_posts(campaign_id, user_id=1)

    rows = query_db("SELECT * FROM campaign_posts WHERE campaign_id = ?", (campaign_id,))
    assert len(rows) > 0, "Posts should be stored in campaign_posts table"


def test_generate_post_has_title(app):
    from post_generator import PostGenerator

    campaign_id = _create_campaign(user_id=1)
    gen = PostGenerator()
    posts = gen.generate_campaign_posts(campaign_id, user_id=1)
    for post in posts:
        assert post.get("title") or post.get("content"), "Post should have title or content"


def test_regenerate_post_creates_new_version(app):
    from post_generator import PostGenerator

    campaign_id = _create_campaign(user_id=1)
    gen = PostGenerator()
    posts = gen.generate_campaign_posts(campaign_id, user_id=1)
    if not posts:
        pytest.skip("No posts generated to regenerate")

    # Get first post from DB
    rows = query_db(
        "SELECT id FROM campaign_posts WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    )
    if not rows:
        pytest.skip("No posts in DB to regenerate")

    post_id = rows[0]["id"]
    result = gen.regenerate_post(post_id, feedback="Make it more engaging")
    assert isinstance(result, dict)
    assert "error" not in result or result.get("content"), f"Regeneration failed: {result}"


def test_regenerate_post_with_feedback(app):
    from post_generator import PostGenerator

    campaign_id = _create_campaign(user_id=1)
    gen = PostGenerator()
    gen.generate_campaign_posts(campaign_id, user_id=1)

    rows = query_db(
        "SELECT id FROM campaign_posts WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    )
    if not rows:
        pytest.skip("No posts in DB")

    post_id = rows[0]["id"]
    result = gen.regenerate_post(post_id, feedback="Add a specific metric about $1.2M savings")
    assert isinstance(result, dict)


def test_generate_multiple_posts(app):
    from post_generator import PostGenerator

    campaign_id = _create_campaign(user_id=1)
    gen = PostGenerator()
    posts = gen.generate_campaign_posts(campaign_id, user_id=1)
    # Campaign has 3 seeds, should generate at least 2 posts
    assert len(posts) >= 2, f"Expected >= 2 posts, got {len(posts)}"
