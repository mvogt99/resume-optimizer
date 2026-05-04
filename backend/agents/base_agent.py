"""Base class for all career assistant agents. All LLM calls route through RTX 5090."""

import asyncio
import datetime
import json
import logging
import threading
import time
import uuid

from llm_helper import call_llm_scored, extract_json
from models import get_db
from personaforge_client import CAREER_NAMESPACE, pf_recall, pf_remember

logger = logging.getLogger(__name__)

_FTAL_PASS_THRESHOLD = 30


class BaseCareerAgent:
    agent_type = "base"
    _last_ftal_scores = None  # set by _call_llm(), consumed by _log_run()
    _pending_retry_teaching: str = ""  # W1: set by route handler before retry; consumed once

    def __init__(self):
        self._claims: dict = {}

    def record_claim(self, claim_text: str, claim_type: str = "achievement") -> str:
        """Record a resume claim and return its ID."""
        claim_id = str(uuid.uuid4())
        self._claims[claim_id] = {
            "claim_id": claim_id,
            "claim_text": claim_text,
            "claim_type": claim_type,
            "recorded_at": datetime.datetime.utcnow().isoformat(),
        }
        return claim_id

    def get_claims(self) -> list:
        """Return a list of all recorded claims."""
        return list(self._claims.values())

    def clear_claims(self) -> None:
        """Clear all recorded claims."""
        self._claims.clear()

    def _call_llm(self, prompt, task_type="reasoning", max_tokens=4096):
        """Call FTAL harness → RTX 5090 with persona context. Returns raw string or None.

        P1-B.3: Prepends persona context from PersonaForge (fire-and-forget on failure).
        P1-B.4: Stores successful output patterns (gap<30) in PersonaForge.
        W1: Prepends retry teaching context when route handler set _pending_retry_teaching.
        """
        # W1: Prepend teaching from a prior failed acceptance attempt (consumed once)
        if self._pending_retry_teaching:
            prompt = (
                f"<retry_context>\n{self._pending_retry_teaching}\n</retry_context>\n\n{prompt}"
            )
            self._pending_retry_teaching = ""

        # CT-4: Prepend structured ro_* knowledge graph context (graceful degradation)
        try:
            arango_ctx = self._get_arango_context(
                user_id=getattr(self, "_current_user_id", ""),
                agent_type=self.agent_type,
            )
            if arango_ctx:
                prompt = f"<knowledge_context>\n{arango_ctx}\n</knowledge_context>\n\n{prompt}"
        except Exception as e:
            logger.debug(f"ArangoDB context fetch failed: {e}")

        # P1-B.3: Recall persona context and prepend to prompt
        persona_ctx = pf_recall(CAREER_NAMESPACE, prompt[:200])
        if persona_ctx:
            prompt = f"<persona_context>\n{persona_ctx}\n</persona_context>\n\n{prompt}"

        text, scores = call_llm_scored(prompt, task_type=task_type, max_tokens=max_tokens)
        self._last_ftal_scores = scores

        if text and scores:
            gap = scores.get("gap")
            # P1-B.4: Store successful output patterns in PersonaForge (fire-and-forget)
            if gap is not None and gap < _FTAL_PASS_THRESHOLD:
                try:
                    pf_remember(
                        CAREER_NAMESPACE,
                        f"[{self.agent_type}] Successful output (gap={gap}): {text[:300]}",
                        {
                            "category": "pattern",
                            "agent_type": self.agent_type,
                            "task_type": task_type,
                            "gap": gap,
                            "confidence": round(max(0.5, 1.0 - gap / 100), 2),
                            "style_tags": ["pattern", self.agent_type, "ftal_pass"],
                        },
                    )
                except Exception as e:
                    logger.debug(f"pf_remember (success pattern) failed: {e}")
            # CT-6: Store failure teaching in PersonaForge so next prompt gets corrective context
            elif gap is not None and gap >= _FTAL_PASS_THRESHOLD:
                try:
                    pf_remember(
                        CAREER_NAMESPACE,
                        f"[{self.agent_type}] FAILED output (gap={gap}): review task_type={task_type}. "
                        f"Common issues: insufficient specificity, missing quantification, "
                        f"generic language. Prompt excerpt: {prompt[:150]}",
                        {
                            "category": "failure_teaching",
                            "agent_type": self.agent_type,
                            "task_type": task_type,
                            "gap": gap,
                            "style_tags": ["failure", self.agent_type, "teaching"],
                        },
                    )
                except Exception as e:
                    logger.debug(f"pf_remember (failure_teaching) failed: {e}")

        return text

    def _call_llm_json(self, prompt, task_type="reasoning", max_tokens=4096, retries=2):
        """Call LLM and parse JSON from response. Returns dict/list or None.

        Retries with exponential backoff on transient failure (GPU busy under load).
        """
        for attempt in range(1 + retries):
            raw = self._call_llm(prompt, task_type=task_type, max_tokens=max_tokens)
            if not raw:
                if attempt < retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
                return None
            parsed = extract_json(raw)
            if parsed is not None:
                return parsed
            # JSON parse failed — retry with exponential backoff
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
        return None

    def _log_run(
        self,
        user_id,
        task_desc,
        input_data,
        output_data,
        model_used="",
        task_type="",
        duration_ms=0,
        status="completed",
        error_message="",
        ftal_scores=None,
        acceptance_result=None,
    ):
        """Insert a record into agent_runs for audit trail. Includes FTAL scores if available."""
        run_id = str(uuid.uuid4())
        scores = ftal_scores or self._last_ftal_scores or {}

        acceptance_passed = None
        acceptance_details = None
        acceptance_attempts = None
        if acceptance_result is not None:
            acceptance_passed = 1 if acceptance_result.passed else 0
            acceptance_details = acceptance_result.to_json()

        with get_db() as conn:
            conn.execute(
                "INSERT INTO agent_runs "
                "(id, user_id, agent_type, task_description, input_json, output_json, "
                "model_used, task_type, duration_ms, status, error_message, "
                "ftal_f, ftal_t, ftal_a, ftal_gap, "
                "acceptance_passed, acceptance_details, acceptance_attempts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    user_id,
                    self.agent_type,
                    task_desc,
                    json.dumps(input_data or {}),
                    json.dumps(output_data or {}),
                    model_used,
                    task_type,
                    duration_ms,
                    status,
                    error_message,
                    scores.get("f"),
                    scores.get("t"),
                    scores.get("a"),
                    scores.get("gap"),
                    acceptance_passed,
                    acceptance_details,
                    acceptance_attempts,
                ),
            )
            conn.commit()
        return run_id

    def _get_user_profile(self, user_id):
        """Load user's LinkedIn + resume data as context for LLM scoring."""
        profile = {"user_id": user_id}

        # LinkedIn profile
        try:
            import linkedin_cache

            raw = linkedin_cache.get_raw(user_id)
            if raw:
                # Build experience from current_job + previous_jobs (canonical field names)
                experience = raw.get("experience", [])
                if not experience:
                    jobs = []
                    current = raw.get("current_job")
                    if isinstance(current, dict) and current.get("title"):
                        jobs.append(current)
                    prev = raw.get("previous_jobs", [])
                    if isinstance(prev, list):
                        jobs.extend(prev)
                    experience = jobs

                # Skills: prefer skills_and_endorsements over skills
                skills = raw.get("skills", [])
                if not skills:
                    endorsed = raw.get("skills_and_endorsements", [])
                    if isinstance(endorsed, list):
                        skills = endorsed

                profile["linkedin"] = {
                    "headline": raw.get("headline", ""),
                    "summary": raw.get("summary", ""),
                    "skills": skills,
                    "experience": experience,
                }
        except (ImportError, AttributeError):
            pass

        # Latest resume text
        with get_db() as conn:
            row = conn.execute(
                "SELECT parsed_text FROM resume_versions WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        if row and row[0]:
            profile["resume_text"] = row[0][:3000]

        # Deep profile summary (if available)
        try:
            from deep_profile import get_deep_profile_engine

            engine = get_deep_profile_engine()
            cached = engine.get_profile(user_id)
            if cached:
                if cached.get("differentiators"):
                    profile["differentiators"] = [
                        (d.get("theme", d.get("label", str(d))) if isinstance(d, dict) else str(d))
                        for d in cached["differentiators"][:5]
                    ]
                if cached.get("technology_mastery"):
                    techs = cached["technology_mastery"]
                    if isinstance(techs, list):
                        profile["top_technologies"] = [
                            (
                                t.get("name", t.get("technology", str(t)))
                                if isinstance(t, dict)
                                else str(t)
                            )
                            for t in techs[:20]
                        ]
                    elif isinstance(techs, dict):
                        profile["top_technologies"] = list(techs.keys())[:20]
                if cached.get("higher_order_skills"):
                    profile["higher_order_skills"] = [
                        (s.get("skill", s.get("name", s)) if isinstance(s, dict) else str(s))
                        for s in cached["higher_order_skills"][:10]
                    ]
        except Exception:
            pass

        return profile

    def _profile_summary(self, profile):
        """Create a compact text summary of the user profile for LLM prompts."""
        parts = []
        li = profile.get("linkedin", {})
        if li.get("headline"):
            parts.append(f"Headline: {li['headline']}")
        if li.get("summary"):
            parts.append(f"Summary: {li['summary'][:500]}")
        if li.get("skills"):
            skill_names = [
                s.get("skill", s.get("name", str(s))) if isinstance(s, dict) else str(s)
                for s in li["skills"][:30]
            ]
            parts.append(f"Skills: {', '.join(skill_names)}")
        if li.get("experience"):
            for exp in li["experience"][:3]:
                if isinstance(exp, dict):
                    parts.append(f"Experience: {exp.get('title', '')} at {exp.get('company', '')}")
        if profile.get("resume_text"):
            parts.append(f"Resume excerpt: {profile['resume_text'][:500]}")
        if profile.get("higher_order_skills"):
            parts.append(f"Higher-order skills: {', '.join(profile['higher_order_skills'])}")
        if profile.get("differentiators"):
            parts.append(f"Differentiators: {', '.join(profile['differentiators'])}")
        if profile.get("top_technologies"):
            parts.append(f"Technologies: {', '.join(profile['top_technologies'])}")
        return "\n".join(parts) if parts else "No profile data available."

    def _replace_placeholders(self, text, posting=None, user_name=None):
        """Replace common LLM placeholders with actual data."""
        if not text:
            return text

        if not user_name:
            try:
                import linkedin_cache

                for uid in list(linkedin_cache._profiles.keys()):
                    raw = linkedin_cache.get_raw(uid)
                    if raw:
                        candidate = raw.get("full_name") or raw.get("name", "")
                        if candidate:
                            user_name = candidate
                            break
            except (ImportError, AttributeError):
                user_name = ""

        title = posting.get("title", "") if posting else ""
        company = posting.get("company", "") if posting else ""

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
                text = text.replace(placeholder, value)
        return text

    def _timed(self, func, *args, **kwargs):
        """Run a function and return (result, duration_ms)."""
        start = time.time()
        result = func(*args, **kwargs)
        duration_ms = int((time.time() - start) * 1000)
        return result, duration_ms

    def _record_claim(
        self,
        user_id,
        task_type,
        input_text,
        output_text,
        metadata=None,
    ):
        """Record claim to gateway accountability system (fire-and-forget).

        Triggers after FTAL scoring to enable resume outputs to flow through
        gateway verification pipeline. Non-blocking; gateway unavailability
        does not interrupt agent execution.

        Args:
            user_id: User ID for claim attribution
            task_type: Agent task type (e.g., 'resume_tailor', 'cover_letter')
            input_text: Original input (job description, resume text, etc.)
            output_text: Generated output (optimized resume, cover letter, etc.)
            metadata: Optional dict with additional context (job_title, company, etc.)
        """
        try:
            from agents.claim_recorder import record_claim_async

            claim_id = f"ro-{self.agent_type}-{uuid.uuid4().hex[:8]}"
            coro = record_claim_async(
                claim_id=claim_id,
                source="resume_optimizer",
                task_type=task_type,
                user_id=user_id,
                input_text=input_text,
                output_text=output_text,
                metadata=metadata or {},
            )
            threading.Thread(
                target=asyncio.run, args=(coro,), daemon=True
            ).start()
        except Exception as e:
            # Import or execution error should not break agent — log and continue
            logger.debug(f"Failed to record claim: {e}")

    def _get_arango_context(
        self,
        user_id,
        agent_type,
        max_tokens=500,
    ):
        """CT-4: Fetch and format knowledge graph context for prompt injection.

        Queries ro_* collections based on agent type and injects quantified
        achievements, skills, milestones, and outcomes into the agent prompt.
        Non-blocking; ArangoDB unavailability returns empty string.

        Args:
            user_id: User ID for graph queries
            agent_type: Agent type (resume_tailor, cover_letter, etc.)
            max_tokens: Maximum token budget for context (default 500)

        Returns:
            Formatted string ready to prepend to prompt. Empty string on error.
        """
        try:
            from arango_query_helper import get_context_helper

            helper = get_context_helper()
            context = ""

            if agent_type == "resume_tailor":
                context = helper.get_project_context(user_id)
            elif agent_type == "cover_letter":
                context = helper.get_milestone_context(user_id)
            elif agent_type == "interview_coach":
                context = helper.get_outcomes_context(user_id)
            elif agent_type == "career_advisor":
                context = helper.get_skills_context(user_id)

            # Rough truncation: assume 4 chars per token
            max_chars = max_tokens * 4
            if len(context) > max_chars:
                context = context[:max_chars] + "..."

            return context
        except Exception as e:
            logger.debug(f"Failed to fetch ArangoDB context for {agent_type}: {e}")
            return ""
