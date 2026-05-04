"""Job Scout Search — background search worker, scraping, and scoring."""

import json
import logging
import uuid

from batch_jobs import get_batch_manager
from models import get_db

logger = logging.getLogger(__name__)


class _JobScoutSearchMixin:

    def _search_worker(self, job_id, user_id, criteria):
        """Background worker: scrape → score → insert postings."""
        mgr = get_batch_manager()

        # 1. Load user profile for scoring context
        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        # 2. Scrape jobs
        mgr.update_progress(job_id, {"stage": "scraping", "percent": 10})
        raw_postings = self._scrape_jobs(criteria)

        if mgr.is_cancelled(job_id):
            return {"cancelled": True}

        total = len(raw_postings)
        mgr.update_progress(job_id, {"stage": "scoring", "percent": 30, "total": total})

        # 3. Score and insert each posting
        for i, posting in enumerate(raw_postings):
            if mgr.is_cancelled(job_id):
                return {"cancelled": True, "inserted": i}

            scored = self._score_posting(posting, profile, profile_text)
            self._insert_posting(user_id, scored)

            if (i + 1) % 5 == 0 or i == total - 1:
                pct = 30 + int(60 * (i + 1) / max(total, 1))
                mgr.update_progress(
                    job_id,
                    {
                        "stage": "scoring",
                        "percent": pct,
                        "scored": i + 1,
                        "total": total,
                    },
                )

        self._log_run(
            user_id,
            f"Job search: {criteria.get('target_roles', [])}",
            {"criteria": criteria},
            {"postings_found": total, "inserted": total},
            task_type="analysis",
        )

        return {"postings_found": total, "inserted": total}

    def _scrape_jobs(self, criteria):
        """Scrape job boards via python-jobspy. Returns list of posting dicts."""
        try:
            from jobspy import scrape_jobs
        except ImportError:
            print("[job_scout] python-jobspy not installed — returning empty results")
            return []

        roles = criteria.get("target_roles", ["Software Engineer"])
        locations = criteria.get("locations", ["Remote"])
        search_term = ", ".join(roles[:3])
        location = locations[0] if locations else "Remote"

        # Build site list
        site_names = ["indeed", "linkedin", "glassdoor"]

        try:
            results = scrape_jobs(
                site_name=site_names,
                search_term=search_term,
                location=location,
                results_wanted=30,
                hours_old=72,
                is_remote=criteria.get("remote_preference") == "remote_only",
                country_indeed="USA",
            )
        except Exception as e:
            print(f"[job_scout] Scrape failed: {e}")
            return []

        postings = []
        if results is not None and hasattr(results, "iterrows"):
            for _, row in results.iterrows():
                posting = {
                    "title": str(row.get("title", "")),
                    "company": str(row.get("company_name", row.get("company", ""))),
                    "location": str(row.get("location", "")),
                    "url": str(row.get("job_url", row.get("link", ""))),
                    "source": str(row.get("site", "")),
                    "description": str(row.get("description", ""))[:10000],
                    "salary_min": float(row.get("min_amount", 0) or 0),
                    "salary_max": float(row.get("max_amount", 0) or 0),
                    "is_remote": 1 if "remote" in str(row.get("location", "")).lower() else 0,
                    "posted_date": str(row.get("date_posted", "")),
                }
                # Skip excluded companies
                excluded = [c.lower() for c in criteria.get("excluded_companies", [])]
                if posting["company"].lower() not in excluded:
                    postings.append(posting)

        return postings

    def _score_posting(self, posting, profile, profile_text):
        """Score a posting: NLP keyword overlap + LLM enrichment."""
        # Stage 1: NLP-based keyword overlap (fast, no GPU)
        match_score = 0.0
        skills_overlap = []
        skills_missing = []

        try:
            from nlp_engine import extract_skill_phrases

            jd_keywords = {
                p.lower()
                for p in extract_skill_phrases(
                    posting.get("description", ""), use_llm_fallback=False
                )
            }
            resume_text = profile.get("resume_text", "")
            if resume_text:
                resume_keywords = {
                    p.lower() for p in extract_skill_phrases(resume_text, use_llm_fallback=False)
                }
                # Enrich with deep profile skills — these are validated across
                # multiple sources and should count as "demonstrated" skills
                for skill in profile.get("higher_order_skills", []):
                    resume_keywords.add(skill.lower())
                for tech in profile.get("top_technologies", []):
                    resume_keywords.add(tech.lower())
                for diff in profile.get("differentiators", []):
                    resume_keywords.add(diff.lower())

                overlap = jd_keywords & resume_keywords
                missing = jd_keywords - resume_keywords
                skills_overlap = sorted(overlap)[:30]
                skills_missing = sorted(missing)[:30]
                if jd_keywords:
                    match_score = len(overlap) / len(jd_keywords) * 100
        except Exception as e:
            print(f"[job_scout] NLP scoring failed: {e}")

        # Stage 2: LLM enrichment (RTX 5090)
        llm_scores = self._llm_enrich_score(
            posting.get("description", "")[:3000],
            profile_text,
        )

        # Blend: 40% NLP + 60% LLM overall
        llm_overall = llm_scores.get("overall_recommendation", match_score) if llm_scores else 0
        if llm_scores:
            blended = 0.4 * match_score + 0.6 * llm_overall
        else:
            blended = match_score

        posting["match_score"] = round(blended, 1)
        posting["llm_score_json"] = json.dumps(llm_scores or {})
        posting["skills_overlap"] = json.dumps(skills_overlap)
        posting["skills_missing"] = json.dumps(skills_missing)

        return posting

    def _llm_enrich_score(self, posting_text, profile_summary):
        """RTX 5090: analyze posting vs candidate. Returns scoring dict."""
        if not posting_text or not profile_summary:
            return None

        prompt = f"""Analyze this job posting against the candidate profile.
Score each dimension 0-100, return ONLY a JSON object:
{{
  "culture_fit": <int>,
  "seniority_match": <int>,
  "growth_potential": <int>,
  "skills_alignment": <int>,
  "overall_recommendation": <int>,
  "reasoning": "<2-3 sentence analysis>"
}}

Job posting:
{posting_text}

Candidate profile:
{profile_summary}"""

        result = self._call_llm_json(prompt, task_type="analysis", max_tokens=1024)
        if isinstance(result, dict) and "overall_recommendation" in result:
            return result
        return None

    def _insert_posting(self, user_id, posting):
        """Insert a scored posting into the DB. Skips duplicates by URL."""
        posting_id = str(uuid.uuid4())
        with get_db() as conn:
            # Check for duplicate URL
            if posting.get("url"):
                existing = conn.execute(
                    "SELECT id FROM job_postings WHERE user_id = ? AND url = ?",
                    (user_id, posting["url"]),
                ).fetchone()
                if existing:
                    return existing[0]

            conn.execute(
                "INSERT INTO job_postings "
                "(id, user_id, title, company, location, url, source, description, "
                "salary_min, salary_max, is_remote, match_score, llm_score_json, "
                "skills_overlap, skills_missing, posted_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    posting_id,
                    user_id,
                    posting.get("title", ""),
                    posting.get("company", ""),
                    posting.get("location", ""),
                    posting.get("url", ""),
                    posting.get("source", ""),
                    posting.get("description", ""),
                    posting.get("salary_min", 0),
                    posting.get("salary_max", 0),
                    posting.get("is_remote", 0),
                    posting.get("match_score", 0),
                    posting.get("llm_score_json", "{}"),
                    posting.get("skills_overlap", "[]"),
                    posting.get("skills_missing", "[]"),
                    posting.get("posted_date", ""),
                ),
            )
            conn.commit()
        return posting_id
