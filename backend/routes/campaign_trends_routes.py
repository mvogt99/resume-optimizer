"""Campaign Trending Topics — discover trending AI content and suggest campaigns."""

import json
import logging

import requests
from auth import require_auth
from flask import Blueprint, g, jsonify

campaign_trends_bp = Blueprint("campaign_trends", __name__)
logger = logging.getLogger(__name__)

_HN_URL = (
    "https://hn.algolia.com/api/v1/search_by_date"
    "?query={query}&tags=story&hitsPerPage=15&numericFilters=num_comments>5"
)
_DEVTO_URL = "https://dev.to/api/articles?tag={tag}&top=7&per_page=10"

_AI_QUERIES = [
    "agentic AI autonomous agents",
    "LLM inference optimization local GPU",
    "AI engineering career",
    "RAG knowledge graphs enterprise AI",
    "vLLM inference serving",
]
_DEVTO_TAGS = ["ai", "machinelearning", "llm"]


def _fetch_hn(query: str, timeout: int = 6) -> list[dict]:
    try:
        r = requests.get(_HN_URL.format(query=requests.utils.quote(query)), timeout=timeout)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        return [
            {"title": h.get("title", ""), "url": h.get("url", ""), "points": h.get("points", 0),
             "source": "HackerNews"}
            for h in hits if h.get("title")
        ]
    except Exception as e:
        logger.warning("HN fetch failed: %s", e)
        return []


def _fetch_devto(tag: str, timeout: int = 6) -> list[dict]:
    try:
        r = requests.get(_DEVTO_URL.format(tag=tag), timeout=timeout)
        r.raise_for_status()
        articles = r.json()
        return [
            {"title": a.get("title", ""), "url": a.get("url", ""),
             "points": a.get("positive_reactions_count", 0), "source": "dev.to"}
            for a in articles if a.get("title")
        ]
    except Exception as e:
        logger.warning("dev.to fetch failed tag=%s: %s", tag, e)
        return []


def _get_user_corpus_summary(user_id: int) -> str:
    """Fetch top skills + technologies from user's journey corpus."""
    try:
        from journey_miner import get_journey_miner
        miner = get_journey_miner()
        skills = miner.get_skills(user_id=user_id)
        top_skills = [s.get("skill", "") for s in (skills or [])[:20] if s.get("skill")]
        if top_skills:
            return "User's AI journey skills: " + ", ".join(top_skills)
    except Exception as e:
        logger.warning("Corpus summary failed: %s", e)
    return "User is an AI/ML engineer with experience in agentic AI, LLMs, and enterprise architecture."


def _synthesize_suggestions(articles: list[dict], corpus_summary: str) -> list[dict]:
    """Use LLM to generate 5 campaign angle suggestions from trending content."""
    from llm_helper import call_llm

    article_lines = "\n".join(
        f"- [{a['source']}] {a['title']}" for a in articles[:25]
    )
    prompt = f"""You are a LinkedIn content strategist. Given trending AI articles and a professional's
background, suggest 5 distinct LinkedIn campaign themes they could create compelling content about.

{corpus_summary}

Trending AI content right now:
{article_lines}

Return ONLY a JSON array of 5 objects. Each object must have:
- "title": short campaign title (5-8 words)
- "theme": one-line theme description
- "angle": 2-sentence description of the unique angle and audience
- "why_relevant": one sentence on why this fits the user's background
- "example_post_hooks": array of 3 engaging opening lines for posts
- "suggested_hashtags": array of 5 relevant hashtags

Return only valid JSON, no markdown, no prose."""

    raw = call_llm(prompt, task_type="reasoning", max_tokens=2048)
    if not raw:
        return []

    # Strip think tags if present
    import re
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    # Extract JSON array
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except Exception:
        return []


@campaign_trends_bp.route("/api/campaigns/discover-trends", methods=["POST"])
@require_auth
def discover_trends():
    """Fetch trending AI content and return campaign suggestions tailored to the user's corpus."""
    # Gather trending articles (parallel-ish via sequential calls — fast enough)
    articles = []
    for q in _AI_QUERIES[:3]:
        articles.extend(_fetch_hn(q))
    for tag in _DEVTO_TAGS[:2]:
        articles.extend(_fetch_devto(tag))

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        key = a["title"].lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    # Sort by engagement
    unique.sort(key=lambda x: x.get("points", 0), reverse=True)

    corpus = _get_user_corpus_summary(g.user_id)
    suggestions = _synthesize_suggestions(unique, corpus)

    return jsonify({
        "suggestions": suggestions,
        "trending_articles": unique[:20],
        "corpus_summary": corpus,
    }), 200
