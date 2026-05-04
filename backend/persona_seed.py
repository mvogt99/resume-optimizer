"""Career persona namespace design and seeding from deep profile data.

The career_profile namespace stores three categories of persona memory
that shape how the LLM generates career content:

1. **Voice** — linguistic characteristics derived from the user's own
   writing: formality level, vocabulary tier, sentence structure, and
   how these shift across output types (resume=formal/concise,
   LinkedIn=conversational/narrative, cover_letter=balanced/persuasive,
   interview=confident/STAR-structured).

2. **Positioning** — career identity signals: where the user sits on the
   IC↔leadership spectrum, strategic↔tactical orientation, domain depth
   vs breadth, and preferred framing of accomplishments (metric-led vs
   narrative-led). Derived from LinkedIn headline, career arc trajectory,
   and business impact patterns.

3. **Patterns** — proven narrative structures that scored well in previous
   FTAL evaluations: bullet formats, keyword density ranges, tone markers
   per audience. These accumulate over time via pf_remember after gap<30
   outputs, creating a feedback loop that tunes generation quality.

Seeding:
    seed_persona_from_profile(user_id) reads the user's deep profile from
    the database and stores the initial voice + positioning memories.
    Pattern memories are NOT seeded — they grow organically from successful
    outputs via the call_llm_scored → pf_remember loop in llm_helper.py.
"""

from __future__ import annotations

import logging
from typing import Any

from deep_profile import get_deep_profile_engine
from personaforge_client import CAREER_NAMESPACE, pf_remember

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Voice extraction from deep profile
# ---------------------------------------------------------------------------


def _extract_voice(profile: dict[str, Any]) -> dict[str, Any]:
    """Derive voice characteristics from existing profile data.

    Returns a voice descriptor dict with per-output-type guidance.
    """
    leadership = profile.get("leadership_profile", {})
    differentiators = profile.get("differentiators", [])
    impacts = profile.get("business_impacts", [])

    # Infer formality from summary style
    # Long-tenure professionals with leadership evidence lean formal-precise
    has_leadership = bool(leadership.get("team_scope") or leadership.get("mentoring_evidence"))
    has_metrics = any(i.get("metrics") for i in impacts) if impacts else False

    voice: dict[str, Any] = {
        "base_tone": (
            "professional-authoritative" if has_leadership else "professional-collaborative"
        ),
        "vocabulary_tier": "senior-technical",  # default for deep-profile users
        "metric_preference": "metric-led" if has_metrics else "narrative-led",
        "per_output_type": {
            "resume": {
                "tone": "formal-concise",
                "sentence_style": "action-verb-led bullets",
                "emphasis": "quantified impact, then technology, then scope",
            },
            "cover_letter": {
                "tone": "persuasive-balanced",
                "sentence_style": "varied paragraph + occasional bullet",
                "emphasis": "cultural fit + value proposition + specific company alignment",
            },
            "linkedin_post": {
                "tone": "conversational-authoritative",
                "sentence_style": "short paragraphs, hooks, whitespace",
                "emphasis": "insight-first, experience as evidence, call to engagement",
            },
            "interview_prep": {
                "tone": "confident-structured",
                "sentence_style": "STAR framework with natural transitions",
                "emphasis": "situation context, then specific actions, then measurable results",
            },
            "career_advice": {
                "tone": "analytical-supportive",
                "sentence_style": "assessment + options + recommendation",
                "emphasis": "market context, skill gaps framed as growth opportunities",
            },
        },
    }

    # Enrich with differentiator themes (what makes this person distinctive)
    if differentiators:
        voice["signature_themes"] = [
            d.get("theme", "") for d in differentiators[:5] if d.get("theme")
        ]

    return voice


# ---------------------------------------------------------------------------
# Positioning extraction from deep profile
# ---------------------------------------------------------------------------


