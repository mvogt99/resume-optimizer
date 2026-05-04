"""Gap classifier — maps JD requirements to 7-type evidence-based gap analysis.

Gap types (from production schema):
  missing_experience        — no evidence in career data for this requirement
  weak_wording              — evidence exists but resume doesn't express it well
  missing_explicit_keyword  — equivalent experience exists; ATS keyword absent
  insufficient_leadership_signal — did the work but resume doesn't show leadership
  seniority_mismatch        — experience exists at wrong level for the role
  domain_gap                — wrong industry context for the requirement
  unsupported_claim_risk    — resume claims something evidence doesn't support

Phase A uses ArangoDB graph + canonical skill inventory for gap detection.
Phase B (hybrid_scorer.py) will add 7-dimension scoring to refine these classifications.
"""

import hashlib
import json
import logging

logger = logging.getLogger(__name__)

# Module-level LLM import — allows test patching via patch("gap_classifier.call_llm_quality")
try:
    from llm_helper import call_llm_quality
except ImportError:  # pragma: no cover
    call_llm_quality = None  # type: ignore[assignment]

GAP_TYPES = {
    "missing_experience",
    "weak_wording",
    "missing_explicit_keyword",
    "insufficient_leadership_signal",
    "seniority_mismatch",
    "domain_gap",
    "unsupported_claim_risk",
}

SEVERITY = {"low", "medium", "high"}

# Seniority keywords that should appear for architect-level roles
_ARCHITECT_SIGNALS = [
    "architect", "principal", "lead", "director", "strategy", "roadmap",
    "governance", "design", "stakeholder", "enterprise",
]

# Leadership signals expected in principal/architect resumes
_LEADERSHIP_SIGNALS = [
    "led", "managed", "mentored", "directed", "owned", "drove",
    "established", "defined", "built team", "hired",
]


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def _extract_json(text, fallback: list) -> list:
    if text is None:
        return fallback
    if isinstance(text, list):
        return text
    if isinstance(text, dict):
        return text.get("gaps", fallback)
    cleaned = str(text).strip()
    for fence in ("```json", "```"):
        if fence in cleaned:
            start = cleaned.find(fence) + len(fence)
            end = cleaned.find("```", start)
            if end > start:
                cleaned = cleaned[start:end].strip()
                break
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return parsed.get("gaps", fallback)
    except (json.JSONDecodeError, ValueError):
        logger.warning("gap_classifier: non-JSON LLM response")
    return fallback


def _skill_in_inventory(skill_name: str, skill_inventory: list) -> bool:
    """Check if a skill name matches any canonical skill or alias in the inventory."""
    lower = skill_name.lower()
    for item in skill_inventory:
        if item.get("canonical_skill", "").lower() == lower:
            return True
        if any(a.lower() == lower for a in item.get("aliases", [])):
            return True
    return False


def _skill_in_resume(skill_name: str, resume_text: str) -> bool:
    """Check if skill name or a close variant appears in resume text."""
    lower = skill_name.lower()
    resume_lower = resume_text.lower()
    if lower in resume_lower:
        return True
    # Check common abbreviations
    abbrevs = {
        "apache kafka": "kafka", "amazon kinesis": "kinesis",
        "apache flink": "flink", "apache spark": "spark",
        "hipaa compliance": "hipaa", "hl7 / fhir": "hl7",
    }
    abbrev = abbrevs.get(lower)
    if abbrev and abbrev in resume_lower:
        return True
    return False


def _equivalent_in_inventory(skill_name: str, skill_inventory: list) -> str | None:
    """Find an equivalent/alias skill in inventory for a given skill name.

    Returns the canonical skill name if an equivalent exists, else None.
    Used to detect missing_explicit_keyword vs missing_experience.
    """
    from normalizer_skills import CANONICAL_SKILL_MAP
    lower = skill_name.lower()

    # Find which canonical group this skill belongs to
    target_key = None
    for key, mapping in CANONICAL_SKILL_MAP.items():
        aliases_lower = [a.lower() for a in mapping["aliases"]]
        if lower in aliases_lower or lower == key or mapping["canonical"].lower() == lower:
            target_key = key
            break

    if target_key is None:
        return None

    # Check if any alias of that group is in the inventory
    mapping = CANONICAL_SKILL_MAP[target_key]
    for alias in mapping["aliases"]:
        if _skill_in_inventory(alias, skill_inventory):
            return mapping["canonical"]

    return None


