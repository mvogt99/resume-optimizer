"""Tests for migrate_qdrant_to_journey_sources() migration function."""
import hashlib
import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
import requests

from migrate_qdrant_to_sqlite import migrate_qdrant_to_journey_sources

_DDL = """
CREATE TABLE IF NOT EXISTS journey_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT, source_path TEXT, content_hash TEXT UNIQUE,
    title TEXT, content_preview TEXT, full_text TEXT, classification TEXT,
    event_date TEXT, metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, user_id INTEGER DEFAULT 0
)
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute(_DDL)
    c.commit()
    return c


def make_qdrant_resp(points, next_offset=None):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": {"points": points, "next_page_offset": next_offset},
        "status": "ok",
    }
    return mock_resp


POINT1 = {"id": 1, "payload": {"content": "Successful coding task retrieved from Qdrant collection.", "category": "coding", "timestamp": "2026-03-10T10:00:00.000000"}}
POINT2 = {"id": 2, "payload": {"content": "Successful reasoning task with detailed explanation of approach.", "category": "reasoning", "timestamp": "2026-03-11T10:00:00.000000"}}
POINT3 = {"id": 3, "payload": {"content": "Planning task completed with architecture decision recorded.", "category": "planning", "timestamp": "2026-03-12T10:00:00.000000"}}


def test_happy_path_inserts_new_records(conn):
    mock_resp = make_qdrant_resp([POINT1, POINT2, POINT3])

    with patch("migrate_qdrant_to_sqlite.requests.post", return_value=mock_resp):
        result = migrate_qdrant_to_journey_sources(conn, "http://fake.url", "hybrid_ai_learnings")

    assert result == 3
    rows = conn.execute("SELECT source_type, source_path FROM journey_sources").fetchall()
    assert len(rows) == 3
    assert all(r[0] == "qdrant" for r in rows)


def test_pagination_two_pages(conn):
    mock_page1 = make_qdrant_resp([POINT1, POINT2], next_offset=100)
    mock_page2 = make_qdrant_resp([POINT3])

    with patch("migrate_qdrant_to_sqlite.requests.post") as mock_post:
        mock_post.side_effect = [mock_page1, mock_page2]
        result = migrate_qdrant_to_journey_sources(conn, "http://fake.url", "hybrid_ai_learnings")

    assert result == 3
    count = conn.execute("SELECT COUNT(*) FROM journey_sources WHERE source_type='qdrant'").fetchone()[0]
    assert count == 3


def test_skips_existing_records(conn):
    existing_content = POINT1["payload"]["content"]
    existing_hash = hashlib.sha256(existing_content.encode()).hexdigest()
    conn.execute(
        "INSERT INTO journey_sources (source_type, source_path, content_hash, title, content_preview, "
        "full_text, classification, event_date, metadata_json, user_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("qdrant", "hybrid_ai_learnings/1", existing_hash, "Qdrant: coding (1)",
         existing_content[:500], existing_content, "knowledge_base", "2026-03-10",
         json.dumps({"collection": "hybrid_ai_learnings", "qdrant_id": 1, "category": "coding"}), 0),
    )
    conn.commit()

    mock_resp = make_qdrant_resp([POINT1, POINT2])
    with patch("migrate_qdrant_to_sqlite.requests.post", return_value=mock_resp):
        result = migrate_qdrant_to_journey_sources(conn, "http://fake.url", "hybrid_ai_learnings")

    assert result == 1
    count = conn.execute("SELECT COUNT(*) FROM journey_sources WHERE source_type='qdrant'").fetchone()[0]
    assert count == 2


def test_qdrant_unavailable_returns_zero(conn):
    with patch("migrate_qdrant_to_sqlite.requests.post", side_effect=requests.exceptions.ConnectionError):
        result = migrate_qdrant_to_journey_sources(conn, "http://fake.url", "hybrid_ai_learnings")

    assert result == 0
    count = conn.execute("SELECT COUNT(*) FROM journey_sources WHERE source_type='qdrant'").fetchone()[0]
    assert count == 0


def test_content_hash_collision_handled_gracefully(conn):
    """Two different Qdrant IDs with identical content — second must not crash."""
    shared_content = "Identical content from two different qdrant point ids for test."
    point_a = {"id": 101, "payload": {"content": shared_content, "category": "coding", "timestamp": "2026-03-10T10:00:00"}}
    point_b = {"id": 202, "payload": {"content": shared_content, "category": "coding", "timestamp": "2026-03-10T11:00:00"}}

    mock_resp = make_qdrant_resp([point_a, point_b])
    with patch("migrate_qdrant_to_sqlite.requests.post", return_value=mock_resp):
        result = migrate_qdrant_to_journey_sources(conn, "http://fake.url", "hybrid_ai_learnings")

    assert result == 1
    count = conn.execute("SELECT COUNT(*) FROM journey_sources WHERE source_type='qdrant'").fetchone()[0]
    assert count == 1
