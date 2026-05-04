"""Candidate profile normalizer — produces normalized_candidate_profile.

Aggregates from:
  - LinkedIn profile (linkedin_cache)
  - ArangoDB knowledge graph (ro_skills, ro_business_outcomes, ro_client_projects)
  - Resume text (for section parsing)

Outputs a candidate_profile dict conforming to resume_optimizer_schema.production.json:
  candidate_id         — SHA-1 of candidate name
  target_role_families — inferred from LinkedIn headline + job target
  branding_summary     — from LinkedIn summary
  artifacts            — source file paths
  experience_units     — one per LinkedIn role + one per client project
  skill_inventory      — canonical skills with aliases + evidence_refs

Skill inventory building and alias mapping is in normalizer_skills.py.
"""

import hashlib
import logging

logger = logging.getLogger(__name__)

# Module-level LLM import — allows test patching via patch("normalizer.call_llm_quality")
try:
    from llm_helper import call_llm_quality
except ImportError:  # pragma: no cover
    call_llm_quality = None  # type: ignore[assignment]

# Known domain inference for client names
_CLIENT_DOMAIN_MAP = {
    "navitus": "healthcare",
    "opi": "healthcare",
    "ahead": "technology",
    "microsoft": "technology",
    "amazon": "technology",
}

# Role-family keyword mapping
_ROLE_FAMILY_SIGNALS = [
    (["enterprise architect", "ea", "togaf"], "enterprise_architect"),
    (["solution architect", "solutions architect"], "solution_architect"),
    (["data architect", "data platform architect"], "data_architect"),
    (["principal engineer", "principal architect"], "principal_engineer"),
    (["staff engineer"], "staff_engineer"),
    (["data engineer", "platform engineer"], "data_engineer"),
    (["software engineer", "software developer", "developer"], "software_engineer"),
    (["director", "vp ", "vice president", "head of"], "director_vp"),
    (["manager", "engineering manager", "program manager"], "manager"),
    (["consultant", "senior consultant", "principal consultant"], "consultant"),
]


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def _infer_role_families(headline: str, title: str) -> list:
    combined = (headline + " " + title).lower()
    families = []
    for signals, family in _ROLE_FAMILY_SIGNALS:
        if any(sig in combined for sig in signals):
            families.append(family)
    return families or ["consultant"]


def _build_experience_units_from_linkedin(linkedin_profile: dict) -> list:
    """Build experience_units from LinkedIn previous_jobs + current_job."""
    units = []
    jobs = list(linkedin_profile.get("previous_jobs", []) or [])
    current = linkedin_profile.get("current_job")
    if current and isinstance(current, dict):
        jobs = [current] + jobs

    for job in jobs:
        if not isinstance(job, dict):
            continue
        title = job.get("title", "")
        company = job.get("company", "")
        if not title and not company:
            continue

        desc = job.get("description", "") or ""
        dates = job.get("dates", {}) or {}
        if isinstance(dates, str):
            dates = {"raw": dates}

        # Extract impact bullets from description
        impacts = []
        action_kws = [
            "led", "designed", "architected", "built", "delivered",
            "reduced", "increased", "improved", "managed", "established",
            "created", "launched", "migrated", "saved",
        ]
        for line in desc.split("\n"):
            line = line.strip().lstrip("-•*").strip()
            if len(line) > 30 and any(kw in line.lower() for kw in action_kws):
                impacts.append(line[:200])

        leadership_signals = [
            s for s in ["stakeholder", "strategy", "governance", "team"]
            if s in desc.lower()
        ]
        scope = "enterprise" if any(
            s in (company + title).lower()
            for s in ["enterprise", "principal", "architect", "director", "vp"]
        ) else "client"

        exp_id = _sha1(f"{company}-{title}")
        units.append({
            "experience_id": exp_id,
            "title": title,
            "company": company,
            "date_range": {
                "start": dates.get("start", dates.get("raw", "")),
                "end": dates.get("end", None),
            },
            "scope_tags": [scope],
            "skills": [],
            "leadership_signals": leadership_signals,
            "impact_statements": impacts[:5],
            "evidence_refs": [f"linkedin:{exp_id}"],
        })

    return units