def _classify_single_requirement(
    requirement: dict,
    candidate_profile: dict,
    resume_text: str,
) -> dict | None:
    """Classify a single requirement gap using heuristic rules.

    Returns a gap dict, or None if no gap detected.
    """
    req_id = requirement.get("requirement_id", "")
    req_text = requirement.get("text", "")
    req_type = requirement.get("requirement_type", "other")
    canonical_skills = requirement.get("canonical_skills", [])
    importance = requirement.get("importance", 0.5)
    skill_inventory = candidate_profile.get("skill_inventory", [])
    resume_lower = resume_text.lower()

    # Skip low-importance or non-skill requirements from strict gap analysis
    if req_type in ("education", "other") and importance < 0.4:
        return None

    # ── Leadership requirement check ─────────────────────────────────────────
    if req_type == "leadership":
        has_leadership = any(sig in resume_lower for sig in _LEADERSHIP_SIGNALS)
        if not has_leadership:
            return {
                "gap_id": _sha1(f"gap-{req_id}-leadership"),
                "requirement_id": req_id,
                "gap_type": "insufficient_leadership_signal",
                "description": (
                    f"Requirement '{req_text[:100]}' calls for leadership evidence, "
                    "but the resume lacks explicit leadership language (led, managed, "
                    "drove, owned, established)."
                ),
                "severity": "high" if importance >= 0.8 else "medium",
                "recommended_action": (
                    "Add leadership verbs to relevant bullets. Frame contributions as "
                    "'Led X to achieve Y' rather than 'Worked on X'."
                ),
            }
        # Has leadership language — check if seniority level matches
        has_architect_signal = any(sig in resume_lower for sig in _ARCHITECT_SIGNALS)
        if not has_architect_signal:
            return {
                "gap_id": _sha1(f"gap-{req_id}-seniority"),
                "requirement_id": req_id,
                "gap_type": "seniority_mismatch",
                "description": (
                    f"Requirement '{req_text[:100]}' expects architect/principal-level "
                    "framing. Resume has leadership language but lacks seniority signals "
                    "(architect, principal, enterprise, strategy, governance)."
                ),
                "severity": "medium",
                "recommended_action": (
                    "Reframe experience at the architecture/strategy level. Use terms "
                    "like 'architected', 'designed the strategy for', 'led enterprise-wide'."
                ),
            }
        return None  # Leadership requirement met

    # ── Domain requirement check ──────────────────────────────────────────────
    if req_type == "domain":
        domain_keywords = [
            w.lower() for w in req_text.split()
            if len(w) > 4 and w.lower() not in ("with", "using", "their", "must", "have")
        ]
        domain_in_resume = any(kw in resume_lower for kw in domain_keywords[:5])
        if not domain_in_resume:
            return {
                "gap_id": _sha1(f"gap-{req_id}-domain"),
                "requirement_id": req_id,
                "gap_type": "domain_gap",
                "description": (
                    f"Domain requirement '{req_text[:100]}' is not reflected in resume "
                    "language. Key domain terms are absent."
                ),
                "severity": "medium",
                "recommended_action": (
                    "Add domain-specific terminology to the professional summary and "
                    "relevant experience bullets."
                ),
            }
        return None

    # ── Skill-based requirement check ────────────────────────────────────────
    for skill in canonical_skills:
        skill_lower = skill.lower()

        in_resume = _skill_in_resume(skill, resume_text)
        in_inventory = _skill_in_inventory(skill, skill_inventory)
        equivalent = _equivalent_in_inventory(skill, skill_inventory)

        if in_resume:
            # Skill is in resume — check if wording is weak
            # Weak wording: skill appears once in a list, no supporting context
            skill_count = resume_lower.count(skill_lower)
            nearby_action = any(
                sig in resume_lower[
                    max(0, resume_lower.find(skill_lower) - 100):
                    resume_lower.find(skill_lower) + 100
                ]
                for sig in ["built", "designed", "architected", "implemented",
                            "led", "delivered", "managed", "years"]
            )
            if skill_count <= 1 and not nearby_action:
                return {
                    "gap_id": _sha1(f"gap-{req_id}-{skill}-wording"),
                    "requirement_id": req_id,
                    "gap_type": "weak_wording",
                    "description": (
                        f"'{skill}' appears in the resume but without supporting context "
                        "(no action verbs, accomplishments, or quantification nearby)."
                    ),
                    "severity": "low",
                    "recommended_action": (
                        f"Add a bullet demonstrating concrete use of {skill}: what you "
                        "built, the scale, and the outcome."
                    ),
                }
            continue  # Skill present and well-expressed — no gap

        if equivalent:
            # Has equivalent skill in inventory but ATS keyword missing from resume
            return {
                "gap_id": _sha1(f"gap-{req_id}-{skill}-keyword"),
                "requirement_id": req_id,
                "gap_type": "missing_explicit_keyword",
                "description": (
                    f"ATS keyword '{skill}' is absent from the resume, but equivalent "
                    f"experience exists ({equivalent}). An ATS will not match this."
                ),
                "severity": "high" if importance >= 0.8 else "medium",
                "recommended_action": (
                    f"Add '{skill}' to the resume alongside your existing {equivalent} "
                    "experience (e.g., 'Kinesis/Kafka-compatible event streaming')."
                ),
            }

        if in_inventory and not in_resume:
            # In knowledge graph but not surfaced in resume — weak wording
            return {
                "gap_id": _sha1(f"gap-{req_id}-{skill}-surface"),
                "requirement_id": req_id,
                "gap_type": "weak_wording",
                "description": (
                    f"'{skill}' exists in your career knowledge graph but does not "
                    "appear in the resume text."
                ),
                "severity": "medium" if importance >= 0.7 else "low",
                "recommended_action": (
                    f"Add '{skill}' explicitly to your skills section or relevant "
                    "experience bullets."
                ),
            }

        # Not in resume, not in inventory — true gap
        return {
            "gap_id": _sha1(f"gap-{req_id}-{skill}-missing"),
            "requirement_id": req_id,
            "gap_type": "missing_experience",
            "description": (
                f"No evidence of '{skill}' found in resume or career knowledge graph."
            ),
            "severity": "high" if importance >= 0.85 else "medium",
            "recommended_action": (
                f"If you have any adjacent experience with {skill} or equivalent tools, "
                "surface it via the keyword equivalency interview."
            ),
        }

    # Requirement has no canonical_skills — do text-based check
    if req_type == "must_have":
        req_words = [
            w.lower() for w in req_text.split()
            if len(w) > 4 and w.isalpha()
        ]
        matches = sum(1 for w in req_words if w in resume_lower)
        if req_words and matches / len(req_words) < 0.3:
            return {
                "gap_id": _sha1(f"gap-{req_id}-text"),
                "requirement_id": req_id,
                "gap_type": "missing_explicit_keyword",
                "description": (
                    f"Must-have requirement '{req_text[:100]}' has low keyword overlap "
                    "with resume text."
                ),
                "severity": "high",
                "recommended_action": (
                    "Review this requirement and ensure the resume explicitly addresses it."
                ),
            }

    return None


