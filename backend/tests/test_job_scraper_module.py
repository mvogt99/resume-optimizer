"""Unit tests for job_scraper module — parsing, cleaning, scraping.

No Flask client needed. Tests pure functions with HTML fixture injection.
"""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


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

TITLE_ONLY_HTML = "<html><head><title>Test Job</title></head><body></body></html>"


def _make_fetcher(html):
    """Return a fetcher callable that returns static HTML for any URL."""

    def fetcher(url):
        return html

    return fetcher


class TestJobScraperModule:
    def test_scrape_invalid_url(self):
        from job_scraper import scrape_job_url

        result = scrape_job_url("")
        assert result["error"]
        assert result["title"] == ""

    def test_scrape_none_url(self):
        from job_scraper import scrape_job_url

        result = scrape_job_url(None)
        assert result["error"]

    def test_scrape_malformed_url(self):
        from job_scraper import scrape_job_url

        result = scrape_job_url("not-a-url")
        assert result["error"]

    def test_scrape_multiple_empty(self):
        from job_scraper import scrape_multiple

        results = scrape_multiple([])
        assert results == []

    def test_ld_json_parsing(self):
        from bs4 import BeautifulSoup
        from job_scraper import _parse_ld_json

        html = """<html><head><script type="application/ld+json">
        {"@type": "JobPosting", "title": "Software Engineer",
         "hiringOrganization": {"name": "Acme Corp"},
         "description": "Build things",
         "jobLocation": {"address": {"addressLocality": "NYC", "addressRegion": "NY"}}}
        </script></head></html>"""
        soup = BeautifulSoup(html, "html.parser")
        result = _parse_ld_json(soup)
        assert result["title"] == "Software Engineer"
        assert result["company"] == "Acme Corp"
        assert "NYC" in result["location"]

    def test_ld_json_with_graph(self):
        from bs4 import BeautifulSoup
        from job_scraper import _parse_ld_json

        html = """<html><head><script type="application/ld+json">
        {"@graph": [{"@type": "JobPosting", "title": "Dev",
         "hiringOrganization": {"name": "ACME"}, "description": "coding"}]}
        </script></head></html>"""
        soup = BeautifulSoup(html, "html.parser")
        result = _parse_ld_json(soup)
        assert result["title"] == "Dev"

    def test_ld_json_array(self):
        from bs4 import BeautifulSoup
        from job_scraper import _parse_ld_json

        html = """<html><head><script type="application/ld+json">
        [{"@type": "Organization", "name": "X"}, {"@type": "JobPosting", "title": "PM", "hiringOrganization": "Corp"}]
        </script></head></html>"""
        soup = BeautifulSoup(html, "html.parser")
        result = _parse_ld_json(soup)
        assert result["title"] == "PM"
        assert result["company"] == "Corp"

    def test_ld_json_salary(self):
        from bs4 import BeautifulSoup
        from job_scraper import _parse_ld_json

        html = """<html><head><script type="application/ld+json">
        {"@type": "JobPosting", "title": "Dev",
         "baseSalary": {"currency": "USD", "value": {"minValue": 100000, "maxValue": 150000}},
         "description": "test"}
        </script></head></html>"""
        soup = BeautifulSoup(html, "html.parser")
        result = _parse_ld_json(soup)
        assert "100000" in result.get("salary_range", "")
        assert "150000" in result.get("salary_range", "")

    def test_meta_tag_parsing(self):
        from bs4 import BeautifulSoup
        from job_scraper import _parse_meta_tags

        html = """<html><head>
        <meta property="og:title" content="Senior Dev" />
        <meta name="description" content="A great job" />
        <meta property="og:site_name" content="Jobs Inc" />
        </head></html>"""
        soup = BeautifulSoup(html, "html.parser")
        result = _parse_meta_tags(soup)
        assert result["title"] == "Senior Dev"
        assert result["description"] == "A great job"
        assert result["company"] == "Jobs Inc"

    def test_heuristic_salary_extraction(self):
        from bs4 import BeautifulSoup
        from job_scraper import _parse_heuristic

        html = "<html><body>Salary: $120,000 - $180,000 per year</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = _parse_heuristic(soup)
        assert "120,000" in result.get("salary_range", "")

    def test_heuristic_requirements_extraction(self):
        from bs4 import BeautifulSoup
        from job_scraper import _parse_heuristic

        html = "<html><body>Requirements:\n- Python\n- AWS\n- Docker\n\nBenefits:</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = _parse_heuristic(soup)
        assert "Python" in result.get("requirements", "")

    def test_clean_html_content(self):
        from job_scraper import _clean

        assert _clean("<b>Hello</b> <i>World</i>") == "Hello World"
        assert _clean("  spaces   between  ") == "spaces between"
        assert _clean("") == ""
        assert _clean(None) == ""

    def test_scrape_with_injected_html(self):
        """Full scrape pipeline using _fetch_html parameter injection."""
        from job_scraper import scrape_job_url

        result = scrape_job_url(
            "https://example.com/job/123",
            _fetch_html=_make_fetcher(LD_JSON_HTML),
        )
        assert result["title"] == "Platform Engineer"
        assert result["company"] == "TechCo"
        assert result["source"] == "example.com"
        assert result["error"] == ""

    def test_scrape_with_fetcher_returning_none(self):
        """Fetcher returning None triggers error path."""
        from job_scraper import scrape_job_url

        result = scrape_job_url(
            "https://example.com/job",
            _fetch_html=lambda url: None,
        )
        assert "Fetch failed" in result["error"]

    def test_scrape_multiple_with_fetcher(self):
        """Batch scrape using _fetch_html parameter."""
        from job_scraper import scrape_multiple

        results = scrape_multiple(
            ["https://a.com/1", "https://b.com/2"],
            _fetch_html=_make_fetcher(BULK_HTML),
        )
        assert len(results) == 2
        assert results[0]["title"] == "Backend Dev"
        assert results[1]["company"] == "Co"

    def test_title_tag_fallback(self):
        """When no LD+JSON or meta, falls back to <title> tag."""
        from job_scraper import scrape_job_url

        result = scrape_job_url(
            "https://example.com/job",
            _fetch_html=_make_fetcher(TITLE_ONLY_HTML),
        )
        assert result["title"] == "Test Job"
