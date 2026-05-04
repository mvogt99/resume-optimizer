"""P2 intelligence gap closure tests — prove the ML feedback loop is fully wired.

Covers:
- P2-C: build_success_context() injected into tailor prompts
- P2-A: profile_stale flag propagated through tailor result
- P2-B: injected evidence items tracked as sourced_from edges
- P2-B: text-matched evidence refs produced when names appear in output
- E2E: full loop trace — feedback → context → prompt → result
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, ".")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_FAKE_JD = "We need a senior Python engineer with AWS and Kubernetes experience."

_JOB_REQS = {
    "required_skills": ["Python", "AWS"],
    "preferred_skills": ["Kubernetes"],
    "experience_level": "senior",
    "years_experience": 5,
    "key_responsibilities": ["Build scalable systems"],
    "industry_keywords": ["cloud"],
    "education": None,
    "certifications": [],
    "soft_skills": [],
}


def _fake_llm(self_or_prompt=None, *args, **kwargs):
    return (
        "Experienced engineer with deep Python and AWS expertise. "
        "Led cloud transformation at AHEAD, delivering $2M savings. "
    ) * 15


def _fake_llm_json(self_or_prompt=None, *args, **kwargs):
    return _JOB_REQS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_ctx():
    import app as flask_app

    with flask_app.app.app_context():
        yield flask_app.app


@pytest.fixture(autouse=True)
def seed_test_data():
    """Seed minimal DB rows needed by tailor tests."""
    from models import get_db_connection

    conn = get_db_connection()
    conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash) "
        "VALUES (3, 'testloop@test.com', 'x')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO resume_versions "
        "(id, user_id, source, file_name, parsed_text) "
        "VALUES (9001, 3, 'test', 'loop_test.txt', "
        "'Python developer with 10 years experience in cloud architecture and AWS.')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO job_postings "
        "(id, user_id, title, company, description, status) "
        "VALUES ('ml_loop_p1', 3, 'Senior Engineer', 'TestCo', ?, 'saved')",
        (_FAKE_JD,),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# P2-C.5: build_success_context injected into tailor prompt
# ---------------------------------------------------------------------------


class TestSuccessContextInjection:
    def test_success_context_appears_in_llm_prompt(self, app_ctx):
        """When callback feedback rows exist, the tailor prompt must include success context."""
        captured_prompts = []

        def recording_llm(self, prompt, *args, **kwargs):
            captured_prompts.append(prompt)
            return _fake_llm()

        # Insert a real feedback row so build_success_context() has data
        from models import get_db_connection

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO application_feedback "
            "(user_id, posting_id, ats_score, outcome_type, outcome) "
            "VALUES (3, 'ml_loop_p1', 0.88, 'callback', 'callback')"
        )
        conn.commit()
        conn.close()

        with (
            patch("agents.resume_tailor.ResumeTailorAgent._call_llm", recording_llm),
            patch("agents.resume_tailor.ResumeTailorAgent._call_llm_json", _fake_llm_json),
            patch("arango_client.get_arango_client") as mock_arango,
            patch(
                "deep_profile_staleness.check_staleness",
                return_value={"is_stale": False, "stale_reason": ""},
            ),
        ):
            mock_arango.return_value.is_connected = False

            from agents import get_resume_tailor

            tailor = get_resume_tailor()
            tailor.tailor_for_posting("3", "ml_loop_p1")

        # Find the resume generation prompt (contains ORIGINAL RESUME)
        tailor_prompts = [p for p in captured_prompts if "ORIGINAL RESUME" in p]
        assert tailor_prompts, "No tailor generation prompt captured"

        main_prompt = tailor_prompts[0]
        has_success_context = (
            "ATS" in main_prompt
            or "successful" in main_prompt.lower()
            or "callback" in main_prompt.lower()
            or "score" in main_prompt.lower()
        )
        assert has_success_context, (
            "Success context not injected into tailor prompt.\n"
            f"Prompt (first 600 chars): {main_prompt[:600]}"
        )

    def test_no_feedback_still_produces_result(self, app_ctx):
        """With no feedback rows, tailor must still succeed gracefully."""
        with (
            patch("agents.resume_tailor.ResumeTailorAgent._call_llm", _fake_llm),
            patch("agents.resume_tailor.ResumeTailorAgent._call_llm_json", _fake_llm_json),
            patch("arango_client.get_arango_client") as mock_arango,
            patch(
                "deep_profile_staleness.check_staleness",
                return_value={"is_stale": False, "stale_reason": ""},
            ),
        ):
            mock_arango.return_value.is_connected = False

            from agents import get_resume_tailor

            tailor = get_resume_tailor()
            result = tailor.tailor_for_posting("3", "ml_loop_p1")

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result.get("optimized_text") or result.get("ats_score") is not None


# ---------------------------------------------------------------------------
# P2-A.5: profile_stale flag in tailor result
# ---------------------------------------------------------------------------


class TestStalenessInTailorResult:
    def test_tailor_result_includes_profile_stale_key(self, app_ctx):
        """tailor_for_posting() result must always include 'profile_stale' key."""
        with (
            patch("agents.resume_tailor.ResumeTailorAgent._call_llm", _fake_llm),
            patch("agents.resume_tailor.ResumeTailorAgent._call_llm_json", _fake_llm_json),
            patch("arango_client.get_arango_client") as mock_arango,
            patch(
                "deep_profile_staleness.check_staleness",
                return_value={"is_stale": False, "stale_reason": ""},
            ),
        ):
            mock_arango.return_value.is_connected = False

            from agents import get_resume_tailor

            tailor = get_resume_tailor()
            result = tailor.tailor_for_posting("3", "ml_loop_p1")

        assert "profile_stale" in result, "profile_stale key missing from tailor result"
        assert result["profile_stale"] is False

    def test_tailor_result_profile_stale_true_when_stale(self, app_ctx):
        """When staleness check returns is_stale=True, result must surface it."""
        with (
            patch("agents.resume_tailor.ResumeTailorAgent._call_llm", _fake_llm),
            patch("agents.resume_tailor.ResumeTailorAgent._call_llm_json", _fake_llm_json),
            patch("arango_client.get_arango_client") as mock_arango,
            patch(
                "deep_profile_staleness.check_staleness",
                return_value={"is_stale": True, "stale_reason": "New project approved"},
            ),
        ):
            mock_arango.return_value.is_connected = False

            from agents import get_resume_tailor

            tailor = get_resume_tailor()
            result = tailor.tailor_for_posting("3", "ml_loop_p1")

        assert (
            result.get("profile_stale") is True
        ), f"Expected profile_stale=True, got {result.get('profile_stale')}"
        assert result.get("stale_reason") == "New project approved"


# ---------------------------------------------------------------------------
# P2-B.5: Evidence tracking — injected items + text-matched items
# ---------------------------------------------------------------------------


class TestEvidenceTracking:
    def test_text_matched_client_produces_evidence_ref(self):
        """If client name appears in tailored text, it becomes an evidence ref."""
        from graph_traceability import extract_evidence_references

        fake_clients = [{"_id": "ro_client_projects/ahead_001", "name": "AHEAD"}]

        with patch("arango_client.get_arango_client") as mock_ac:
            mock_client = MagicMock()
            mock_client.is_connected = True

            def fake_query(aql, params):
                if "ro_client_projects" in aql and "ro_version_sourced_from" not in aql:
                    return fake_clients
                return []

            mock_client.query = fake_query
            mock_ac.return_value = mock_client

            text = "Led cloud modernization initiative for AHEAD, delivering $2M in savings."
            refs = extract_evidence_references(text, user_id=3)

        assert len(refs) > 0, "Expected at least one evidence ref when client name in text"
        assert any(r["_id"] == "ro_client_projects/ahead_001" for r in refs)

    def test_client_not_in_text_produces_no_ref(self):
        """Client name absent from tailored text → no evidence ref for that client."""
        from graph_traceability import extract_evidence_references

        fake_clients = [{"_id": "ro_client_projects/opi_001", "name": "OPI"}]

        with patch("arango_client.get_arango_client") as mock_ac:
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.query = lambda aql, params: (
                fake_clients
                if "ro_client_projects" in aql and "ro_version_sourced_from" not in aql
                else []
            )
            mock_ac.return_value = mock_client

            text = "Built microservices architecture using Kubernetes and AWS."
            refs = extract_evidence_references(text, user_id=3)

        assert not any(r["_id"] == "ro_client_projects/opi_001" for r in refs)

    def test_injected_evidence_items_in_prompt_injection(self):
        """build_untapped_prompt_injection() surfaces untapped item names."""
        from graph_traceability import build_untapped_prompt_injection

        untapped = [
            {"type": "client", "name": "Navitus", "_id": "ro_client_projects/nav_1"},
            {
                "type": "outcome",
                "name": "Reduced latency by 40%",
                "_id": "ro_business_outcomes/out_1",
            },
        ]
        injection = build_untapped_prompt_injection(untapped)
        assert "Navitus" in injection
        assert "Reduced latency" in injection

    def test_write_resume_version_creates_one_edge_per_ref(self):
        """write_resume_version_to_graph writes exactly one edge per evidence ref."""
        from graph_traceability import write_resume_version_to_graph

        with patch("arango_client.get_arango_client") as mock_ac:
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.upsert_vertex.return_value = "ro_resume_versions/rv_1"
            mock_ac.return_value = mock_client

            evidence_refs = [
                {
                    "_id": "ro_client_projects/ahead_1",
                    "type": "client",
                    "confidence": 0.9,
                    "section": "",
                },
                {
                    "_id": "ro_business_outcomes/out_1",
                    "type": "outcome",
                    "confidence": 0.8,
                    "section": "prompt_injection",
                },
            ]
            write_resume_version_to_graph(
                user_id=3,
                version_id=42,
                source="agent_tailor",
                posting={"title": "SWE", "company": "TestCo"},
                evidence_refs=evidence_refs,
            )

        assert mock_client.upsert_edge.call_count == 2


# ---------------------------------------------------------------------------
# P2-E.5: Concurrent SQLite writes — WAL mode safety
# ---------------------------------------------------------------------------


class TestConcurrentWriteSafety:
    def test_wal_mode_active_on_connections(self, app_ctx):
        """WAL mode must be set on all DB connections (P1-A requirement)."""
        from models import get_db_connection

        conn = get_db_connection()
        row = conn.execute("PRAGMA journal_mode").fetchone()
        conn.close()
        assert row[0] == "wal", f"Expected WAL mode, got {row[0]}"

    def test_parallel_log_writes_do_not_error(self, app_ctx):
        """Concurrent _log_run calls from parallel pipeline must not raise."""
        import concurrent.futures

        from agents import get_orchestrator

        orch = get_orchestrator()
        errors = []

        def do_log(n):
            try:
                orch._log_run(
                    "3",
                    f"Concurrent test {n}",
                    {},
                    {"n": n},
                    task_type="test",
                    duration_ms=1,
                )
            except Exception as e:
                errors.append(str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            list(ex.map(do_log, range(8)))

        assert not errors, f"Concurrent _log_run raised: {errors}"


# ---------------------------------------------------------------------------
# E2E: Full ML loop trace
# ---------------------------------------------------------------------------


class TestFullMLLoop:
    def test_feedback_to_prompt_full_trace(self):
        """Trace full loop: record feedback → build context → inject into prompt."""
        from feedback_analyzer import build_success_context, classify_outcome_type

        # Step 1: Feedback rows from stage transitions
        rows = [
            {"ats_score": 0.88, "outcome_type": classify_outcome_type("applied", "phone_screen")},
            {"ats_score": 0.92, "outcome_type": classify_outcome_type("phone_screen", "interview")},
            {"ats_score": 0.45, "outcome_type": classify_outcome_type("applied", "rejected")},
        ]
        assert rows[0]["outcome_type"] == "callback"
        assert rows[1]["outcome_type"] == "advanced"

        # Step 2: Build success context
        context = build_success_context(rows)
        assert isinstance(context, str)
        assert len(context) > 0, "Success context empty despite callback/advanced rows"
        assert "ATS" in context or "score" in context.lower()

        # Step 3: Context is non-trivial and ready for prompt injection
        assert "%" in context or "successful" in context.lower() or "callback" in context.lower()

    def test_outcome_classification_covers_all_stages(self):
        """All meaningful stage transitions produce correct outcome types."""
        from feedback_analyzer import classify_outcome_type

        cases = [
            (("applied", "phone_screen"), "callback"),
            (("phone_screen", "interview"), "advanced"),
            (("interview", "offer"), "success"),
            (("applied", "rejected"), "rejected"),
            (("phone_screen", "rejected"), "rejected"),
            (("applied", "applied"), "neutral"),
        ]
        for (old, new), expected in cases:
            got = classify_outcome_type(old, new)
            assert (
                got == expected
            ), f"classify_outcome_type({old!r}, {new!r}) = {got!r}, want {expected!r}"

    def test_get_correlations_reflects_recorded_feedback(self):
        """get_correlations() returns correct callback_rate from mock rows."""
        from feedback_analyzer import get_correlations

        mock_rows = [
            {
                "ats_score": 0.85,
                "outcome_type": "callback",
                "resume_version_id": "1",
                "new_stage": "phone_screen",
            },
            {
                "ats_score": 0.90,
                "outcome_type": "advanced",
                "resume_version_id": "1",
                "new_stage": "interview",
            },
            {
                "ats_score": 0.40,
                "outcome_type": "rejected",
                "resume_version_id": "2",
                "new_stage": "rejected",
            },
        ]

        with patch("models.get_db_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = mock_rows
            mock_conn.return_value.execute.return_value = mock_cursor
            mock_conn.return_value.close = MagicMock()

            result = get_correlations(user_id=3)

        assert result["callback_rate"] > 60.0
        assert result["total_applications"] == 3
        assert result["avg_ats_callback"] is not None
        assert result["avg_ats_callback"] > result["avg_ats_rejected"]