def classify_gaps(
    requirements: list,
    candidate_profile: dict,
    resume_text: str,
    use_llm: bool = True,
) -> list:
    """Classify gaps between JD requirements and candidate evidence.

    Args:
        requirements:      List of requirement dicts from jd_parser.parse_requirements().
        candidate_profile: Candidate profile dict from normalizer.normalize_candidate().
        resume_text:       Current resume text for direct keyword matching.
        use_llm:           If True, use LLM to refine heuristic gaps (optional).

    Returns:
        List of gap dicts conforming to the production schema.
        Sorted by severity (high → medium → low) then importance.
        Never raises — returns [] on any error.
    """
    if not requirements:
        return []

    try:
        heuristic_gaps = []
        for req in requirements:
            gap = _classify_single_requirement(req, candidate_profile, resume_text)
            if gap:
                heuristic_gaps.append(gap)

        # LLM refinement: re-classify heuristic gaps and surface any missed ones
        if use_llm:
            heuristic_gaps = _refine_gaps_with_llm(
                heuristic_gaps, requirements, candidate_profile, resume_text
            )

        # Sort: high → medium → low
        order = {"high": 0, "medium": 1, "low": 2}
        heuristic_gaps.sort(key=lambda g: order.get(g.get("severity", "low"), 3))

        return heuristic_gaps

    except Exception as exc:
        logger.error("gap_classifier: unexpected error: %s", exc)
        return []


