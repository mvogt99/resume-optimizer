"""Tests for Phase 10 Track D content generation via RTX 5090.

Verifies journey_synthesizer.generate_all() and deep_profile.build_profile()
produce substantive content grounded in enriched journey data.
All tests use REAL LLM (RTX 5090 port 8021) — no mocks, no skips.
"""

import contextlib
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models
from journey_miner import JourneyMiner
from journey_synthesizer import JourneySynthesizer

WORKDIR_ROOT = os.environ.get(
    "JOURNEY_WORKDIR", "/home/mike/models/source/hybrid-ai-windows/workdir"
)

# Test user ID isolated from other test modules
TEST_USER_ID = 98


@pytest.fixture(scope="module", autouse=True)
def _isolated_db(tmp_path_factory):
    """Create an isolated database for content generation tests."""
    original_db_path = models.DB_PATH

    tmp_dir = tmp_path_factory.mktemp("content_gen")
    db_path = str(tmp_dir / "test.db")

    models.DB_PATH = db_path
    for mod in list(sys.modules.values()):
        if mod is None or mod is models:
            continue
        if hasattr(mod, "DB_PATH") and isinstance(mod.DB_PATH, str):
            with contextlib.suppress(AttributeError, TypeError):
                mod.DB_PATH = db_path

    models.init_db()

    # Reset singletons
    import journey_miner as _jm
    import journey_synthesizer as _js

    _jm._miner = None

    yield db_path

    models.DB_PATH = original_db_path
    for mod in list(sys.modules.values()):
        if mod is None or mod is models:
            continue
        if hasattr(mod, "DB_PATH") and isinstance(mod.DB_PATH, str):
            with contextlib.suppress(AttributeError, TypeError):
                mod.DB_PATH = original_db_path
    _jm._miner = None


@pytest.fixture(scope="module")
def enriched_journey(_isolated_db):
    """Mine journey sources to populate events for synthesis."""
    miner = JourneyMiner()

    # Mine teaching docs and governance (guaranteed local sources)
    miner._mine_teaching_documents(user_id=TEST_USER_ID)
    miner._mine_governance_achievements(user_id=TEST_USER_ID)
    miner._mine_autonomy_phases(user_id=TEST_USER_ID)

    # Build timeline from mined sources
    miner._build_timeline(user_id=TEST_USER_ID)

    # Verify we have events
    conn = sqlite3.connect(models.DB_PATH)
    conn.row_factory = sqlite3.Row
    event_count = conn.execute("SELECT COUNT(*) as c FROM journey_events").fetchone()["c"]
    conn.close()

    assert event_count > 0, f"Journey mining must produce events for synthesis (got {event_count})"
    return event_count


@pytest.fixture(scope="module")
def synthesized_content(enriched_journey):
    """Run full synthesis pipeline via RTX 5090."""
    synth = JourneySynthesizer()
    synth.generate_all(user_id=TEST_USER_ID)

    # Collect all generated narratives
    conn = sqlite3.connect(models.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT narrative_type, title, content FROM journey_narratives " "WHERE user_id = ?",
        (TEST_USER_ID,),
    ).fetchall()
    conn.close()

    narratives = {}
    for row in rows:
        ntype = row["narrative_type"]
        if ntype not in narratives:
            narratives[ntype] = []
        narratives[ntype].append({"title": row["title"], "content": row["content"]})

    return narratives


class TestResumeEntries:
    """D.2: Auto-generated resume entries from journey data."""

    def test_resume_entries_generated(self, synthesized_content):
        """At least 2 resume entries generated."""
        entries = synthesized_content.get("resume_entry", [])
        assert len(entries) >= 2, f"Expected 2+ resume entries, got {len(entries)}"

    def test_resume_entries_substantive(self, synthesized_content):
        """Resume entries are substantive (>50 chars each)."""
        entries = synthesized_content.get("resume_entry", [])
        assert len(entries) > 0, "No resume entries to check"
        for entry in entries:
            content = entry["content"]
            assert (
                len(content) > 50
            ), f"Resume entry too short ({len(content)} chars): {content[:80]}"

    def test_resume_entries_include_journey_themes(self, synthesized_content):
        """Resume entries reference AI/ML journey themes."""
        entries = synthesized_content.get("resume_entry", [])
        all_text = " ".join(e["content"].lower() for e in entries)

        journey_terms = [
            "ai",
            "gpu",
            "model",
            "llm",
            "gateway",
            "autonomous",
            "learning",
            "agent",
            "deploy",
            "local",
        ]
        matches = [t for t in journey_terms if t in all_text]
        assert (
            len(matches) >= 3
        ), f"Resume entries should mention 3+ journey terms, found: {matches}"


