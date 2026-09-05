"""Tests for journey_synthesizer.py — narrative generation from journey events.

Seeds journey_events DB, monkeypatches call_llm for deterministic output.
"""

import json

import pytest
from test_helpers import query_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _seed_journey_events(app):
    """Seed journey_events with deterministic test data."""
    from models import get_db_connection

    conn = get_db_connection()
    for i in range(5):
        conn.execute(
            "INSERT INTO journey_events "
            "(user_id, event_date, title, category, technologies, source_ids) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                1,
                f"2026-01-{10 + i:02d}",
                f"Event {i}: built system component {i}",
                ["coding", "deployment", "analysis", "planning", "review"][i],
                json.dumps(["Python", "Docker", "FastAPI"] if i < 3 else ["React", "TypeScript"]),
                json.dumps([f"src_{i}"]),
            ),
        )
    conn.commit()
    conn.close()


@pytest.fixture()
def _patch_llm(monkeypatch):
    """Monkeypatch call_llm and synthesize_narrative to return deterministic results."""

    def fake_call_llm(prompt, task_type="coding", max_tokens=2048):
        # extract_json tries {…} before […], so wrap arrays in ```json to hit tier-1
        if "STAR-format resume bullet" in prompt:
            arr = json.dumps(
                [
                    {
                        "title": "AI Pipeline",
                        "bullet": "Built local AI pipeline reducing cloud costs by 90%",
                        "technologies": ["Python", "vLLM"],
                    },
                    {
                        "title": "Knowledge Graph",
                        "bullet": "Designed ArangoDB graph with 16 collections",
                        "technologies": ["ArangoDB"],
                    },
                ]
            )
            return f"```json\n{arr}\n```"
        if "LinkedIn profile additions" in prompt:
            return json.dumps(
                {
                    "headline_addition": "AI Infrastructure Architect",
                    "summary_paragraph": "Deployed local AI models on RTX 5090 for zero-cost inference.",
                    "featured_projects": [
                        {
                            "title": "Hybrid AI Gateway",
                            "description": "Multi-model orchestration gateway.",
                        },
                    ],
                }
            )
        if "campaign themes" in prompt:
            arr = json.dumps(
                [
                    {
                        "theme": "Local AI Revolution",
                        "description": "Cost-free AI inference on consumer GPUs",
                        "post_angles": ["angle1", "angle2", "angle3"],
                        "target_audience": "ML engineers",
                        "grounding_outcome": None,
                    },
                ]
            )
            return f"```json\n{arr}\n```"
        if "content themes" in prompt:
            arr = json.dumps(
                [
                    {
                        "theme": "GPU Optimization",
                        "description": "Getting max perf from RTX cards",
                        "evidence_count": 5,
                        "audience": "Engineers",
                        "sample_hook": "Did you know...",
                    },
                ]
            )
            return f"```json\n{arr}\n```"
        return "Generic LLM response"

    def fake_synthesize(context, prompt, max_tokens=2048):
        return "Phase 1: Foundation — learned Python and Docker. Phase 2: Specialization — deployed AI models locally."

    monkeypatch.setattr("llm_helper.call_llm", fake_call_llm)
    monkeypatch.setattr("journey_synthesizer.call_llm_quality", fake_call_llm)
    monkeypatch.setattr("llm_helper.synthesize_narrative", fake_synthesize)


# ---------------------------------------------------------------------------
# _get_events_summary / _get_skills_summary / _build_context
# ---------------------------------------------------------------------------


class TestEventAndSkillQueries:
    def test_get_events_summary_returns_seeded(self):
        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        events = synth._get_events_summary()
        assert len(events) == 5
        assert events[0]["title"].startswith("Event 0")
        assert events[0]["event_date"] == "2026-01-10"
        assert events[0]["category"] == "coding"

    def test_get_events_dates_ordered(self):
        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        events = synth._get_events_summary()
        dates = [e["event_date"] for e in events]
        assert dates == sorted(dates)

    def test_get_skills_summary_counts(self):
        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        skills = synth._get_skills_summary()
        skill_dict = dict(skills)
        # Python appears in events 0,1,2 → count 3
        assert skill_dict.get("Python", 0) == 3
        assert skill_dict.get("Docker", 0) == 3
        # React in events 3,4 → count 2
        assert skill_dict.get("React", 0) == 2
        # Sorted by frequency descending
        assert skills[0][1] >= skills[-1][1]

    def test_build_context_format(self):
        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        events = synth._get_events_summary()
        skills = synth._get_skills_summary()
        context = synth._build_context(events, skills)
        assert "=== AI Journey Timeline" in context
        assert "=== Skills (by frequency)" in context
        assert "Event 0" in context
        assert "Python:" in context