def _build_experience_units_from_arango(arango_client) -> list:
    """Build experience_units from ArangoDB client projects."""
    if not arango_client or not arango_client.is_connected:
        return []

    aql = """
    FOR proj IN ro_client_projects
      FILTER proj.name != null AND NOT STARTS_WITH(proj.name, "test_")
      LET skill_names = (
        FOR skill IN 1..1 OUTBOUND proj ro_client_demonstrated_skill
          LIMIT 10
          RETURN skill.name
      )
      LET outcome_titles = (
        FOR outcome IN 1..1 OUTBOUND proj ro_client_achieved_outcome
          LIMIT 5
          RETURN outcome.title
      )
      RETURN {
        name: proj.name,
        proj_id: proj._id,
        skills: skill_names,
        outcomes: outcome_titles
      }
    """
    try:
        projects = arango_client.query(aql)
    except Exception as e:
        logger.warning("normalizer: arango project query failed: %s", e)
        return []

    units = []
    for proj in projects:
        name = proj.get("name", "")
        if not name:
            continue
        exp_id = _sha1(f"project-{name}")
        units.append({
            "experience_id": exp_id,
            "title": "Data Platform Architect / Senior Consultant",
            "company": name,
            "date_range": {"start": "", "end": None},
            "scope_tags": ["client", "enterprise"],
            "skills": proj.get("skills", [])[:10],
            "leadership_signals": [],
            "impact_statements": proj.get("outcomes", [])[:5],
            "evidence_refs": [proj.get("proj_id", "")],
        })

    return units


def normalize_candidate(
    user_id: int,
    resume_text: str = "",
    target_job_title: str = "",
) -> dict:
    """Build normalized candidate profile from all available sources.

    Args:
        user_id:          User ID for LinkedIn cache lookup.
        resume_text:      Current resume text (optional, enables LLM skill enrichment).
        target_job_title: Target role title for role-family inference.

    Returns:
        candidate_profile dict conforming to the production schema.
        Never raises — returns minimal fallback on any error.
    """
    fallback = {
        "candidate_id": _sha1(str(user_id)),
        "target_role_families": ["data_architect", "consultant"],
        "branding_summary": "",
        "artifacts": {
            "linkedin_profile_path": "",
            "resume_paths": [],
            "experience_journey_path": "",
        },
        "experience_units": [],
        "skill_inventory": [],
    }

    try:
        # LinkedIn profile
        linkedin_profile: dict = {}
        try:
            from linkedin_cache import get_profile
            linkedin_profile = get_profile(user_id) or {}
        except Exception as e:
            logger.debug("normalizer: linkedin cache unavailable: %s", e)

        # ArangoDB client
        arango = None
        try:
            from arango_client import get_arango_client
            arango = get_arango_client()
        except Exception as e:
            logger.debug("normalizer: arango client unavailable: %s", e)

        full_name = linkedin_profile.get("full_name", f"User {user_id}")
        headline = linkedin_profile.get("headline", "")
        summary = linkedin_profile.get("summary", "")
        current_job = linkedin_profile.get("current_job") or {}
        current_title = current_job.get("title", "") if isinstance(current_job, dict) else ""

        candidate_id = _sha1(full_name.lower())
        target_role_families = _infer_role_families(
            headline, current_title or target_job_title
        )

        # Build experience units
        linkedin_units = _build_experience_units_from_linkedin(linkedin_profile)
        arango_units = _build_experience_units_from_arango(arango)

        # Merge: LinkedIn units first; add arango units for companies not already covered
        all_units = list(linkedin_units)
        linkedin_companies = {u["company"].lower() for u in linkedin_units}
        for unit in arango_units:
            if unit["company"].lower() not in linkedin_companies:
                all_units.append(unit)

        # Build skill inventory from ArangoDB canonical clustering
        from normalizer_skills import build_inventory_from_arango, enhance_inventory_with_llm
        skill_inventory = build_inventory_from_arango(arango)

        # LLM enrichment if resume text available
        if resume_text and len(resume_text) > 200:
            skill_inventory = enhance_inventory_with_llm(
                skill_inventory, resume_text, target_job_title
            )

        return {
            "candidate_id": candidate_id,
            "target_role_families": target_role_families,
            "branding_summary": summary[:500] if summary else "",
            "artifacts": {
                "linkedin_profile_path": f"linkedin_cache:{user_id}",
                "resume_paths": [],
                "experience_journey_path": "arango:ro_journey_milestones",
            },
            "experience_units": all_units,
            "skill_inventory": skill_inventory,
        }

    except Exception as exc:
        logger.error("normalizer: unexpected error: %s", exc)
        return fallback