def _refine_gaps_with_llm(
    gaps: list,
    requirements: list,
    candidate_profile: dict,
    resume_text: str,
) -> list:
    """Use LLM to review and refine heuristically-classified gaps."""
    try:
        # Summarize what we have for context
        skill_names = [
            item.get("canonical_skill", "")
            for item in candidate_profile.get("skill_inventory", [])[:30]
        ]
        gap_summary = [
            {"req_id": g["requirement_id"], "type": g["gap_type"],
             "description": g["description"][:80]}
            for g in gaps[:15]
        ]

        prompt = f"""You are reviewing pre-classified resume gaps for accuracy.

CANDIDATE SKILL INVENTORY (canonical names):
{json.dumps(skill_names)}

RESUME TEXT (abbreviated):
{resume_text[:1000]}

PRE-CLASSIFIED GAPS:
{json.dumps(gap_summary, indent=2)}

Review each gap and correct any misclassifications. Common errors:
- "missing_experience" when the candidate clearly has equivalent skill (should be "missing_explicit_keyword")
- "weak_wording" when the skill simply isn't relevant to their background (should be "missing_experience")
- "seniority_mismatch" when the resume is strong but targeted at a different level

Return ONLY a JSON array of corrected gaps. Keep the same structure, only change \
gap_type, severity, description, or recommended_action where correction is needed. \
Do NOT add or remove gaps.

{{
  "gaps": [
    {{
      "gap_id": "<same gap_id>",
      "requirement_id": "<same>",
      "gap_type": "<corrected type from the 7 valid types>",
      "description": "<corrected description>",
      "severity": "low|medium|high",
      "recommended_action": "<corrected action>"
    }}
  ]
}}"""

        raw = call_llm_quality(prompt, task_type="analysis", max_tokens=1500)
        parsed_list = _extract_json(raw, [])

        if not parsed_list:
            # Try nested
            import json as _json
            try:
                obj = _json.loads(raw.strip()) if raw else {}
                parsed_list = obj.get("gaps", [])
            except Exception:
                pass

        if parsed_list:
            # Build index of heuristic gaps by gap_id for merging
            heuristic_by_id = {g["gap_id"]: dict(g) for g in gaps}
            refined = []
            for item in parsed_list:
                gap_id = item.get("gap_id", _sha1(item.get("description", str(item))))
                gap_type = item.get("gap_type", "missing_experience")
                severity = item.get("severity", "medium")
                # Only accept valid enum values
                if gap_type not in GAP_TYPES or severity not in SEVERITY:
                    continue
                if gap_id in heuristic_by_id:
                    # Correct existing heuristic gap
                    existing = heuristic_by_id[gap_id]
                    existing["gap_type"] = gap_type
                    existing["severity"] = severity
                    existing["description"] = item.get("description", existing["description"])
                    existing["recommended_action"] = item.get(
                        "recommended_action", existing.get("recommended_action", "")
                    )
                    refined.append(existing)
                else:
                    # LLM found an additional gap — accept it if it has required fields
                    if item.get("requirement_id") and item.get("description"):
                        item["gap_id"] = gap_id
                        refined.append(item)
            return refined if refined else gaps

    except Exception as e:
        logger.warning("gap_classifier: LLM refinement failed: %s", e)

    return gaps


def summarize_gaps(gaps: list) -> dict:
    """Produce a summary dict for frontend display."""
    by_type: dict = {}
    by_severity: dict = {"high": 0, "medium": 0, "low": 0}
    for gap in gaps:
        gt = gap.get("gap_type", "other")
        by_type[gt] = by_type.get(gt, 0) + 1
        sev = gap.get("severity", "low")
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return {
        "total": len(gaps),
        "by_type": by_type,
        "by_severity": by_severity,
        "critical_count": by_severity["high"],
    }