# ---------------------------------------------------------------------------
# _store_narrative — DB verification
# ---------------------------------------------------------------------------


class TestStoreNarrative:
    def test_store_inserts_row(self):
        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        synth._store_narrative(1, "resume_entry", "Test Title", "Test bullet content")

        rows = query_db(
            "SELECT narrative_type, title, content FROM journey_narratives WHERE user_id = 1"
        )
        assert len(rows) == 1
        assert rows[0]["narrative_type"] == "resume_entry"
        assert rows[0]["title"] == "Test Title"
        assert rows[0]["content"] == "Test bullet content"

    def test_store_multiple_types(self):
        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        synth._store_narrative(1, "resume_entry", "Entry", "bullet")
        synth._store_narrative(1, "linkedin_headline", "Headline", "AI Architect")
        synth._store_narrative(1, "campaign_seed", "Theme", '{"theme": "AI"}')

        rows = query_db(
            "SELECT narrative_type FROM journey_narratives WHERE user_id = 1 ORDER BY narrative_type"
        )
        types = [r["narrative_type"] for r in rows]
        assert "campaign_seed" in types
        assert "linkedin_headline" in types
        assert "resume_entry" in types


# ---------------------------------------------------------------------------
# generate_all — full pipeline with monkeypatched LLM
# ---------------------------------------------------------------------------


class TestGenerateAll:
    def test_generate_all_stores_narratives(self, _patch_llm):
        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        synth.generate_all(user_id=1)

        rows = query_db("SELECT narrative_type, title FROM journey_narratives WHERE user_id = 1")
        types = [r["narrative_type"] for r in rows]
        # Should have: resume_entry (2), linkedin_headline, linkedin_summary, linkedin_project,
        # campaign_seed, learning_arc, theme_index
        assert "resume_entry" in types
        assert "linkedin_headline" in types
        assert "linkedin_summary" in types
        assert "campaign_seed" in types
        assert "learning_arc" in types
        assert "theme_index" in types

    def test_generate_all_resume_entries_content(self, _patch_llm):
        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        synth.generate_all(user_id=1)

        entries = query_db(
            "SELECT title, content FROM journey_narratives "
            "WHERE user_id = 1 AND narrative_type = 'resume_entry'"
        )
        assert len(entries) == 2
        assert entries[0]["title"] == "AI Pipeline"
        assert "cloud costs" in entries[0]["content"]

    def test_generate_all_empty_events(self, _patch_llm):
        """No events — generate_all returns early, no narratives stored."""
        from models import get_db_connection

        conn = get_db_connection()
        conn.execute("DELETE FROM journey_events")
        conn.commit()
        conn.close()

        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        synth.generate_all(user_id=1)

        rows = query_db("SELECT COUNT(*) as cnt FROM journey_narratives WHERE user_id = 1")
        assert rows[0]["cnt"] == 0


# ---------------------------------------------------------------------------
# generate_with_interview_context
# ---------------------------------------------------------------------------


