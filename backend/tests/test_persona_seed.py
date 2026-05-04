"""Tests for persona_seed.py — voice/positioning extraction and seeding."""

from unittest.mock import MagicMock, patch

import persona_seed as ps

# ---------------------------------------------------------------------------
# Sample deep profile data
# ---------------------------------------------------------------------------

SAMPLE_PROFILE = {
    "professional_summary": (
        "Enterprise architect with 20+ years of experience in integration, "
        "API design, and data governance across financial and healthcare sectors."
    ),
    "career_arc": {
        "phases": [
            {"title": "IC Engineer", "period": "2003-2010", "focus": "Integration engineering"},
            {"title": "Lead Architect", "period": "2010-2018", "focus": "Enterprise architecture"},
            {
                "title": "Principal Architect",
                "period": "2018-present",
                "focus": "AI + platform strategy",
            },
        ],
        "trajectory": "IC → Lead → Principal Architect",
        "years_total": 22,
    },
    "technology_mastery": [
        {"name": "Python", "proficiency": "expert", "years_approx": 10},
        {"name": "Enterprise Integration", "proficiency": "expert", "years_approx": 20},
    ],
    "higher_order_skills": [
        {"skill": "Solution Architecture", "proficiency": "expert"},
        {"skill": "Enterprise Integration Strategy", "proficiency": "expert"},
        {"skill": "Team Leadership", "proficiency": "advanced"},
        {"skill": "Agentic AI Design", "proficiency": "advanced"},
    ],
    "business_impacts": [
        {
            "title": "Reduced API latency by 40%",
            "context": "OPI Project",
            "scope": "Enterprise-wide",
            "metrics": {"improvement": "40%"},
        },
        {
            "title": "Unified data governance framework",
            "context": "Navitus",
            "scope": "Enterprise-wide",
            "metrics": {"compliance": "100%"},
        },
        {
            "title": "Automated deployment pipeline",
            "context": "Internal",
            "scope": "Team",
            "metrics": {"time_saved": "80%"},
        },
    ],
    "leadership_profile": {
        "team_scope": "8-12 engineers",
        "mentoring_evidence": ["Mentored 5 junior architects"],
        "cross_functional": ["Led cross-team API standards initiative"],
        "decision_examples": ["Selected integration platform for $2M project"],
    },
    "differentiators": [
        {"theme": "Deep integration expertise across regulated industries"},
        {"theme": "Bridges business strategy and technical implementation"},
        {"theme": "Active AI/ML skill investment via hands-on side projects"},
    ],
    "knowledge_gaps": [
        {"area": "Frontend frameworks", "current_level": "beginner"},
    ],
}


MINIMAL_PROFILE = {
    "professional_summary": "Software developer.",
    "career_arc": {"phases": [], "trajectory": "", "years_total": 3},
    "technology_mastery": [],
    "higher_order_skills": [],
    "business_impacts": [],
    "leadership_profile": {},
    "differentiators": [],
}


# ---------------------------------------------------------------------------
# Voice extraction
# ---------------------------------------------------------------------------


class TestExtractVoice:
    def test_returns_dict(self):
        voice = ps._extract_voice(SAMPLE_PROFILE)
        assert isinstance(voice, dict)

    def test_has_base_tone(self):
        voice = ps._extract_voice(SAMPLE_PROFILE)
        assert "base_tone" in voice
        # Profile has leadership evidence
        assert "authoritative" in voice["base_tone"]

    def test_minimal_profile_gets_collaborative_tone(self):
        voice = ps._extract_voice(MINIMAL_PROFILE)
        assert "collaborative" in voice["base_tone"]

    def test_metric_preference_from_impacts(self):
        voice = ps._extract_voice(SAMPLE_PROFILE)
        assert voice["metric_preference"] == "metric-led"

    def test_narrative_preference_without_metrics(self):
        voice = ps._extract_voice(MINIMAL_PROFILE)
        assert voice["metric_preference"] == "narrative-led"

    def test_per_output_type_keys(self):
        voice = ps._extract_voice(SAMPLE_PROFILE)
        expected_types = {
            "resume",
            "cover_letter",
            "linkedin_post",
            "interview_prep",
            "career_advice",
        }
        assert set(voice["per_output_type"].keys()) == expected_types

    def test_each_output_type_has_tone_and_emphasis(self):
        voice = ps._extract_voice(SAMPLE_PROFILE)
        for otype, guidance in voice["per_output_type"].items():
            assert "tone" in guidance, f"{otype} missing tone"
            assert "emphasis" in guidance, f"{otype} missing emphasis"

    def test_signature_themes_from_differentiators(self):
        voice = ps._extract_voice(SAMPLE_PROFILE)
        assert "signature_themes" in voice
        assert len(voice["signature_themes"]) == 3

    def test_no_signature_themes_when_no_differentiators(self):
        voice = ps._extract_voice(MINIMAL_PROFILE)
        assert "signature_themes" not in voice or voice.get("signature_themes") == []

    def test_empty_profile_no_crash(self):
        voice = ps._extract_voice({})
        assert isinstance(voice, dict)
        assert "base_tone" in voice


# ---------------------------------------------------------------------------
# Positioning extraction
# ---------------------------------------------------------------------------


