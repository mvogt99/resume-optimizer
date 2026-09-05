"""Tests for personaforge_client.py — pf_recall, pf_remember, pf_feedback."""

import time
from unittest.mock import MagicMock, patch

import httpx
import personaforge_client as pfc
import pytest

pytestmark = pytest.mark.real_pf  # skip conftest _block_personaforge fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code=200, json_data=None, raise_exc=None):
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = str(json_data or {})
    if raise_exc:
        resp.raise_for_status.side_effect = raise_exc
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_default_pf_url(self):
        assert pfc.PF_URL.startswith("http")

    def test_cache_ttl_positive(self):
        assert pfc._CACHE_TTL > 0

    def test_career_namespace_defined(self):
        assert pfc.CAREER_NAMESPACE
        assert isinstance(pfc.CAREER_NAMESPACE, str)


# ---------------------------------------------------------------------------
# pf_recall
# ---------------------------------------------------------------------------


class TestPfRecall:
    def setup_method(self):
        """Clear cache before each test."""
        pfc._recall_cache.clear()

    def test_returns_context_string_on_success(self):
        payload = {"context": {"compiled_context": "You are an enterprise architect."}}
        with patch(
            "personaforge_client.httpx.post", return_value=_mock_response(json_data=payload)
        ):
            result = pfc.pf_recall("career_profile", "write a resume summary")
        assert result == "You are an enterprise architect."

    def test_returns_none_on_connection_error(self):

        with patch(
            "personaforge_client.httpx.post", side_effect=httpx.ConnectError("connection failed")
        ):
            result = pfc.pf_recall("career_profile", "any task")
        assert result is None

    def test_returns_none_on_timeout(self):

        with patch("personaforge_client.httpx.post", side_effect=httpx.TimeoutException("timeout")):
            result = pfc.pf_recall("career_profile", "any task")
        assert result is None

    def test_returns_none_on_http_error(self):

        resp = _mock_response(
            status_code=500,
            raise_exc=httpx.HTTPStatusError("http error", request=MagicMock(), response=MagicMock(status_code=500, text="err")),
        )
        with patch("personaforge_client.httpx.post", return_value=resp):
            result = pfc.pf_recall("career_profile", "any task")
        assert result is None

    def test_returns_none_on_empty_context(self):
        payload = {"context": {"compiled_context": ""}}
        with patch(
            "personaforge_client.httpx.post", return_value=_mock_response(json_data=payload)
        ):
            result = pfc.pf_recall("career_profile", "any task")
        assert result is None

    def test_returns_none_on_missing_context_key(self):
        with patch("personaforge_client.httpx.post", return_value=_mock_response(json_data={})):
            result = pfc.pf_recall("career_profile", "any task")
        assert result is None

    def test_caches_result(self):
        payload = {"context": {"compiled_context": "cached persona"}}
        mock_post = MagicMock(return_value=_mock_response(json_data=payload))
        with patch("personaforge_client.httpx.post", mock_post):
            r1 = pfc.pf_recall("career_profile", "same task")
            r2 = pfc.pf_recall("career_profile", "same task")
        assert r1 == r2 == "cached persona"
        assert mock_post.call_count == 1  # second call hits cache

    def test_cache_miss_on_different_query(self):
        payload = {"context": {"compiled_context": "persona"}}
        mock_post = MagicMock(return_value=_mock_response(json_data=payload))
        with patch("personaforge_client.httpx.post", mock_post):
            pfc.pf_recall("career_profile", "task A")
            pfc.pf_recall("career_profile", "task B")
        assert mock_post.call_count == 2

    def test_cache_expires_after_ttl(self):
        payload = {"context": {"compiled_context": "fresh"}}
        mock_post = MagicMock(return_value=_mock_response(json_data=payload))
        with patch("personaforge_client.httpx.post", mock_post):
            pfc.pf_recall("career_profile", "ttl task")
            # Manually expire the cache entry
            for key in pfc._recall_cache:
                pfc._recall_cache[key] = (
                    pfc._recall_cache[key][0],
                    time.monotonic() - pfc._CACHE_TTL - 1,
                )
            pfc.pf_recall("career_profile", "ttl task")
        assert mock_post.call_count == 2

    def test_sends_correct_namespace_in_payload(self):
        payload = {"context": {"compiled_context": "ok"}}
        mock_post = MagicMock(return_value=_mock_response(json_data=payload))
        with patch("personaforge_client.httpx.post", mock_post):
            pfc.pf_recall("my_namespace", "some query")
        call_kwargs = mock_post.call_args
        sent_payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
        assert sent_payload.get("namespace") == "my_namespace"

    def test_never_raises(self):
        with patch("personaforge_client.httpx.post", side_effect=RuntimeError("boom")):
            result = pfc.pf_recall("career_profile", "any")
        assert result is None  # Never raises, always returns None on error