class TestGenerateWithInterview:
    def test_interview_context_stores_narratives(self, _patch_llm):
        """Monkeypatched LLM returns structured JSON → narratives stored."""

        def fake_call_interview(prompt, task_type="coding", max_tokens=2048):
            obj = json.dumps(
                {
                    "resume_bullets": ["Built AI system on RTX 5090", "Designed knowledge graph"],
                    "linkedin_summary": "Expert in local AI deployment.",
                    "key_themes": ["AI Infrastructure", "Knowledge Graphs"],
                }
            )
            return f"```json\n{obj}\n```"

        import journey_synthesizer as js_mod
        import llm_helper

        orig_helper = llm_helper.call_llm
        orig_js = js_mod.call_llm
        llm_helper.call_llm = fake_call_interview
        js_mod.call_llm = fake_call_interview
        try:
            from journey_synthesizer import JourneySynthesizer

            synth = JourneySynthesizer()
            synth.generate_with_interview_context(1, "I want to focus on AI infrastructure.")

            rows = query_db(
                "SELECT narrative_type, content FROM journey_narratives WHERE user_id = 1"
            )
            types = [r["narrative_type"] for r in rows]
            assert "resume_entry" in types
            assert "linkedin_summary" in types
            assert "campaign_seed" in types
        finally:
            llm_helper.call_llm = orig_helper
            js_mod.call_llm = orig_js


# ---------------------------------------------------------------------------
# _get_business_outcomes_summary
# ---------------------------------------------------------------------------


class TestBusinessOutcomes:
    def test_empty_projects(self):
        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        outcomes = synth._get_business_outcomes_summary()
        assert outcomes == []

    def test_outcomes_from_approved_projects(self):
        from models import get_db_connection

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO client_projects (user_id, client_name, folder_id, approved, business_outcomes_json) "
            "VALUES (1, 'TestCo', 'test_folder_1', 1, ?)",
            (
                json.dumps(
                    [
                        {
                            "outcome_title": "Cost Savings",
                            "outcome_type": "cost_reduction",
                            "metric_value": "$2M",
                            "confidence": 0.9,
                        },
                        {
                            "outcome_title": "Speed Boost",
                            "outcome_type": "efficiency_improvement",
                            "metric_value": "3x",
                            "confidence": 0.8,
                        },
                    ]
                ),
            ),
        )
        conn.commit()
        conn.close()

        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        outcomes = synth._get_business_outcomes_summary()
        assert len(outcomes) == 2
        # cost_reduction rank=10 > efficiency_improvement rank=9
        assert outcomes[0]["type"] == "cost_reduction"
        assert outcomes[0]["title"] == "Cost Savings"
        assert outcomes[0]["client"] == "TestCo"
        assert outcomes[0]["metric"] == "$2M"

    def test_outcomes_limited_to_ten(self):
        from models import get_db_connection

        conn = get_db_connection()
        bo_list = [
            {"outcome_title": f"Outcome {i}", "outcome_type": "revenue_growth", "confidence": 0.5}
            for i in range(15)
        ]
        conn.execute(
            "INSERT INTO client_projects (user_id, client_name, folder_id, approved, business_outcomes_json) "
            "VALUES (1, 'BigCo', 'test_folder_2', 1, ?)",
            (json.dumps(bo_list),),
        )
        conn.commit()
        conn.close()

        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        outcomes = synth._get_business_outcomes_summary()
        assert len(outcomes) <= 10

    def test_unapproved_projects_excluded(self):
        from models import get_db_connection

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO client_projects (user_id, client_name, folder_id, approved, business_outcomes_json) "
            "VALUES (1, 'DraftCo', 'test_folder_3', 0, ?)",
            (json.dumps([{"outcome_title": "Draft", "outcome_type": "revenue_growth"}]),),
        )
        conn.commit()
        conn.close()

        from journey_synthesizer import JourneySynthesizer

        synth = JourneySynthesizer()
        outcomes = synth._get_business_outcomes_summary()
        assert all(o["client"] != "DraftCo" for o in outcomes)


# ---------------------------------------------------------------------------
# Outcome type ranking
# ---------------------------------------------------------------------------


class TestOutcomeTypeRanking:
    def test_ranking_order(self):
        from journey_synthesizer import _OUTCOME_TYPE_RANK

        assert _OUTCOME_TYPE_RANK["revenue_growth"] > _OUTCOME_TYPE_RANK["cost_reduction"]
        assert _OUTCOME_TYPE_RANK["cost_reduction"] > _OUTCOME_TYPE_RANK["efficiency_improvement"]
        assert _OUTCOME_TYPE_RANK["time_savings"] == 1
        assert _OUTCOME_TYPE_RANK["revenue_growth"] == 11