def _extract_positioning(profile: dict[str, Any]) -> dict[str, Any]:
    """Derive career positioning from profile data.

    Returns a positioning descriptor that tells the LLM how to frame
    this person's career narrative.
    """
    arc = profile.get("career_arc", {})
    leadership = profile.get("leadership_profile", {})
    higher_order = profile.get("higher_order_skills", [])
    impacts = profile.get("business_impacts", [])

    # Trajectory tells us IC vs leadership vs architect
    trajectory = arc.get("trajectory", "")
    years = arc.get("years_total", 0)

    # Determine primary orientation
    leadership_signals = sum(
        1
        for s in higher_order
        if any(
            kw in (s.get("skill", "") or "").lower()
            for kw in ["leadership", "architecture", "strategy", "governance", "mentoring"]
        )
    )
    technical_signals = sum(
        1
        for s in higher_order
        if any(
            kw in (s.get("skill", "") or "").lower()
            for kw in ["coding", "engineering", "development", "implementation", "design"]
        )
    )

    if leadership_signals > technical_signals:
        orientation = "strategic-leadership"
    elif leadership_signals == technical_signals and leadership_signals > 0:
        orientation = "technical-leadership"
    else:
        orientation = "technical-specialist"

    # Scope from business impacts
    enterprise_scope = sum(1 for i in impacts if "enterprise" in (i.get("scope", "") or "").lower())

    positioning: dict[str, Any] = {
        "trajectory": trajectory or "experienced professional",
        "years_experience": years,
        "orientation": orientation,
        "scope": "enterprise" if enterprise_scope >= 2 else "team/department",
        "domain_depth": [],
        "framing_preference": "metric-led" if len(impacts) >= 3 else "narrative-led",
        "seniority_cues": {
            "team_scope": leadership.get("team_scope", ""),
            "decision_authority": bool(leadership.get("decision_examples")),
            "cross_functional": bool(leadership.get("cross_functional")),
        },
    }

    # Extract domain depth from career phases
    phases = arc.get("phases", [])
    if phases:
        positioning["domain_depth"] = [p.get("focus", "") for p in phases if p.get("focus")][:5]

    return positioning


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def seed_persona_from_profile(user_id: int) -> dict[str, Any]:
    """Seed the career_profile PersonaForge namespace from the user's deep profile.

    Reads the latest deep profile from SQLite and stores voice + positioning
    memories in PersonaForge. Pattern memories are NOT seeded — they grow
    from successful FTAL outputs.

    Returns a summary dict of what was seeded, or {"error": ...} on failure.
    """
    engine = get_deep_profile_engine()
    profile = engine.get_profile(user_id)

    if not profile:
        logger.warning("[PersonaSeed] No deep profile found for user_id=%s", user_id)
        return {"error": "no_deep_profile", "message": "Build a deep profile first."}

    voice = _extract_voice(profile)
    positioning = _extract_positioning(profile)

    # Store voice as a formatted context block
    voice_content = (
        f"Professional voice profile:\n"
        f"Base tone: {voice['base_tone']}\n"
        f"Vocabulary: {voice['vocabulary_tier']}\n"
        f"Metric preference: {voice['metric_preference']}\n"
    )
    if voice.get("signature_themes"):
        voice_content += f"Signature themes: {', '.join(voice['signature_themes'])}\n"
    voice_content += "\nPer-output-type guidance:\n"
    for output_type, guidance in voice["per_output_type"].items():
        voice_content += f"  {output_type}: {guidance['tone']} — {guidance['emphasis']}\n"

    pf_remember(
        CAREER_NAMESPACE,
        voice_content,
        {
            "category": "voice",
            "confidence": 0.9,
            "style_tags": ["voice", "persona_seed"],
            "source": "deep_profile",
            "user_id": user_id,
        },
    )

    # Store positioning as a formatted context block
    pos_content = (
        f"Career positioning:\n"
        f"Trajectory: {positioning['trajectory']}\n"
        f"Years: {positioning['years_experience']}\n"
        f"Orientation: {positioning['orientation']}\n"
        f"Scope: {positioning['scope']}\n"
        f"Framing: {positioning['framing_preference']}\n"
    )
    if positioning.get("domain_depth"):
        pos_content += f"Domain depth: {', '.join(positioning['domain_depth'])}\n"
    sc = positioning.get("seniority_cues", {})
    if sc.get("team_scope"):
        pos_content += f"Team scope: {sc['team_scope']}\n"
    if sc.get("decision_authority"):
        pos_content += "Has decision authority evidence.\n"
    if sc.get("cross_functional"):
        pos_content += "Cross-functional collaboration evidence.\n"

    pf_remember(
        CAREER_NAMESPACE,
        pos_content,
        {
            "category": "positioning",
            "confidence": 0.9,
            "style_tags": ["positioning", "persona_seed"],
            "source": "deep_profile",
            "user_id": user_id,
        },
    )

    logger.info(
        "[PersonaSeed] Seeded career persona for user_id=%s: voice=%d chars, positioning=%d chars",
        user_id,
        len(voice_content),
        len(pos_content),
    )

    return {
        "status": "seeded",
        "voice": voice,
        "positioning": positioning,
        "namespace": CAREER_NAMESPACE,
    }
