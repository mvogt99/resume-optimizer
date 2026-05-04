"""
Deep Professional Profile Engine.
Aggregates all data sources (LinkedIn, projects, journey, experiences, resumes,
skills interviews) and synthesizes a unified professional profile via LLM.
"""

import contextlib
import json
import os
import uuid
from datetime import datetime, timezone

from models import get_db

# WIP project directories to scan for deep profile
_APPLICATIONS_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # resume-optimizer/
    "..",  # applications/
)


def _init_deep_profile_tables():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deep_profiles (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                profile_json TEXT DEFAULT '{}',
                raw_data_json TEXT DEFAULT '{}',
                source_summary TEXT DEFAULT '',
                source_hash TEXT DEFAULT '',
                is_stale INTEGER DEFAULT 0,
                stale_reason TEXT DEFAULT '',
                last_checked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS role_syntheses (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                profile_id TEXT NOT NULL,
                job_text_hash TEXT NOT NULL,
                job_title TEXT DEFAULT '',
                synthesis_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()


class DeepProfileEngine:
    """Aggregates all data sources into a unified professional profile."""

    def __init__(self):
        _init_deep_profile_tables()

    def build_profile(self, user_id):
        """Aggregate all data sources into a unified professional profile."""
        from deep_profile_sources import (
            get_experience_data,
            get_journey_data,
            get_linkedin_data,
            get_project_data,
            get_resume_data,
            get_skills_interview_data,
            get_wip_projects,
        )
        from deep_profile_synthesis import (
            build_fallback_profile,
            build_source_summary,
            synthesize_profile,
        )

        self._current_user_id = user_id
        raw = {
            "linkedin": get_linkedin_data(user_id),
            "projects": get_project_data(user_id),
            "journey": get_journey_data(),
            "experiences": get_experience_data(user_id),
            "resumes": get_resume_data(user_id),
            "skills_interviews": get_skills_interview_data(),
            "wip_projects": get_wip_projects(_APPLICATIONS_ROOT),
        }

        source_summary = build_source_summary(raw)
        profile_json = synthesize_profile(raw)

        if not profile_json:
            profile_json = build_fallback_profile(raw)

        self._save_profile(user_id, raw, profile_json, source_summary)
        return profile_json

    def get_profile(self, user_id):
        """Retrieve the latest deep profile for a user."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM deep_profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["profile_json"])
        except (json.JSONDecodeError, TypeError):
            return None

    def get_profile_with_meta(self, user_id):
        """Retrieve deep profile with metadata (id, timestamps, source summary)."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM deep_profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        try:
            profile = json.loads(row["profile_json"])
        except (json.JSONDecodeError, TypeError):
            profile = {}
        return {
            "id": row["id"],
            "profile": profile,
            "source_summary": row["source_summary"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_role_synthesis(self, user_id, job_text):
        """Generate or retrieve a role-specific synthesis from the deep profile."""
        import hashlib

        from deep_profile_synthesis import synthesize_for_role

        profile = self.get_profile(user_id)
        if not profile:
            return None

        job_hash = hashlib.sha256(job_text.encode()).hexdigest()

        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM role_syntheses WHERE user_id = ? AND job_text_hash = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id, job_hash),
            ).fetchone()

        if row:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                return json.loads(row["synthesis_json"])

        synthesis = synthesize_for_role(profile, job_text)
        if synthesis:
            self._save_role_synthesis(user_id, job_hash, synthesis)
        return synthesis

    def update_profile_from_interview(self, user_id, updates):
        """Merge interview-discovered insights into the existing profile."""
        profile = self.get_profile(user_id)
        if not profile:
            return None

        for update in updates:
            field = update.get("field", "")
            value = update.get("value")
            if not field or value is None:
                continue

            # Handle nested fields like "leadership_profile.team_scope"
            parts = field.split(".")
            target = profile
            for part in parts[:-1]:
                if isinstance(target, dict) and part in target:
                    target = target[part]
                else:
                    break
            else:
                if isinstance(target, dict):
                    key = parts[-1]
                    if isinstance(target.get(key), list) and not isinstance(value, list):
                        target[key].append(value)
                    else:
                        target[key] = value

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM deep_profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if existing and existing["id"] is not None:
                conn.execute(
                    "UPDATE deep_profiles SET profile_json = ?, updated_at = ? WHERE id = ?",
                    (
                        json.dumps(profile, default=str),
                        datetime.now(timezone.utc).isoformat(),
                        existing["id"],
                    ),
                )
                conn.commit()
            elif existing:
                conn.execute(
                    "UPDATE deep_profiles SET profile_json = ?, updated_at = ? WHERE user_id = ? AND id IS NULL",
                    (
                        json.dumps(profile, default=str),
                        datetime.now(timezone.utc).isoformat(),
                        user_id,
                    ),
                )
                conn.commit()
        return profile

    # --- Persistence ---

    def _save_profile(self, user_id, raw, profile_json, source_summary):
        """Save or update the deep profile."""
        from deep_profile_staleness import compute_source_hash

        source_hash = compute_source_hash(user_id)

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM deep_profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()

            now = datetime.now(timezone.utc).isoformat()
            profile_str = json.dumps(profile_json, default=str)
            raw_str = json.dumps(raw, default=str)

            if existing and existing["id"] is not None:
                conn.execute(
                    "UPDATE deep_profiles SET profile_json = ?, raw_data_json = ?, "
                    "source_summary = ?, source_hash = ?, is_stale = 0, stale_reason = '', "
                    "last_checked_at = ?, updated_at = ? WHERE id = ?",
                    (profile_str, raw_str, source_summary, source_hash, now, now, existing["id"]),
                )
            elif existing:
                # Legacy row with NULL id — update by user_id
                conn.execute(
                    "UPDATE deep_profiles SET profile_json = ?, raw_data_json = ?, "
                    "source_summary = ?, source_hash = ?, is_stale = 0, stale_reason = '', "
                    "last_checked_at = ?, updated_at = ? WHERE user_id = ? AND id IS NULL",
                    (profile_str, raw_str, source_summary, source_hash, now, now, user_id),
                )
            else:
                profile_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO deep_profiles (id, user_id, profile_json, raw_data_json, "
                    "source_summary, source_hash, is_stale, last_checked_at, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
                    (
                        profile_id,
                        user_id,
                        profile_str,
                        raw_str,
                        source_summary,
                        source_hash,
                        now,
                        now,
                        now,
                    ),
                )
            conn.commit()

    def _save_role_synthesis(self, user_id, job_hash, synthesis):
        """Save a role-specific synthesis."""
        with get_db() as conn:
            profile_row = conn.execute(
                "SELECT id FROM deep_profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            profile_id = profile_row["id"] if profile_row else ""

            syn_id = str(uuid.uuid4())
            job_title = synthesis.get("job_title", "")
            conn.execute(
                "INSERT INTO role_syntheses (id, user_id, profile_id, job_text_hash, "
                "job_title, synthesis_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    syn_id,
                    user_id,
                    profile_id,
                    job_hash,
                    job_title,
                    json.dumps(synthesis, default=str),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()


# Singleton
_engine = None


def get_deep_profile_engine():
    global _engine
    if _engine is None:
        _engine = DeepProfileEngine()
    return _engine