# ---------------------------------------------------------------------------
# pf_remember
# ---------------------------------------------------------------------------


class TestPfRemember:
    def test_returns_none_on_success(self):
        with patch(
            "personaforge_client.httpx.post", return_value=_mock_response(status_code=200)
        ):
            result = pfc.pf_remember("career_profile", "STAR bullet worked well", {})
        assert result is None

    def test_never_raises_on_connection_error(self):

        with patch(
            "personaforge_client.httpx.post", side_effect=httpx.ConnectError("connection failed")
        ):
            result = pfc.pf_remember("career_profile", "content", {})
        assert result is None

    def test_never_raises_on_exception(self):
        with patch("personaforge_client.httpx.post", side_effect=RuntimeError("boom")):
            result = pfc.pf_remember("career_profile", "content", {})
        assert result is None

    def test_sends_namespace_and_content(self):
        mock_post = MagicMock(return_value=_mock_response())
        with patch("personaforge_client.httpx.post", mock_post):
            pfc.pf_remember("test_ns", "my content", {"source": "resume"})
        call_kwargs = mock_post.call_args
        sent = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
        assert sent.get("namespace") == "test_ns"
        assert sent.get("content") == "my content"

    def test_sends_metadata(self):
        mock_post = MagicMock(return_value=_mock_response())
        metadata = {"output_type": "cover_letter", "gap": 22}
        with patch("personaforge_client.httpx.post", mock_post):
            pfc.pf_remember("career_profile", "good output", metadata)
        sent = mock_post.call_args[1]["json"]
        assert sent.get("metadata") == metadata


# ---------------------------------------------------------------------------
# pf_feedback
# ---------------------------------------------------------------------------


class TestPfFeedback:
    def test_returns_none_on_success(self):
        with patch("personaforge_client.httpx.post", return_value=_mock_response()):
            result = pfc.pf_feedback("pass", 0.9)
        assert result is None

    def test_never_raises_on_error(self):
        with patch("personaforge_client.httpx.post", side_effect=RuntimeError("boom")):
            result = pfc.pf_feedback("fail", 0.1)
        assert result is None

    def test_sends_outcome_and_confidence(self):
        mock_post = MagicMock(return_value=_mock_response())
        with patch("personaforge_client.httpx.post", mock_post):
            pfc.pf_feedback("pass", 0.85)
        sent = mock_post.call_args[1]["json"]
        assert sent.get("outcome") == "pass"
        assert sent.get("confidence") == 0.85


# ---------------------------------------------------------------------------
# Cache key stability
# ---------------------------------------------------------------------------


class TestCacheKey:
    def test_same_inputs_same_key(self):
        k1 = pfc._make_cache_key("career_profile", "write a summary")
        k2 = pfc._make_cache_key("career_profile", "write a summary")
        assert k1 == k2

    def test_different_namespace_different_key(self):
        k1 = pfc._make_cache_key("ns_a", "task")
        k2 = pfc._make_cache_key("ns_b", "task")
        assert k1 != k2

    def test_different_query_different_key(self):
        k1 = pfc._make_cache_key("ns", "task A")
        k2 = pfc._make_cache_key("ns", "task B")
        assert k1 != k2
