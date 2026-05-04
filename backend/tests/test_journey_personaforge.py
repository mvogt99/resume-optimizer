"""Tests for _mine_personaforge() PersonaForge API mining."""
from unittest.mock import MagicMock, patch

from journey_miner_enrichment_mixin import EnrichmentMixin


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


def test_career_profile_happy_path():
    miner = TestMiner()
    docs = [
        {
            "_key": "mem-abc001",
            "content": "Resume tailor pattern: enterprise architecture skills analysis.",
            "created_at": "2026-03-28T01:25:52.885461+00:00",
            "metadata": {"category": "pattern", "confidence": 0.75},
        },
        {
            "_key": "mem-abc002",
            "content": "Failure teaching: missing skill gap for data architecture role.",
            "created_at": "2026-03-29T10:00:00.000000+00:00",
            "metadata": {"category": "failure_teaching", "confidence": 0.70},
        },
    ]
    mock_client = _make_arango_mock(docs)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"items": [], "diagnostics": {}}

    with patch("journey_miner_enrichment_mixin._ArangoClient", return_value=mock_client), \
         patch("journey_miner_enrichment_mixin.requests.post", return_value=mock_resp):
        result = miner._mine_personaforge()

    assert result == 2
    assert all(item["source_type"] == "personaforge" for item in miner._stored)
    assert all(item["source_path"].startswith("personaforge/career_profile/") for item in miner._stored)


def test_project_knowledge_happy_path():
    miner = TestMiner()
    mock_client = _make_arango_mock([])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [
            {
                "memory_id": "mem-pk001",
                "content": "Enterprise architecture integration technology stack knowledge base.",
                "score": 0.87,
                "namespace": "project_knowledge",
                "source": "vector",
                "rationale": "high similarity",
                "component_scores": {},
            },
            {
                "memory_id": "mem-pk002",
                "content": "Career achievement milestone delivery leadership excellence.",
                "score": 0.81,
                "namespace": "project_knowledge",
                "source": "vector",
                "rationale": "high similarity",
                "component_scores": {},
            },
        ],
        "diagnostics": {},
    }

    with patch("journey_miner_enrichment_mixin._ArangoClient", return_value=mock_client), \
         patch("journey_miner_enrichment_mixin.requests.post", return_value=mock_resp):
        result = miner._mine_personaforge()

    assert result == 2
    assert all(item["source_path"].startswith("personaforge/project_knowledge/") for item in miner._stored)


def test_arango_unavailable_falls_through():
    miner = TestMiner()
    mock_client = MagicMock()
    mock_client.db.side_effect = Exception("down")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [
            {
                "memory_id": "mem-pk999",
                "content": "Project knowledge item retrieved despite ArangoDB being down.",
                "score": 0.75,
                "namespace": "project_knowledge",
                "source": "vector",
                "rationale": "fallback",
                "component_scores": {},
            }
        ],
        "diagnostics": {},
    }

    with patch("journey_miner_enrichment_mixin._ArangoClient", return_value=mock_client), \
         patch("journey_miner_enrichment_mixin.requests.post", return_value=mock_resp):
        result = miner._mine_personaforge()

    assert result == 1
    assert len(miner._stored) == 1


def test_deduplication():
    miner = TestMiner()
    shared_content = "duplicate content for dedup test check abcdefgh ijklmnop"
    docs = [
        {
            "_key": "mem-dup001",
            "content": shared_content,
            "created_at": "2026-03-28T01:00:00.000000+00:00",
            "metadata": {"category": "pattern"},
        }
    ]
    mock_client = _make_arango_mock(docs)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [
            {
                "memory_id": "mem-dup002",
                "content": shared_content,
                "score": 0.90,
                "namespace": "project_knowledge",
                "source": "vector",
                "rationale": "exact match",
                "component_scores": {},
            }
        ],
        "diagnostics": {},
    }

    with patch("journey_miner_enrichment_mixin._ArangoClient", return_value=mock_client), \
         patch("journey_miner_enrichment_mixin.requests.post", return_value=mock_resp):
        result = miner._mine_personaforge()

    assert result == 1
    assert len(miner._stored) == 1
