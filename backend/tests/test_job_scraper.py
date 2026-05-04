"""Route tests for job URL scraper and import endpoints (Phase 13.2).

No mocks — uses _test_fetcher module hook for HTML injection.
Unit tests for scraper module are in test_job_scraper_module.py.
"""

import json

import pytest
from test_helpers import AGENT_HEADERS_1, AGENT_HEADERS_2, JD_TEXT, query_db

# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

LD_JSON_HTML = """<html><head><script type="application/ld+json">
{"@type": "JobPosting", "title": "Platform Engineer",
 "hiringOrganization": {"name": "TechCo"},
 "description": "Build infrastructure",
 "jobLocation": {"address": {"addressLocality": "SF", "addressRegion": "CA"}}}
</script></head><body></body></html>"""

BULK_HTML = """<html><head><script type="application/ld+json">
{"@type": "JobPosting", "title": "Backend Dev",
 "hiringOrganization": {"name": "Co"},
 "description": "Python developer needed"}
</script></head></html>"""


def _make_fetcher(html):
    """Return a fetcher callable that returns static HTML for any URL."""

    def fetcher(url):
        return html

    return fetcher


# ---------------------------------------------------------------------------
# Route integration tests (using _test_fetcher module hook)
# ---------------------------------------------------------------------------


class TestScraperRoutes:
    @pytest.fixture(autouse=True)
    def _set_test_fetcher(self):
        """Install and remove module-level test fetcher for route tests."""
        import job_scraper

        job_scraper._test_fetcher = _make_fetcher(LD_JSON_HTML)
        yield
        job_scraper._test_fetcher = None

    def test_scrape_url_missing(self, client, auth_headers):
        resp = client.post("/api/agents/scout/scrape-url", headers=auth_headers, json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert isinstance(data["error"], str)

    def test_scrape_url_returns_posting(self, client, auth_headers):
        resp = client.post(
            "/api/agents/scout/scrape-url",
            headers=auth_headers,
            json={"url": "https://example.com/job"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "posting" in data
        assert data["posting"]["title"] == "Platform Engineer"
        assert data["posting"]["company"] == "TechCo"
        assert data["posting"]["source"] == "example.com"
        assert isinstance(data["posting"]["description"], str)
        assert len(data["posting"]["description"]) > 0
        # DB: scrape-url does NOT auto-save posting
        rows = query_db("SELECT id FROM job_postings WHERE user_id = 1")
        assert len(rows) == 0

    def test_import_url_missing(self, client, auth_headers):
        resp = client.post("/api/agents/scout/import-url", headers=auth_headers, json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert isinstance(data["error"], str)

    def test_import_url_saves_posting(self, client, auth_headers):
        resp = client.post(
            "/api/agents/scout/import-url",
            headers=auth_headers,
            json={"url": "https://example.com/job/42"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "posting_id" in data
        assert data["scraped"]["title"] == "Platform Engineer"
        assert data["scraped"]["company"] == "TechCo"
        # DB: verify posting persisted
        rows = query_db(
            "SELECT title, company, source FROM job_postings WHERE id = ?", (data["posting_id"],)
        )
        assert len(rows) == 1
        assert rows[0]["title"] == "Platform Engineer"
        assert rows[0]["company"] == "TechCo"
        assert rows[0]["source"] == "example.com"

    def test_bulk_import_empty(self, client, auth_headers):
        resp = client.post("/api/agents/scout/bulk-import", headers=auth_headers, json={"urls": []})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert isinstance(data["error"], str)

    def test_bulk_import_creates_postings(self, client, auth_headers):
        import job_scraper

        job_scraper._test_fetcher = _make_fetcher(BULK_HTML)
        resp = client.post(
            "/api/agents/scout/bulk-import",
            headers=auth_headers,
            json={"urls": ["https://a.com/1", "https://b.com/2"]},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["count"] == 2
        assert len(data["imported"]) == 2
        assert data["imported"][0]["title"] == "Backend Dev"
        assert data["imported"][1]["title"] == "Backend Dev"
        # DB: verify both postings persisted
        rows = query_db("SELECT title, company FROM job_postings WHERE user_id = 1 ORDER BY id")
        assert len(rows) >= 2
        assert rows[0]["title"] == "Backend Dev"
        assert rows[0]["company"] == "Co"

    def test_scrape_url_auth_required(self, client):
        resp = client.post("/api/agents/scout/scrape-url", json={"url": "https://x.com"})
        assert resp.status_code == 401
        data = resp.get_json()
        assert "error" in data or "message" in data

    def test_import_url_auth_required(self, client):
        resp = client.post("/api/agents/scout/import-url", json={"url": "https://x.com"})
        assert resp.status_code == 401
        data = resp.get_json()
        assert "error" in data or "message" in data

    def test_bulk_import_auth_required(self, client):
        resp = client.post("/api/agents/scout/bulk-import", json={"urls": ["https://x.com"]})
        assert resp.status_code == 401
        data = resp.get_json()
        assert "error" in data or "message" in data

    def test_import_url_location_parsed(self, client, auth_headers):
        """Import URL parses location from LD+JSON."""
        resp = client.post(
            "/api/agents/scout/import-url",
            headers=auth_headers,
            json={"url": "https://example.com/job/loc"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["scraped"]["location"] == "SF, CA"
        # DB: verify location stored
        rows = query_db("SELECT location FROM job_postings WHERE id = ?", (data["posting_id"],))
        assert len(rows) == 1
        assert "SF" in rows[0]["location"]
