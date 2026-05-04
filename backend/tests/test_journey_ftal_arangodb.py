"""Tests for _mine_ftal_history() ArangoDB replacement."""
import contextlib
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from journey_miner_enrichment_mixin import EnrichmentMixin

_JOURNEY_SOURCES_DDL = """
CREATE TABLE IF NOT EXISTS journey_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT, source_path TEXT, content_hash TEXT UNIQUE,
    title TEXT, content_preview TEXT, full_text TEXT, classification TEXT,
    event_date TEXT, metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, user_id INTEGER DEFAULT 0
)
"""


def make_db(rows=None):
    conn = sqlite3.connect(":memory:")
    conn.execute(_JOURNEY_SOURCES_DDL)
    conn.commit()
    if rows:
        conn.executemany(
            "INSERT INTO journey_sources "
            "(source_type, source_path, content_hash, title, content_preview, "
            "full_text, classification, event_date, metadata_json, user_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
    return conn


class TestMiner(EnrichmentMixin):
    def __init__(self):
        self._stored = []

    def _store_source(self, **kwargs):
        self._stored.append(kwargs)


def _make_arango_mock(docs):
    mock_cursor = MagicMock()
    mock_cursor.__iter__ = MagicMock(return_value=iter(docs))
    mock_db = MagicMock()
    mock_db.aql.execute.return_value = mock_cursor
    mock_client = MagicMock()
    mock_client.db.return_value = mock_db
    return mock_client


SAMPLE_DOCS = [
    {
        "_key": "k1",
        "content": "long content text here abc def ghi jkl mno pqr",
        "learning_type": "pattern",
        "domain": "async",
        "f_score": 25,
        "t_score": 25,
        "a_score": 25,
        "l_score": 15,
        "created_at": "2026-04-15",
    },
    {
        "_key": "k2",
        "content": "another long content text here abc def ghi jkl mno",
        "learning_type": "anti_pattern",
        "domain": "database",
        "f_score": 30,
        "t_score": 30,
        "a_score": 20,
        "l_score": 10,
        "created_at": "2026-04-15",
    },
    {
        "_key": "k3",
        "content": "yet another long content text here abc def ghi jkl",
        "learning_type": "best_practice",
        "domain": "testing",
        "f_score": 20,
        "t_score": 20,
        "a_score": 30,
        "l_score": 20,
        "created_at": "2026-04-16",
    },
]


def test_happy_path():
    conn = make_db()
    miner = TestMiner()
    mock_client = _make_arango_mock(SAMPLE_DOCS)

    with patch("journey_miner_enrichment_mixin.get_db", return_value=conn), \
         patch("journey_miner_enrichment_mixin._ArangoClient", return_value=mock_client):
        result = miner._mine_ftal_history(user_id=1)

    assert result == 3
    assert len(miner._stored) == 3
    assert all(s["source_type"] == "ftal_history" for s in miner._stored)


def test_watermark_blocks_old_records():
    conn = make_db(
        rows=[("ftal_history", "arangodb/learnings/old_key", "old_hash",
               "FTAL: old - old", "old preview", "old full text",
               "ftal_task", "2026-04-19", "{}", 1)]
    )
    miner = TestMiner()
    mock_client = _make_arango_mock([])

    with patch("journey_miner_enrichment_mixin.get_db", return_value=conn), \
         patch("journey_miner_enrichment_mixin._ArangoClient", return_value=mock_client):
        result = miner._mine_ftal_history(user_id=1)

    assert result == 0
    count = conn.execute("SELECT COUNT(*) FROM journey_sources WHERE user_id=1").fetchone()[0]
    assert count == 1


def test_arango_unavailable():
    conn = make_db()
    miner = TestMiner()

    with patch("journey_miner_enrichment_mixin.get_db", return_value=conn), \
         patch("journey_miner_enrichment_mixin._ArangoClient", side_effect=Exception("down")):
        result = miner._mine_ftal_history(user_id=1)

    assert result == 0


def test_empty_collection():
    conn = make_db()
    miner = TestMiner()
    mock_client = _make_arango_mock([])

    with patch("journey_miner_enrichment_mixin.get_db", return_value=conn), \
         patch("journey_miner_enrichment_mixin._ArangoClient", return_value=mock_client):
        result = miner._mine_ftal_history(user_id=1)

    assert result == 0
