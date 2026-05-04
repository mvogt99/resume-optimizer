"""Application Tracker Agent — Kanban pipeline, analytics, follow-up generation via RTX 5090."""

import contextlib
import json

from agents.base_agent import BaseCareerAgent
from models import get_db

PIPELINE_STAGES = [
    "discovered",
    "bookmarked",
    "tailored",
    "applied",
    "phone_screen",
    "interview",
    "offered",
    "accepted",
    "rejected",
    "withdrawn",
]


class ApplicationTrackerAgent(BaseCareerAgent):
    agent_type = "app_tracker"

    def get_pipeline(self, user_id):
        """Group job_postings by status → Kanban columns."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM job_postings WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()

        columns = {stage: [] for stage in PIPELINE_STAGES}
        for row in rows:
            d = self._posting_to_dict(row)
            status = d.get("status", "discovered")
            if status in columns:
                columns[status].append(d)
            else:
                columns["discovered"].append(d)

        return {
            "stages": PIPELINE_STAGES,
            "columns": columns,
            "total": len(rows),
        }

    def move_posting(self, posting_id, new_status, notes="", user_id=None):
        """Move a posting to a new pipeline stage."""
        if new_status not in PIPELINE_STAGES:
            return {"error": f"Invalid stage: {new_status}"}

        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT id FROM job_postings WHERE id = ? AND user_id = ?",
                    (posting_id, user_id),
                ).fetchone()
                if not row:
                    return {"error": "Posting not found"}

            # SAFE: `sets` contains only hardcoded column-assignment strings,
            # never user input. Values are passed via ? parameterized placeholders.
            sets = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            vals = [new_status]
            if notes:
                sets.append("notes = ?")
                vals.append(notes)
            vals.append(posting_id)
            conn.execute(f"UPDATE job_postings SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()

        return self._get_posting(posting_id, user_id=user_id)

    def get_analytics(self, user_id):
        """SQL aggregation: volume by status, response rate, avg days per stage."""
        with get_db() as conn:
            # Count by status
            status_counts = {}
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM job_postings "
                "WHERE user_id = ? GROUP BY status",
                (user_id,),
            ).fetchall()
            for r in rows:
                status_counts[r["status"]] = r["cnt"]

            total = sum(status_counts.values())

            # Response rate: (phone_screen + interview + offered + accepted) / applied
            applied = sum(
                status_counts.get(s, 0)
                for s in [
                    "applied",
                    "phone_screen",
                    "interview",
                    "offered",
                    "accepted",
                    "rejected",
                ]
            )
            responded = sum(
                status_counts.get(s, 0)
                for s in ["phone_screen", "interview", "offered", "accepted"]
            )
            response_rate = round(responded / max(applied, 1) * 100, 1)

            # Avg days from discovered to applied
            avg_days = conn.execute(
                "SELECT AVG(julianday(updated_at) - julianday(discovered_at)) as avg_d "
                "FROM job_postings WHERE user_id = ? AND status IN "
                "('applied', 'phone_screen', 'interview', 'offered', 'accepted')",
                (user_id,),
            ).fetchone()
            avg_days_to_apply = round(avg_days["avg_d"] or 0, 1) if avg_days else 0

            # Top companies
            top_companies = conn.execute(
                "SELECT company, COUNT(*) as cnt FROM job_postings "
                "WHERE user_id = ? AND company != '' "
                "GROUP BY company ORDER BY cnt DESC LIMIT 10",
                (user_id,),
            ).fetchall()

            # Top sources
            top_sources = conn.execute(
                "SELECT source, COUNT(*) as cnt FROM job_postings "
                "WHERE user_id = ? AND source != '' "
                "GROUP BY source ORDER BY cnt DESC LIMIT 5",
                (user_id,),
            ).fetchall()

        return {
            "total": total,
            "by_status": status_counts,
            "response_rate": response_rate,
            "avg_days_to_apply": avg_days_to_apply,
            "top_companies": [{"company": r["company"], "count": r["cnt"]} for r in top_companies],
            "top_sources": [{"source": r["source"], "count": r["cnt"]} for r in top_sources],
        }

    def get_reminders(self, user_id):
        """Find stale applications needing follow-up (applied > 7 days ago, no progress)."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM job_postings WHERE user_id = ? "
                "AND status = 'applied' "
                "AND updated_at < datetime('now', '-7 days') "
                "ORDER BY updated_at ASC LIMIT 20",
                (user_id,),
            ).fetchall()
        return [self._posting_to_dict(r) for r in rows]

    def generate_followup(self, posting_id, user_id):
        """RTX 5090: generate a follow-up email draft for a posting."""
        posting = self._get_posting(posting_id)
        if not posting:
            return {"error": "Posting not found"}

        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        prompt = f"""Write a professional follow-up email for a job application.
Keep it concise (under 200 words), warm but professional.
Reference specific aspects of the role that interest the candidate.

Return ONLY a JSON object:
{{
  "subject": "<email subject line>",
  "body": "<email body text>",
  "tone": "<professional|friendly|enthusiastic>"
}}

Job title: {posting.get('title', '')}
Company: {posting.get('company', '')}
Job description excerpt: {posting.get('description', '')[:1500]}

Candidate profile:
{profile_text}"""

        result, duration = self._timed(
            self._call_llm_json,
            prompt,
            task_type="narrative_generation",
            max_tokens=1024,
        )

        # Replace common LLM placeholders with actual data
        if result and isinstance(result.get("body"), str):
            user_name = ""
            try:
                import linkedin_cache

                raw = linkedin_cache.get_raw(user_id)
                if raw:
                    user_name = raw.get("full_name") or raw.get("name", "")
            except (ImportError, AttributeError):
                pass

            body = result["body"]
            title = posting.get("title", "")
            company = posting.get("company", "")
            replacements = {
                "[Your Name]": user_name,
                "[Your Full Name]": user_name,
                "[Candidate Name]": user_name,
                "[Candidate's Name]": user_name,
                "[Position]": title,
                "[Job Title]": title,
                "[Role]": title,
                "[Company]": company,
                "[Company Name]": company,
                "[Hiring Manager]": "Hiring Manager",
                "[Hiring Manager's Name]": "Hiring Manager",
                "[Recruiter Name]": "Hiring Team",
                "[Interviewer Name]": "Hiring Manager",
            }
            for placeholder, value in replacements.items():
                if value:
                    body = body.replace(placeholder, value)
            result["body"] = body

            if result.get("subject"):
                subj = result["subject"]
                for placeholder, value in replacements.items():
                    if value:
                        subj = subj.replace(placeholder, value)
                result["subject"] = subj

        self._log_run(
            user_id,
            f"Follow-up email: {posting.get('title', '')}",
            {"posting_id": posting_id},
            result or {},
            task_type="narrative_generation",
            duration_ms=duration,
        )

        return result or {"error": "LLM failed to generate follow-up"}

    def analyze_performance(self, user_id):
        """RTX 5090: analyze patterns in application outcomes."""
        analytics = self.get_analytics(user_id)
        if analytics["total"] < 3:
            return {"analysis": "Not enough data for pattern analysis. Apply to more positions."}

        # Get a sample of accepted/rejected postings for LLM
        with get_db() as conn:
            sample = conn.execute(
                "SELECT title, company, match_score, status, llm_score_json "
                "FROM job_postings WHERE user_id = ? "
                "AND status IN ('accepted', 'rejected', 'offered', 'interview', 'applied') "
                "ORDER BY updated_at DESC LIMIT 20",
                (user_id,),
            ).fetchall()

        sample_text = "\n".join(
            f"- {r['title']} @ {r['company']} | Score: {r['match_score']} | Status: {r['status']}"
            for r in sample
        )

        prompt = f"""Analyze this job application history and identify patterns.

Application analytics:
- Total applications: {analytics['total']}
- Status breakdown: {json.dumps(analytics['by_status'])}
- Response rate: {analytics['response_rate']}%
- Avg days to apply: {analytics['avg_days_to_apply']}

Recent applications:
{sample_text}

Return a JSON object with:
{{
  "patterns": ["<pattern 1>", "<pattern 2>", ...],
  "strengths": ["<what's working>", ...],
  "improvements": ["<actionable suggestion>", ...],
  "recommended_focus": "<one sentence recommendation>"
}}"""

        result, duration = self._timed(
            self._call_llm_json, prompt, task_type="analysis", max_tokens=1024
        )

        self._log_run(
            user_id,
            "Performance analysis",
            {"analytics_summary": analytics},
            result or {},
            task_type="analysis",
            duration_ms=duration,
        )

        return result or {"analysis": "Unable to analyze — LLM unavailable"}

    # --- Helpers ---

    def _get_posting(self, posting_id, user_id=None):
        from models import get_db

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
