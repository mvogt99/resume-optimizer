"""Job Scout Agent — scrapes job boards via python-jobspy, scores postings with NLP + RTX 5090."""

import contextlib
import json
import uuid

from agents.base_agent import BaseCareerAgent
from agents.job_scout_search import _JobScoutSearchMixin
from batch_jobs import get_batch_manager
from models import get_db


# INTEGER columns that callers commonly send as JSON booleans.
_INTEGER_FLAG_COLUMNS = {"is_starred", "is_test"}


class JobScoutAgent(_JobScoutSearchMixin, BaseCareerAgent):
    agent_type = "job_scout"

    # --- Search ---

    def search_jobs(self, user_id, criteria_id=None):
        """Start a background job search. Returns batch job_id."""
        criteria = None
        if criteria_id:
            criteria = self._get_criteria_by_id(criteria_id)
        if not criteria:
            # Use first active criteria or defaults
            all_criteria = self.get_criteria(user_id)
            criteria = (
                all_criteria[0]
                if all_criteria
                else {
                    "target_roles": ["Software Engineer"],
                    "locations": ["Remote"],
                    "remote_preference": "any",
                }
            )

        mgr = get_batch_manager()
        job_id = mgr.create_job("job_scout_search", user_id, {"criteria": criteria})

        def worker(jid):
            return self._search_worker(jid, user_id, criteria)

        mgr.start_job(job_id, worker)
        return job_id

    # --- Postings CRUD ---

    def get_postings(self, user_id, status=None, min_score=0, limit=50):
        """List postings with optional filters."""
        with get_db() as conn:
            query = "SELECT * FROM job_postings WHERE user_id = ? AND match_score >= ?"
            params = [user_id, min_score]
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY match_score DESC, discovered_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
        return [self._posting_to_dict(r) for r in rows]

    def get_posting(self, posting_id, user_id=None):
        """Get a single posting by ID, optionally filtered by user_id."""
        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM job_postings WHERE id = ? AND user_id = ?",
                    (posting_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM job_postings WHERE id = ?", (posting_id,)
                ).fetchone()
        return self._posting_to_dict(row) if row else None

    def update_posting(self, posting_id, updates, user_id=None):
        """Update posting fields (status, notes, is_starred)."""
        # SAFE: only keys in `allowed` become column names in the SET clause.
        # User-supplied values always go through ? parameterized placeholders.
        allowed = {"status", "notes", "is_starred", "is_test"}
        sets = []
        vals = []
        for k, v in updates.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                # JSON booleans reach INTEGER columns: a client posting
                # {"is_starred": true} yields a Python bool. sqlite3 coerced it
                # silently; PostgreSQL rejects it outright. Coerce only these
                # flag columns -- a blanket int(v) would corrupt a future TEXT or
                # BOOLEAN column, and None must pass through to clear the field.
                if k in _INTEGER_FLAG_COLUMNS and isinstance(v, bool):
                    vals.append(int(v))
                else:
                    vals.append(v)
        if not sets:
            return None
        sets.append("updated_at = CURRENT_TIMESTAMP")
        with get_db() as conn:
            if user_id is not None:
                vals.append(posting_id)
                vals.append(user_id)
                conn.execute(
                    f"UPDATE job_postings SET {', '.join(sets)} WHERE id = ? AND user_id = ?",
                    vals,
                )
            else:
                vals.append(posting_id)
                conn.execute(f"UPDATE job_postings SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
        return self.get_posting(posting_id, user_id=user_id)

    def delete_posting(self, posting_id, user_id=None):
        """Delete a posting."""
        with get_db() as conn:
            if user_id is not None:
                conn.execute(
                    "DELETE FROM job_postings WHERE id = ? AND user_id = ?",
                    (posting_id, user_id),
                )
            else:
                conn.execute("DELETE FROM job_postings WHERE id = ?", (posting_id,))
            conn.commit()

    def add_posting(self, user_id, data):
        """Manually add a posting (no scraping)."""
        posting_id = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT INTO job_postings "
                "(id, user_id, title, company, location, url, description, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    posting_id,
                    user_id,
                    data.get("title", ""),
                    data.get("company", ""),
                    data.get("location", ""),
                    data.get("url", ""),
                    data.get("description", ""),
                    data.get("status", "discovered"),
                ),
            )
            conn.commit()
        return self.get_posting(posting_id, user_id=user_id)

    def import_scraped_posting(self, user_id, scraped):
        """Import a scraped posting dict (from job_scraper) into the DB."""
        posting = {
            "title": scraped.get("title", ""),
            "company": scraped.get("company", ""),
            "location": scraped.get("location", ""),
            "url": scraped.get("url", ""),
            "source": scraped.get("source", "scraped"),
            "description": scraped.get("description", ""),
            "salary_min": 0,
            "salary_max": 0,
            "is_remote": 0,
            "match_score": 0,
            "llm_score_json": "{}",
            "skills_overlap": "[]",
            "skills_missing": "[]",
            "posted_date": "",
        }
        return self._insert_posting(user_id, posting)

    def rescore_posting(self, posting_id, user_id):
        """Re-score a posting with LLM (on-demand). RTX 5090."""
        posting = self.get_posting(posting_id, user_id=user_id)
        if not posting:
            return None

        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        # Enrich with deep profile role-fit data if available
        deep_fit_text = ""
        try:
            from deep_profile import get_deep_profile_engine

            dp = get_deep_profile_engine()
            jd_text = posting.get("description", "")
            if jd_text:
                fit = dp.synthesize_role_fit(int(user_id), jd_text)
                if fit and isinstance(fit, dict):
                    score = fit.get("fit_score", "")
                    gaps = fit.get("gaps", [])
                    strengths = fit.get("strengths", [])
                    parts = []
                    if score:
                        parts.append(f"Deep profile fit score: {score}%")
                    if strengths:
                        parts.append("Key strengths: " + ", ".join(str(s) for s in strengths[:5]))
                    if gaps:
                        parts.append("Gaps: " + ", ".join(str(g) for g in gaps[:5]))
                    if parts:
                        deep_fit_text = "\n" + "\n".join(parts)
        except Exception:
            pass

        enriched_profile = profile_text + deep_fit_text

        llm_scores, duration = self._timed(
            self._llm_enrich_score,
            posting.get("description", "")[:3000],
            enriched_profile,
        )

        if llm_scores:
            # Recalculate blended score
            nlp_score = posting.get("match_score", 0)
            blended = 0.4 * nlp_score + 0.6 * llm_scores.get("overall_recommendation", 0)

            with get_db() as conn:
                conn.execute(
                    "UPDATE job_postings SET match_score = ?, llm_score_json = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (round(blended, 1), json.dumps(llm_scores), posting_id),
                )
                conn.commit()

            self._log_run(
                user_id,
                f"Re-score posting: {posting.get('title', '')}",
                {"posting_id": posting_id},
                llm_scores,
                task_type="analysis",
                duration_ms=duration,
            )

            # CT-1: Record claim for accountability audit
            self._record_claim(
                user_id,
                "job_scout",
                posting.get("description", "")[:500],
                str(llm_scores)[:500],
                metadata={"posting_id": posting_id, "score": round(blended, 1)},
            )

        return self.get_posting(posting_id)

    # --- Search criteria ---

    def save_criteria(self, user_id, criteria):
        """Save search criteria. Returns the saved record."""
        with get_db() as conn:
            conn.execute(
                "INSERT INTO search_criteria "
                "(user_id, search_name, target_roles, locations, remote_preference, "
                "salary_min, industries, excluded_companies, keywords) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    criteria.get("search_name", "Default"),
                    json.dumps(criteria.get("target_roles", [])),
                    json.dumps(criteria.get("locations", [])),
                    criteria.get("remote_preference", "any"),
                    criteria.get("salary_min", 0),
                    json.dumps(criteria.get("industries", [])),
                    json.dumps(criteria.get("excluded_companies", [])),
                    json.dumps(criteria.get("keywords", [])),
                ),
            )
            criteria_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
        return {"id": criteria_id, **criteria}

    def get_criteria(self, user_id):
        """List saved search criteria for user."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM search_criteria WHERE user_id = ? AND is_active = 1 "
                "ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [self._criteria_to_dict(r) for r in rows]

    def _get_criteria_by_id(self, criteria_id):
        """Get a single criteria record."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM search_criteria WHERE id = ?", (criteria_id,)
            ).fetchone()
        return self._criteria_to_dict(row) if row else None

    # --- Helpers ---

    @staticmethod
    def _posting_to_dict(row):
        if not row:
            return None
        d = dict(row)
        for key in ("llm_score_json", "skills_overlap", "skills_missing"):
            if key in d and isinstance(d[key], str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    d[key] = json.loads(d[key])
        return d

    @staticmethod
    def _criteria_to_dict(row):
        if not row:
            return None
        d = dict(row)
        for key in ("target_roles", "locations", "industries", "excluded_companies", "keywords"):
            if key in d and isinstance(d[key], str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    d[key] = json.loads(d[key])
        return d
