"""P1-D: LinkedIn narrative regeneration tests.

Tests that:
- Regenerated headline reflects leadership/practice-building positioning
- Old narratives are superseded (preserved with superseded_at timestamp)
- Campaign seeds align with deep profile differentiators
- journey_synthesizer.regenerate_linkedin_sections() exists and works
"""

import json
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, ".")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_ctx():
    import app as flask_app

    with flask_app.app.app_context():
        yield flask_app.app


@pytest.fixture()
def db_conn():
    """Provide a direct database connection for assertion queries."""
    from models import get_db_connection

    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture()
def synthesizer():
    from journey_synthesizer import JourneySynthesizer

    return JourneySynthesizer()


# ---------------------------------------------------------------------------
# P1-D.1: Schema — superseded_at column exists
# ---------------------------------------------------------------------------


class TestSupersededAtColumn:
    def test_journey_narratives_has_superseded_at(self, db_conn):
        """journey_narratives table must have a superseded_at column."""
        cursor = db_conn.execute("PRAGMA table_info(journey_narratives)")
        cols = [row["name"] for row in cursor]
        assert "superseded_at" in cols, (
            "journey_narratives is missing superseded_at column — " "run DB migration in models.py"
        )


# ---------------------------------------------------------------------------
# P1-D.1: regenerate_linkedin_sections method exists
# ---------------------------------------------------------------------------


class TestRegenerateLinkedInSections:
    def test_method_exists(self, synthesizer):
        """JourneySynthesizer must expose regenerate_linkedin_sections()."""
        assert hasattr(
            synthesizer, "regenerate_linkedin_sections"
        ), "JourneySynthesizer missing regenerate_linkedin_sections() method"

    def test_method_callable(self, synthesizer):
        assert callable(synthesizer.regenerate_linkedin_sections)

    def test_accepts_user_id_and_profile(self, synthesizer):
        """Method signature: regenerate_linkedin_sections(user_id, deep_profile, pf_context)."""
        import inspect

        sig = inspect.signature(synthesizer.regenerate_linkedin_sections)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert (
            "deep_profile" in params or len(params) >= 2
        ), f"Expected at least user_id + deep_profile params, got: {params}"


# ---------------------------------------------------------------------------
# P1-D.1: Headline reflects leadership positioning
# ---------------------------------------------------------------------------


LEADERSHIP_KEYWORDS = [
    "practice",
    "director",
    "principal",
    "leader",
    "vp",
    "vice president",
    "executive",
    "architect",
    "strategy",
    "enterprise",
    "advisory",
    "managing",
]


class TestHeadlinePositioning:
    def test_headline_not_ic_framing(self, db_conn, app_ctx, synthesizer):
        """Regenerated headline must NOT use IC-engineer framing."""
        ic_phrases = ["ai/ml engineer", "full-stack", "llm specialist"]

        fake_llm_output = json.dumps(
            {
                "headline": (
                    "Enterprise Data & AI Practice Leader" " | Director-Level Architect | P&L Owner"
                ),
                "summary_paragraph": (
                    "Senior practice leader with 15+ years building enterprise data and AI "
                    "capabilities across AHEAD, PwC, SPR, NVISIA, and PSC Group. "
                    "Led cross-functional teams and drove seven-figure P&L outcomes."
                ),
                "featured_projects": [
                    {
                        "title": "Enterprise AI Platform",
                        "description": "Led delivery of RTX 5090 AI platform for practice.",
                    },
                ],
            }
        )

        with patch("journey_synthesizer.call_llm_quality", return_value=fake_llm_output):
            result = synthesizer.regenerate_linkedin_sections(
                user_id=3,
                deep_profile={
                    "differentiators": ["Practice Builder", "P&L Leader"],
                    "technology_mastery": [{"name": "Azure"}],
                },
                pf_context="Senior practice leader with enterprise architecture background.",
            )

        assert result is not None, "regenerate_linkedin_sections returned None"
        headline = result.get("headline", "")
        assert headline, "Returned dict has empty headline"

        lower = headline.lower()
        for phrase in ic_phrases:
            assert phrase not in lower, f"Headline still uses IC framing '{phrase}': {headline}"

    def test_headline_contains_leadership_signal(self, db_conn, app_ctx, synthesizer):
        """Regenerated headline must contain at least one leadership keyword."""
        fake_output = json.dumps(
            {
                "headline": "Enterprise Data & AI Practice Leader | Director | P&L Owner",
                "summary_paragraph": "Senior practice leader with 15+ years...",
                "featured_projects": [],
            }
        )

        with patch("journey_synthesizer.call_llm_quality", return_value=fake_output):
            result = synthesizer.regenerate_linkedin_sections(
                user_id=3,
                deep_profile={"differentiators": ["Practice Builder"]},
                pf_context="",
            )

        headline = (result or {}).get("headline", "").lower()
        found = [kw for kw in LEADERSHIP_KEYWORDS if kw in headline]
        assert (
            found
        ), f"Headline has no leadership keywords (checked: {LEADERSHIP_KEYWORDS}): {headline!r}"


