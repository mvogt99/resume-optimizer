"""Hybrid alignment scorer — 7-dimension requirement-to-candidate scoring.

Produces match_scores and match_type classification per JD requirement.

Scoring dimensions (weights sum to 1.0):
  semantic_similarity    (0.35) — sentence-transformer cosine via nlp_engine
  keyword_alignment      (0.20) — canonical skill overlap
  evidence_strength      (0.20) — ArangoDB graph traversal depth
  seniority_alignment    (0.10) — seniority signal matching
  domain_alignment       (0.05) — industry domain context
  leadership_alignment   (0.05) — leadership signal presence
  recency_alignment      (0.05) — recency of relevant experience

Match types (from production schema):
  direct                — strong match across multiple dimensions (score >= 0.80)
  direct_plus_inferred  — direct match with inferred/adjacent evidence (0.65–0.80)
  partial               — some evidence but gaps remain (0.40–0.65)
  weak                  — minimal relevant signal (0.20–0.40)
  none                  — no meaningful match (< 0.20)
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)

# Scoring dimension weights — must sum to 1.0
DIMENSION_WEIGHTS = {
    "semantic_similarity": 0.35,
    "keyword_alignment": 0.20,
    "evidence_strength": 0.20,
    "seniority_alignment": 0.10,
    "domain_alignment": 0.05,
    "leadership_alignment": 0.05,
    "recency_alignment": 0.05,
}

# Match type thresholds
_MATCH_THRESHOLDS = [
    ("direct", 0.80),
    ("direct_plus_inferred", 0.65),
    ("partial", 0.40),
    ("weak", 0.20),
]

# Seniority signals — used across dimensions
_SENIORITY_SIGNALS = [
    "architect", "principal", "lead", "director", "vp", "head of",
    "strategy", "roadmap", "enterprise", "governance", "staff engineer",
]

# Leadership signals
_LEADERSHIP_SIGNALS = [
    "led", "managed", "mentored", "directed", "owned", "drove",
    "established", "defined", "built team", "hired", "oversee",
]

# Domain keyword map — industry → keywords
_DOMAIN_KEYWORDS = {
    "healthcare": ["hipaa", "hl7", "fhir", "phi", "clinical", "formulary",
                   "pharmacy", "claims", "navitus", "opi"],
    "finance": ["fintech", "payments", "banking", "trading", "compliance",
                "sec", "sox", "pci"],
    "technology": ["saas", "platform", "cloud", "devops", "microservices"],
    "data": ["lakehouse", "data mesh", "warehouse", "medallion", "delta", "iceberg"],
}


def _classify_match_type(composite_score: float) -> str:
    """Convert composite score to match type enum."""
    for match_type, threshold in _MATCH_THRESHOLDS:
        if composite_score >= threshold:
            return match_type
    return "none"


def _score_semantic_similarity(
    requirement: dict,
    candidate_profile: dict,
    resume_text: str,
) -> float:
    """Compute semantic similarity between requirement text and resume/profile.

    Uses sentence-transformer model from nlp_engine if available, else 0.0.
    """
    req_text = requirement.get("text", "")
    if not req_text or not resume_text:
        return 0.0
    try:
        from nlp_engine import calculate_similarity
        # Compare requirement against full resume text (truncated for performance)
        return float(calculate_similarity(req_text, resume_text[:2000]))
    except Exception as e:
        logger.debug("hybrid_scorer: semantic similarity failed: %s", e)
        return 0.0


def _score_keyword_alignment(
    requirement: dict,
    candidate_profile: dict,
    resume_text: str,
) -> float:
    """Score canonical skill keyword overlap between requirement and candidate."""
    canonical_skills = requirement.get("canonical_skills", [])
    if not canonical_skills:
        return 0.5  # No skills to check — neutral

    skill_inventory = candidate_profile.get("skill_inventory", [])
    resume_lower = resume_text.lower()

    # Build flat set of all known aliases for candidate skills
    candidate_aliases: set = set()
    for item in skill_inventory:
        candidate_aliases.add(item.get("canonical_skill", "").lower())
        for alias in item.get("aliases", []):
            candidate_aliases.add(alias.lower())

    matched = 0
    in_resume = 0
    for skill in canonical_skills:
        skill_lower = skill.lower()
        if skill_lower in candidate_aliases:
            matched += 1
        if skill_lower in resume_lower:
            in_resume += 1

    total = len(canonical_skills)
    if total == 0:
        return 0.5

    # Weight: inventory match 60%, resume mention 40%
    inventory_score = matched / total
    resume_score = in_resume / total
    return min(1.0, inventory_score * 0.6 + resume_score * 0.4)


def _score_evidence_strength(
    requirement: dict,
    candidate_profile: dict,
) -> float:
    """Score evidence strength from ArangoDB graph depth.

    Uses experience_units (number of client engagements where this skill appears)
    as a proxy for graph evidence depth until ro_evidence_chunks is built (Phase B+).
    """
    canonical_skills = requirement.get("canonical_skills", [])
    if not canonical_skills:
        # Use experience_units count as weak signal
        exp_count = len(candidate_profile.get("experience_units", []))
        return min(1.0, exp_count * 0.15)

    skill_inventory = candidate_profile.get("skill_inventory", [])
    best_evidence = 0.0

    for skill in canonical_skills:
        skill_lower = skill.lower()
        for item in skill_inventory:
            canonical = item.get("canonical_skill", "").lower()
            aliases_lower = [a.lower() for a in item.get("aliases", [])]
            if canonical == skill_lower or skill_lower in aliases_lower:
                # evidence_refs count indicates depth of graph evidence
                evidence_count = len(item.get("evidence_refs", []))
                # Scoring: 1 ref = 0.3, 2 refs = 0.5, 3+ refs = 0.7+
                score = min(0.95, 0.3 + evidence_count * 0.2)
                best_evidence = max(best_evidence, score)

    return best_evidence


def _score_seniority_alignment(
    requirement: dict,
    candidate_profile: dict,
    resume_text: str,
) -> float:
    """Score seniority level alignment between requirement and candidate profile."""
    req_type = requirement.get("requirement_type", "other")
    req_text = requirement.get("text", "").lower()
    resume_lower = resume_text.lower()

    # Check if requirement expects seniority
    req_expects_senior = any(sig in req_text for sig in _SENIORITY_SIGNALS)
    req_expects_senior = req_expects_senior or req_type in ("leadership", "must_have")

    # Check candidate profile for seniority signals
    role_families = candidate_profile.get("target_role_families", [])
    senior_families = {"data_architect", "principal_engineer", "director_vp",
                       "solution_architect", "enterprise_architect", "consultant"}
    candidate_is_senior = bool(set(role_families) & senior_families)

    # Check resume text
    resume_has_senior = any(sig in resume_lower for sig in _SENIORITY_SIGNALS)

    if not req_expects_senior:
        return 0.8  # Requirement doesn't need seniority — neutral-positive

    if candidate_is_senior and resume_has_senior:
        return 1.0
    if candidate_is_senior or resume_has_senior:
        return 0.6
    return 0.2


def _score_domain_alignment(
    requirement: dict,
    candidate_profile: dict,
    resume_text: str,
) -> float:
    """Score domain/industry alignment between requirement and candidate experience."""
    req_type = requirement.get("requirement_type", "other")
    if req_type != "domain":
        return 0.7  # Non-domain requirements get neutral-positive pass

    req_text = requirement.get("text", "").lower()
    resume_lower = resume_text.lower()

    # Find which domain the requirement references
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in req_text for kw in keywords):
            # Check if candidate has experience in this domain
            domain_in_resume = any(kw in resume_lower for kw in keywords)
            # Check experience_units for domain context
            units = candidate_profile.get("experience_units", [])
            domain_in_units = any(
                any(kw in (u.get("company", "") + u.get("title", "")).lower()
                    for kw in keywords)
                for u in units
            )
            if domain_in_resume and domain_in_units:
                return 1.0
            if domain_in_resume or domain_in_units:
                return 0.6
            return 0.1

    return 0.5  # Unknown domain — neutral


def _score_leadership_alignment(
    requirement: dict,
    candidate_profile: dict,
    resume_text: str,
) -> float:
    """Score leadership signal alignment for leadership-type requirements."""
    req_type = requirement.get("requirement_type", "other")
    if req_type != "leadership":
        return 0.8  # Non-leadership requirement — neutral-positive

    resume_lower = resume_text.lower()
    has_leadership = any(sig in resume_lower for sig in _LEADERSHIP_SIGNALS)

    # Check experience_units for leadership signals
    units = candidate_profile.get("experience_units", [])
    unit_leadership = any(
        len(u.get("leadership_signals", [])) > 0 for u in units
    )

    if has_leadership and unit_leadership:
        return 1.0
    if has_leadership or unit_leadership:
        return 0.6
    return 0.1


def _score_recency_alignment(
    requirement: dict,
    candidate_profile: dict,
) -> float:
    """Score recency of relevant experience for this requirement.

    Checks experience_units date_range for recent activity with the skill.
    Recency: < 2 years = 1.0, 2-4 years = 0.7, 4-6 years = 0.4, > 6 years = 0.2
    """
    canonical_skills = requirement.get("canonical_skills", [])
    units = candidate_profile.get("experience_units", [])
    if not units:
        return 0.5  # No experience data — neutral

    current_year = date.today().year
    best_recency = 0.0

    for unit in units:
        # Check if this unit has relevant skills
        unit_skills = [s.lower() for s in unit.get("skills", [])]
        has_relevant_skill = any(
            s.lower() in unit_skills for s in canonical_skills
        ) if canonical_skills else True

        if not has_relevant_skill:
            continue

        # Parse end date (None = current role)
        date_range = unit.get("date_range", {})
        end = date_range.get("end")
        if end is None:
            years_ago = 0  # Current role
        else:
            try:
                end_year = int(str(end)[:4])
                years_ago = current_year - end_year
            except (ValueError, TypeError):
                years_ago = 3  # Unknown — assume mid-recency

        if years_ago <= 2:
            recency = 1.0
        elif years_ago <= 4:
            recency = 0.7
        elif years_ago <= 6:
            recency = 0.4
        else:
            recency = 0.2

        best_recency = max(best_recency, recency)

    return best_recency if best_recency > 0 else 0.5


def score_requirement(
    requirement: dict,
    candidate_profile: dict,
    resume_text: str,
) -> dict:
    """Score a single JD requirement against a candidate profile.

    Args:
        requirement:       Single requirement dict from jd_parser.parse_requirements().
        candidate_profile: Candidate profile from normalizer.normalize_candidate().
        resume_text:       Current resume text for keyword + semantic matching.

    Returns:
        Dict with composite_score, match_type, dimension_scores, and requirement_id.
        Never raises — returns zero scores on any error.
    """
    req_id = requirement.get("requirement_id", "")
    zero_result = {
        "requirement_id": req_id,
        "composite_score": 0.0,
        "match_type": "none",
        "dimension_scores": {k: 0.0 for k in DIMENSION_WEIGHTS},
    }

    try:
        dim_scores = {
            "semantic_similarity": _score_semantic_similarity(
                requirement, candidate_profile, resume_text
            ),
            "keyword_alignment": _score_keyword_alignment(
                requirement, candidate_profile, resume_text
            ),
            "evidence_strength": _score_evidence_strength(
                requirement, candidate_profile
            ),
            "seniority_alignment": _score_seniority_alignment(
                requirement, candidate_profile, resume_text
            ),
            "domain_alignment": _score_domain_alignment(
                requirement, candidate_profile, resume_text
            ),
            "leadership_alignment": _score_leadership_alignment(
                requirement, candidate_profile, resume_text
            ),
            "recency_alignment": _score_recency_alignment(
                requirement, candidate_profile
            ),
        }

        composite = sum(
            score * DIMENSION_WEIGHTS[dim]
            for dim, score in dim_scores.items()
        )
        composite = round(min(1.0, max(0.0, composite)), 4)

        return {
            "requirement_id": req_id,
            "composite_score": composite,
            "match_type": _classify_match_type(composite),
            "dimension_scores": {k: round(v, 4) for k, v in dim_scores.items()},
        }

    except Exception as exc:
        logger.error("hybrid_scorer: score_requirement failed for %s: %s", req_id, exc)
        return zero_result


def score_all_requirements(
    requirements: list,
    candidate_profile: dict,
    resume_text: str,
) -> list:
    """Score all JD requirements against candidate profile.

    Args:
        requirements:      List from jd_parser.parse_requirements().
        candidate_profile: Dict from normalizer.normalize_candidate().
        resume_text:       Current resume text.

    Returns:
        List of score dicts, sorted by composite_score descending.
        Never raises.
    """
    if not requirements:
        return []

    scores = []
    for req in requirements:
        score = score_requirement(req, candidate_profile, resume_text)
        scores.append(score)

    scores.sort(key=lambda s: s["composite_score"], reverse=True)
    return scores


def build_alignment_summary(
    requirements: list,
    scores: list,
    gaps: list,
) -> dict:
    """Build a summary dict for the full alignment analysis.

    Combines requirement scores + gap classifications into a display-ready summary.

    Args:
        requirements: List from jd_parser.
        scores:       List from score_all_requirements().
        gaps:         List from gap_classifier.classify_gaps().

    Returns:
        Summary dict with overall_score, match_distribution, coverage_pct,
        critical_gaps, and top_matches.
    """
    if not requirements:
        return {
            "overall_score": 0.0,
            "match_distribution": {},
            "coverage_pct": 0.0,
            "critical_gaps": 0,
            "top_matches": [],
        }

    # Build score index by requirement_id
    score_by_id = {s["requirement_id"]: s for s in scores}

    # Weighted overall score (weight by requirement importance)
    total_weight = sum(r.get("importance", 0.5) for r in requirements)
    weighted_sum = 0.0
    for req in requirements:
        req_id = req.get("requirement_id", "")
        importance = req.get("importance", 0.5)
        composite = score_by_id.get(req_id, {}).get("composite_score", 0.0)
        weighted_sum += composite * importance

    overall_score = round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0

    # Match distribution
    distribution: dict = {"direct": 0, "direct_plus_inferred": 0,
                          "partial": 0, "weak": 0, "none": 0}
    for s in scores:
        mt = s.get("match_type", "none")
        distribution[mt] = distribution.get(mt, 0) + 1

    # Coverage: % of requirements with at least partial match
    covered = sum(
        1 for s in scores
        if s.get("match_type") not in ("weak", "none")
    )
    coverage_pct = round(covered / len(requirements) * 100, 1) if requirements else 0.0

    # Critical gaps (high severity)
    critical_gaps = sum(1 for g in gaps if g.get("severity") == "high")

    # Top matches (direct + direct_plus_inferred, sorted by score)
    top_matches = [
        {
            "requirement_id": s["requirement_id"],
            "composite_score": s["composite_score"],
            "match_type": s["match_type"],
        }
        for s in scores
        if s.get("match_type") in ("direct", "direct_plus_inferred")
    ][:10]

    return {
        "overall_score": overall_score,
        "match_distribution": distribution,
        "coverage_pct": coverage_pct,
        "critical_gaps": critical_gaps,
        "top_matches": top_matches,
    }