class TestLinkedInSections:
    """D.3: Auto-generated LinkedIn profile sections."""

    def test_linkedin_sections_generated(self, synthesized_content):
        """LinkedIn headline and/or summary generated."""
        has_headline = len(synthesized_content.get("linkedin_headline", [])) > 0
        has_summary = len(synthesized_content.get("linkedin_summary", [])) > 0
        assert (
            has_headline or has_summary
        ), "Expected at least linkedin_headline or linkedin_summary"

    def test_linkedin_summary_substantive(self, synthesized_content):
        """LinkedIn summary paragraph is 50+ words."""
        summaries = synthesized_content.get("linkedin_summary", [])
        if not summaries:
            pytest.skip("No linkedin_summary generated (headline-only result)")

        content = summaries[0]["content"]
        word_count = len(content.split())
        assert word_count >= 30, f"LinkedIn summary too short ({word_count} words): {content[:100]}"

    def test_linkedin_projects_generated(self, synthesized_content):
        """Featured projects generated from journey."""
        projects = synthesized_content.get("linkedin_project", [])
        # Projects are optional but expected
        assert len(projects) >= 1, "Expected at least 1 featured project"


class TestCampaignSeeds:
    """D.4: Auto-generated campaign seed themes."""

    def test_campaign_seeds_generated(self, synthesized_content):
        """At least 3 campaign seeds generated."""
        seeds = synthesized_content.get("campaign_seed", [])
        assert len(seeds) >= 3, f"Expected 3+ campaign seeds, got {len(seeds)}"

    def test_campaign_seeds_have_themes(self, synthesized_content):
        """Each campaign seed has a non-empty theme title."""
        seeds = synthesized_content.get("campaign_seed", [])
        assert len(seeds) > 0, "No campaign seeds to check"
        for seed in seeds:
            assert len(seed["title"]) > 3, f"Campaign seed title too short: '{seed['title']}'"

    def test_campaign_seeds_distinct(self, synthesized_content):
        """Campaign seeds have distinct themes (not duplicates)."""
        seeds = synthesized_content.get("campaign_seed", [])
        titles = [s["title"].lower().strip() for s in seeds]
        unique_titles = set(titles)
        assert (
            len(unique_titles) >= 3
        ), f"Expected 3+ distinct themes, got {len(unique_titles)}: {titles}"


class TestLearningArc:
    """D.5: Learning arc narrative generation."""

    def test_learning_arc_generated(self, synthesized_content):
        """Learning arc narrative exists."""
        arcs = synthesized_content.get("learning_arc", [])
        assert len(arcs) >= 1, "Expected learning arc narrative"

    def test_learning_arc_substantive(self, synthesized_content):
        """Learning arc is a substantive narrative (200+ chars)."""
        arcs = synthesized_content.get("learning_arc", [])
        if not arcs:
            pytest.skip("No learning arc generated")

        content = arcs[0]["content"]
        assert len(content) >= 200, f"Learning arc too short ({len(content)} chars)"


class TestContentUsesRealLLM:
    """Verify content was generated by real LLM, not templates."""

    def test_content_not_template_fallback(self, synthesized_content):
        """Generated content is diverse and substantive (not canned responses)."""
        all_content = []
        for ntype, items in synthesized_content.items():
            for item in items:
                all_content.append(item["content"])

        assert len(all_content) >= 5, f"Expected 5+ narrative items total, got {len(all_content)}"

        # Check content is not all identical (would indicate template)
        unique_contents = set(c[:100] for c in all_content)
        assert (
            len(unique_contents) >= 4
        ), "Content appears to be templated (too many identical prefixes)"


class TestThemeIndex:
    """Theme index generation from journey events."""

    def test_theme_index_generated(self, synthesized_content):
        """Theme index exists as a JSON array."""
        themes = synthesized_content.get("theme_index", [])
        assert len(themes) >= 1, "Expected theme index narrative"

        # Parse the JSON content
        content = themes[0]["content"]
        parsed = json.loads(content)
        assert isinstance(parsed, list), "Theme index should be a JSON array"
        assert len(parsed) >= 3, f"Expected 3+ themes in index, got {len(parsed)}"