# ---------------------------------------------------------------------------
# P1-D.2: Old narratives superseded (not deleted)
# ---------------------------------------------------------------------------


class TestNarrativeSupersession:
    def test_old_narratives_superseded_not_deleted(self, db_conn, app_ctx, synthesizer):
        """After regeneration, old linkedin_headline rows get superseded_at set."""
        fake_output = json.dumps(
            {
                "headline": "Practice Director – Data & AI | Enterprise Architect",
                "summary_paragraph": "Senior leader with P&L ownership...",
                "featured_projects": [],
            }
        )

        # Count current headlines before
        before = db_conn.execute(
            "SELECT COUNT(*) FROM journey_narratives "
            "WHERE user_id=3 AND narrative_type='linkedin_headline'"
        ).fetchone()[0]

        with patch("journey_synthesizer.call_llm_quality", return_value=fake_output):
            synthesizer.regenerate_linkedin_sections(
                user_id=3,
                deep_profile={"differentiators": ["Practice Builder"]},
                pf_context="",
            )

        # After: old rows still exist (superseded, not deleted)
        after_total = db_conn.execute(
            "SELECT COUNT(*) FROM journey_narratives "
            "WHERE user_id=3 AND narrative_type='linkedin_headline'"
        ).fetchone()[0]

        assert after_total > before, "Expected a new linkedin_headline row to be inserted"

        # Old rows preserved
        old_rows = db_conn.execute(
            "SELECT COUNT(*) FROM journey_narratives "
            "WHERE user_id=3 AND narrative_type='linkedin_headline' "
            "AND superseded_at IS NOT NULL"
        ).fetchone()[0]

        # At least the previously existing rows should be superseded
        assert old_rows >= before, f"Expected {before} old rows to be superseded, got {old_rows}"

    def test_new_narrative_not_superseded(self, db_conn, app_ctx, synthesizer):
        """The newly inserted narrative row must NOT be superseded."""
        fake_output = json.dumps(
            {
                "headline": "Data Practice Director | Enterprise AI Leader",
                "summary_paragraph": "Leader in enterprise data platforms...",
                "featured_projects": [],
            }
        )

        with patch("journey_synthesizer.call_llm_quality", return_value=fake_output):
            synthesizer.regenerate_linkedin_sections(
                user_id=3,
                deep_profile={"differentiators": ["Enterprise Architect"]},
                pf_context="",
            )

        latest = db_conn.execute(
            "SELECT superseded_at FROM journey_narratives "
            "WHERE user_id=3 AND narrative_type='linkedin_headline' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

        assert latest is not None
        assert latest["superseded_at"] is None, "Newly inserted headline row must not be superseded"


# ---------------------------------------------------------------------------
# P1-D.3: Campaign seeds align with differentiators
# ---------------------------------------------------------------------------


class TestCampaignSeedAlignment:
    def test_regenerate_campaign_seeds_method_exists(self, synthesizer):
        assert hasattr(
            synthesizer, "regenerate_campaign_seeds"
        ), "JourneySynthesizer missing regenerate_campaign_seeds() method"

    def test_campaign_seeds_reference_differentiators(self, app_ctx, synthesizer):
        """Campaign seeds must include at least one differentiator theme."""
        differentiators = ["Practice Builder", "P&L Leader", "Enterprise Architect"]

        fake_output = json.dumps(
            {
                "campaign_seeds": [
                    {
                        "theme": "Building Data & AI Practices at Scale",
                        "audience": "CTOs and CDOs",
                        "content_angle": "Practice leadership lessons",
                    },
                    {
                        "theme": "Enterprise Architecture in the AI Era",
                        "audience": "Enterprise architects",
                        "content_angle": "Modernizing legacy stacks",
                    },
                ]
            }
        )

        with patch("journey_synthesizer.call_llm_quality", return_value=fake_output):
            result = synthesizer.regenerate_campaign_seeds(
                user_id=3,
                deep_profile={"differentiators": differentiators},
                linkedin_headline="Practice Director – Data & AI",
            )

        assert result is not None
        seeds = result.get("campaign_seeds", [])
        assert len(seeds) >= 1, "Expected at least 1 campaign seed"

        all_text = " ".join(
            (s.get("theme", "") + " " + s.get("content_angle", "")).lower() for s in seeds
        )
        # At least one seed should relate to practice/enterprise/leadership
        leadership_signals = ["practice", "enterprise", "architect", "leader", "p&l", "director"]
        found = [s for s in leadership_signals if s in all_text]
        assert found, f"No leadership signals found in campaign seeds. Seeds: {seeds}"


# ---------------------------------------------------------------------------
# P1-D.1: Summary paragraph quality
# ---------------------------------------------------------------------------


class TestSummaryQuality:
    def test_summary_min_100_words(self, app_ctx, synthesizer):
        """Regenerated summary must be at least 100 words."""
        long_summary = (
            "Senior practice leader with 15+ years building and scaling enterprise data and AI "
            "capabilities across healthcare, financial services, and professional services. "
            "Led cross-functional teams of 10-50 engineers and architects, delivering "
            "cloud-native data platforms and AI systems generating measurable business value. "
            "Director-level experience at AHEAD, PwC Advisory, SPR, NVISIA, and PSC Group "
            "with direct P&L ownership exceeding $10M annually. "
            "Proven track record driving strategic technology initiatives and building "
            "high-performance practices, translating complex AI capabilities into outcomes. "
            "Deep expertise in enterprise architecture, data strategy, agentic AI systems, and "
            "cloud-native platform engineering across Azure, AWS, and on-premises environments. "
            "Track record of delivering measurable ROI at enterprise scale."
        )
        fake_output = json.dumps(
            {
                "headline": "Practice Director – Data & AI | Enterprise Architect",
                "summary_paragraph": long_summary,
                "featured_projects": [],
            }
        )

        with patch("journey_synthesizer.call_llm_quality", return_value=fake_output):
            result = synthesizer.regenerate_linkedin_sections(
                user_id=3,
                deep_profile={"differentiators": ["Practice Builder"]},
                pf_context="",
            )

        summary = (result or {}).get("summary_paragraph", "")
        word_count = len(summary.split())
        assert word_count >= 100, f"Summary too short: {word_count} words (need ≥100)"

    def test_summary_no_ic_framing(self, app_ctx, synthesizer):
        """Summary must not frame as individual contributor."""
        ic_phrases = ["i'm learning", "my journey spans", "i'm a dedicated ai/ml engineer"]
        summary = (
            "Senior enterprise data and AI practice leader with 15 years driving "
            "strategic technology initiatives across Fortune 500 clients."
        )
        fake_output = json.dumps(
            {
                "headline": "Practice Director – Data & AI",
                "summary_paragraph": summary,
                "featured_projects": [],
            }
        )

        with patch("journey_synthesizer.call_llm_quality", return_value=fake_output):
            result = synthesizer.regenerate_linkedin_sections(
                user_id=3,
                deep_profile={"differentiators": ["Practice Builder"]},
                pf_context="",
            )

        actual = (result or {}).get("summary_paragraph", "").lower()
        for phrase in ic_phrases:
            assert phrase not in actual, f"Summary uses IC framing '{phrase}'"