class TestExtractPositioning:
    def test_returns_dict(self):
        pos = ps._extract_positioning(SAMPLE_PROFILE)
        assert isinstance(pos, dict)

    def test_trajectory_from_arc(self):
        pos = ps._extract_positioning(SAMPLE_PROFILE)
        assert "IC" in pos["trajectory"]

    def test_years_from_arc(self):
        pos = ps._extract_positioning(SAMPLE_PROFILE)
        assert pos["years_experience"] == 22

    def test_strategic_leadership_orientation(self):
        pos = ps._extract_positioning(SAMPLE_PROFILE)
        # Profile has leadership + architecture + strategy signals
        assert "leadership" in pos["orientation"]

    def test_technical_specialist_for_minimal(self):
        pos = ps._extract_positioning(MINIMAL_PROFILE)
        assert pos["orientation"] == "technical-specialist"

    def test_enterprise_scope_from_impacts(self):
        pos = ps._extract_positioning(SAMPLE_PROFILE)
        assert pos["scope"] == "enterprise"

    def test_team_scope_without_enterprise_impacts(self):
        pos = ps._extract_positioning(MINIMAL_PROFILE)
        assert "team" in pos["scope"]

    def test_domain_depth_from_phases(self):
        pos = ps._extract_positioning(SAMPLE_PROFILE)
        assert len(pos["domain_depth"]) == 3
        assert "Integration engineering" in pos["domain_depth"]

    def test_seniority_cues(self):
        pos = ps._extract_positioning(SAMPLE_PROFILE)
        cues = pos["seniority_cues"]
        assert cues["team_scope"] == "8-12 engineers"
        assert cues["decision_authority"] is True
        assert cues["cross_functional"] is True

    def test_empty_profile_no_crash(self):
        pos = ps._extract_positioning({})
        assert isinstance(pos, dict)
        assert "orientation" in pos

    def test_metric_led_framing_with_enough_impacts(self):
        pos = ps._extract_positioning(SAMPLE_PROFILE)
        assert pos["framing_preference"] == "metric-led"

    def test_narrative_led_framing_without_impacts(self):
        pos = ps._extract_positioning(MINIMAL_PROFILE)
        assert pos["framing_preference"] == "narrative-led"


# ---------------------------------------------------------------------------
# seed_persona_from_profile
# ---------------------------------------------------------------------------


class TestSeedPersona:
    @patch("persona_seed.pf_remember")
    @patch("persona_seed.get_deep_profile_engine")
    def test_success_returns_seeded(self, mock_engine_factory, mock_remember):
        engine = MagicMock()
        engine.get_profile.return_value = SAMPLE_PROFILE
        mock_engine_factory.return_value = engine

        result = ps.seed_persona_from_profile(user_id=1)
        assert result["status"] == "seeded"
        assert result["namespace"] == "career_profile"
        assert "voice" in result
        assert "positioning" in result

    @patch("persona_seed.pf_remember")
    @patch("persona_seed.get_deep_profile_engine")
    def test_calls_pf_remember_twice(self, mock_engine_factory, mock_remember):
        engine = MagicMock()
        engine.get_profile.return_value = SAMPLE_PROFILE
        mock_engine_factory.return_value = engine

        ps.seed_persona_from_profile(user_id=1)
        assert mock_remember.call_count == 2  # voice + positioning

    @patch("persona_seed.pf_remember")
    @patch("persona_seed.get_deep_profile_engine")
    def test_voice_remember_call(self, mock_engine_factory, mock_remember):
        engine = MagicMock()
        engine.get_profile.return_value = SAMPLE_PROFILE
        mock_engine_factory.return_value = engine

        ps.seed_persona_from_profile(user_id=1)
        voice_call = mock_remember.call_args_list[0]
        assert voice_call[0][0] == "career_profile"  # namespace
        assert "voice" in voice_call[0][2]["category"]  # metadata

    @patch("persona_seed.pf_remember")
    @patch("persona_seed.get_deep_profile_engine")
    def test_positioning_remember_call(self, mock_engine_factory, mock_remember):
        engine = MagicMock()
        engine.get_profile.return_value = SAMPLE_PROFILE
        mock_engine_factory.return_value = engine

        ps.seed_persona_from_profile(user_id=1)
        pos_call = mock_remember.call_args_list[1]
        assert pos_call[0][0] == "career_profile"  # namespace
        assert "positioning" in pos_call[0][2]["category"]

    @patch("persona_seed.pf_remember")
    @patch("persona_seed.get_deep_profile_engine")
    def test_no_profile_returns_error(self, mock_engine_factory, mock_remember):
        engine = MagicMock()
        engine.get_profile.return_value = None
        mock_engine_factory.return_value = engine

        result = ps.seed_persona_from_profile(user_id=999)
        assert "error" in result
        assert mock_remember.call_count == 0

    @patch("persona_seed.pf_remember")
    @patch("persona_seed.get_deep_profile_engine")
    def test_voice_content_includes_output_types(self, mock_engine_factory, mock_remember):
        engine = MagicMock()
        engine.get_profile.return_value = SAMPLE_PROFILE
        mock_engine_factory.return_value = engine

        ps.seed_persona_from_profile(user_id=1)
        voice_content = mock_remember.call_args_list[0][0][1]
        for otype in ["resume", "cover_letter", "linkedin_post", "interview_prep", "career_advice"]:
            assert otype in voice_content

    @patch("persona_seed.pf_remember")
    @patch("persona_seed.get_deep_profile_engine")
    def test_positioning_content_includes_trajectory(self, mock_engine_factory, mock_remember):
        engine = MagicMock()
        engine.get_profile.return_value = SAMPLE_PROFILE
        mock_engine_factory.return_value = engine

        ps.seed_persona_from_profile(user_id=1)
        pos_content = mock_remember.call_args_list[1][0][1]
        assert "IC" in pos_content
        assert "22" in pos_content
