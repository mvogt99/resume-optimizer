"""Job posting URL scraper — extracts structured data from job listing URLs."""

import json
import logging
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Test hook: set to a callable(url) -> html_string to bypass HTTP requests.
# Used by integration tests to avoid mocking.
_test_fetcher = None

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
]


def scrape_job_url(url, _fetch_html=None):
    """Scrape a job posting URL and return structured data.

    Args:
        url: Job posting URL to scrape.
        _fetch_html: Optional callable(url) -> html_string for testing.

    Returns dict: {title, company, location, description, requirements,
                   salary_range, url, source, error}
    """
    if not url or not isinstance(url, str):
        return _empty(url, "Invalid URL")

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return _empty(url, "Invalid URL format")

    source = parsed.netloc.replace("www.", "")

    fetcher = _fetch_html or _test_fetcher
    if fetcher is not None:
        html = fetcher(url)
        if html is None:
            return _empty(url, "Fetch failed: fetcher returned None")
    else:
        try:
            resp = httpx.get(
                url,
                timeout=15,
                headers={"User-Agent": _USER_AGENTS[0]},
                follow_redirects=True,
            )
            resp.raise_for_status()
        except (httpx.RequestError, httpx.HTTPError) as exc:
            return _empty(url, f"Fetch failed: {exc}")
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")

    # Layer 1: LD+JSON schema.org/JobPosting (most reliable)
    result = _parse_ld_json(soup)

    # Layer 2: OpenGraph / meta tags (fill gaps)
    meta = _parse_meta_tags(soup)
    for k, v in meta.items():
        if v and not result.get(k):
            result[k] = v

    # Layer 3: Heuristic text extraction (fill remaining gaps)
    heuristic = _parse_heuristic(soup)
    for k, v in heuristic.items():
        if v and not result.get(k):
            result[k] = v

    # Layer 4: title tag fallback
    if not result.get("title") and soup.title:
        result["title"] = _clean(soup.title.string or "")

    # Layer 5: LLM fallback when all parsers returned empty
    if not result.get("title") and not result.get("description"):
        llm_result = _parse_llm_fallback(soup.get_text(separator="\n")[:4000])
        for k, v in llm_result.items():
            if v and not result.get(k):
                result[k] = v

    result["url"] = url
    result["source"] = source
    result.setdefault("title", "")
    result.setdefault("company", "")
    result.setdefault("location", "")
    result.setdefault("description", "")
    result.setdefault("requirements", "")
    result.setdefault("salary_range", "")
    result.setdefault("error", "")
    return result


def scrape_multiple(urls, _fetch_html=None, delay=1.0):
    """Scrape multiple URLs. Returns list of result dicts.

    Args:
        urls: List of URLs to scrape.
        _fetch_html: Optional callable(url) -> html_string for testing.
        delay: Seconds between requests (rate limiting). Set to 0 for tests.
    """
    import time

    results = []
    for i, url in enumerate(urls):
        results.append(scrape_job_url(url.strip(), _fetch_html=_fetch_html))
        # Rate-limit real HTTP requests (skip delay for test fetchers and last URL)
        if delay > 0 and _fetch_html is None and _test_fetcher is None and i < len(urls) - 1:
            time.sleep(delay)
    return results


# ---------------------------------------------------------------------------
# Internal parsers
# ---------------------------------------------------------------------------


def _empty(url, error):
    return {
        "title": "",
        "company": "",
        "location": "",
        "description": "",
        "requirements": "",
        "salary_range": "",
        "url": url or "",
        "source": "",
        "error": error,
    }


def _clean(text):
    """Strip HTML and normalize whitespace."""
    if not text:
        return ""
    if "<" in text:
        text = BeautifulSoup(text, "html.parser").get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_ld_json(soup):
    """Extract from schema.org/JobPosting LD+JSON."""
    result = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle arrays
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            # Check @graph
            if "@graph" in item:
                items.extend(item["@graph"])
                continue
            if item.get("@type") not in ("JobPosting", "jobPosting"):
                continue

            result["title"] = item.get("title", "")
            org = item.get("hiringOrganization", {})
            if isinstance(org, dict):
                result["company"] = org.get("name", "")
            elif isinstance(org, str):
                result["company"] = org

            loc = item.get("jobLocation")
            if isinstance(loc, dict):
                addr = loc.get("address", loc)
                if isinstance(addr, dict):
                    parts = [
                        addr.get("addressLocality", ""),
                        addr.get("addressRegion", ""),
                        addr.get("addressCountry", ""),
                    ]
                    result["location"] = ", ".join(p for p in parts if p)
            elif isinstance(loc, list) and loc:
                result["location"] = str(loc[0].get("address", {}).get("addressLocality", ""))

            result["description"] = _clean(item.get("description", ""))
            result["requirements"] = _clean(
                item.get("qualifications", item.get("experienceRequirements", ""))
            )

            salary = item.get("baseSalary")
            if isinstance(salary, dict):
                value = salary.get("value", {})
                if isinstance(value, dict):
                    lo = value.get("minValue", "")
                    hi = value.get("maxValue", "")
                    cur = salary.get("currency", "USD")
                    if lo and hi:
                        result["salary_range"] = f"{cur} {lo}-{hi}"
                elif value:
                    result["salary_range"] = f"{salary.get('currency', 'USD')} {value}"

            break  # Only use first JobPosting found
    return result


def _parse_meta_tags(soup):
    """Extract from meta tags (og:*, twitter:*, standard)."""
    result = {}

    def meta(name=None, prop=None):
        tag = None
        if name:
            tag = soup.find("meta", attrs={"name": name})
        if not tag and prop:
            tag = soup.find("meta", attrs={"property": prop})
        return tag.get("content", "").strip() if tag else ""

    result["title"] = meta("title", "og:title")
    result["description"] = meta("description", "og:description")
    result["company"] = meta("company") or meta(prop="og:site_name")
    return {k: v for k, v in result.items() if v}


def _parse_heuristic(soup):
    """Heuristic text extraction from page body."""
    result = {}
    text = soup.get_text(separator="\n")

    # Salary patterns
    for pat in [
        r"\$\s*([\d,]+)\s*[-–—]\s*\$\s*([\d,]+)",
        r"([\d,]+)\s*[-–—]\s*([\d,]+)\s*(?:per\s+(?:year|annum)|/yr|/year)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["salary_range"] = f"${m.group(1)} - ${m.group(2)}"
            break

    # Requirements section
    for pat in [
        r"(?:Requirements?|Qualifications?|What you.ll need)\s*[:\n](.*?)(?:\n\s*\n|\Z)",
    ]:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            result["requirements"] = m.group(1).strip()[:2000]
            break

    return {k: v for k, v in result.items() if v}


def _parse_llm_fallback(text):
    """Use LLM to extract job posting fields from raw text. Best-effort."""
    result = {}
    if not text or len(text.strip()) < 50:
        return result
    try:
        from smart_llm import call_llm

        prompt = (
            "Extract the following from this job posting text. "
            "Return JSON with keys: title, company, location, description, "
            "requirements, salary_range. "
            "If a field is not found, use empty string.\n\n"
            f"TEXT:\n{text[:3000]}"
        )
        raw = call_llm(prompt, max_tokens=512)
        if raw:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                data = json.loads(m.group())
                for key in (
                    "title",
                    "company",
                    "location",
                    "description",
                    "requirements",
                    "salary_range",
                ):
                    if data.get(key):
                        result[key] = str(data[key])[:2000]
    except Exception as exc:
        logger.debug("LLM fallback failed: %s", exc)
    return result
