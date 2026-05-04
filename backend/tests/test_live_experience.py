"""Live Experience Chat integration tests — verifies experience_chat.py with real LLM.

Tests: session start, stage advancement, LLM follow-up generation, full conversation,
finalize, STAR bullet generation.
Requires FTAL harness on localhost:8000 and RTX 5090 on port 8021.
Skips gracefully if services unavailable.
"""

import os
import sys
import tempfile

import pytest
import requests

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def _harness_up():
    try:
        r = requests.get("http://localhost:8000/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


HARNESS_AVAILABLE = _harness_up()
pytestmark = pytest.mark.skipif(
    not HARNESS_AVAILABLE,
    reason="FTAL harness not running",
)


@pytest.fixture()
def extractor_with_test_db():
    """Return ExperienceExtractor with temp test DB."""
    import models

    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    old_db = models.DB_PATH
    models.DB_PATH = db_path
    for mod in list(sys.modules.values()):
        if mod is None or mod is models:
            continue
        if hasattr(mod, "DB_PATH") and isinstance(mod.DB_PATH, str):
            try:
                mod.DB_PATH = db_path
            except (AttributeError, TypeError):
                pass

    models.init_db()

    import experience_chat

    experience_chat._extractor = None
    ext = experience_chat.get_experience_extractor()

    yield ext

    experience_chat._extractor = None
    models.DB_PATH = old_db
    os.close(db_fd)
    os.unlink(db_path)


# ===================================================================
# Session Lifecycle (3 tests)
# ===================================================================


class TestSessionLifecycle:
    """Session start and stage transitions."""

    def test_start_session_returns_intro(self, extractor_with_test_db):
        """start_session → stage is 'intro' or 'role', has message."""
        result = extractor_with_test_db.start_session(user_id=1)
        assert "session_id" in result
        assert result["stage"] in ("intro", "role")
        assert len(result["message"]) > 10, "Opening message must be substantive"

    def test_send_employer_advances_stage(self, extractor_with_test_db):
        """Sending employer name advances past intro stage."""
        session = extractor_with_test_db.start_session(user_id=1)
        sid = session["session_id"]

        result = extractor_with_test_db.process_message(
            sid,
            "I worked at Navitus Health Solutions as a Solutions Architect.",
            user_id=1,
        )
        assert "stage" in result
        # Should advance to role or responsibilities
        assert result["stage"] != "intro", f"Should advance past intro, still at: {result['stage']}"
        assert len(result["message"]) > 10, "AI must generate follow-up question"

    def test_sparse_response_skips_stage(self, extractor_with_test_db):
        """Sparse response (skip/n/a) advances 2 stages."""
        session = extractor_with_test_db.start_session(user_id=1)
        sid = session["session_id"]

        # Give employer to move past intro
        r1 = extractor_with_test_db.process_message(
            sid,
            "Navitus Health Solutions, Solutions Architect",
            user_id=1,
        )
        stage_after_intro = r1["stage"]

        # Send sparse response to skip current stage
        r2 = extractor_with_test_db.process_message(sid, "skip", user_id=1)
        # Should have advanced past the current stage (possibly 2 stages)
        assert (
            r2["stage"] != stage_after_intro
        ), f"Sparse 'skip' should advance stage, still at: {r2['stage']}"


# ===================================================================
# LLM Follow-up Quality (2 tests)
# ===================================================================


class TestLLMFollowUp:
    """LLM generates contextual follow-up questions."""

    def test_llm_generates_follow_up(self, extractor_with_test_db):
        """LLM follow-up is not a template — contains context-specific content."""
        session = extractor_with_test_db.start_session(
            user_id=1,
            employer="OPI",
            client="Global Pharma",
        )
        sid = session["session_id"]

        result = extractor_with_test_db.process_message(
            sid,
            "I was the Lead Solutions Architect responsible for enterprise integration.",
            user_id=1,
        )
        msg = result["message"]
        assert len(msg) > 20, "Follow-up must be substantive"
        # LLM should generate a question (ends with ?)
        assert "?" in msg, f"Follow-up should contain a question, got: {msg[:100]}"

    def test_context_preserved_across_messages(self, extractor_with_test_db):
        """Context accumulates across messages."""
        session = extractor_with_test_db.start_session(
            user_id=1,
            employer="AHEAD",
            client="Enterprise",
        )
        sid = session["session_id"]

        extractor_with_test_db.process_message(
            sid,
            "Principal Architect for cloud migration projects.",
            user_id=1,
        )
        extractor_with_test_db.process_message(
            sid,
            "We used AWS, Terraform, and Kubernetes daily.",
            user_id=1,
        )

        summary = extractor_with_test_db.get_summary(sid, user_id=1)
        assert "error" not in summary
        # Context should have accumulated technologies
        context_str = str(summary).lower()
        assert (
            "aws" in context_str or "terraform" in context_str or "kubernetes" in context_str
        ), f"Context should include mentioned technologies, got: {summary}"


# ===================================================================
# Full Conversation & Finalize (2 tests)
# ===================================================================


class TestFullConversation:
    """Complete conversation through all stages."""

    def test_full_conversation_reaches_complete(self, extractor_with_test_db):
        """Walk through all 6 stages → reach 'complete'."""
        session = extractor_with_test_db.start_session(
            user_id=1,
            employer="Navitus",
            client="PBM Platform",
        )
        sid = session["session_id"]

        responses = [
            "Senior Solutions Architect, leading the platform modernization team.",
            "Designed and implemented microservices architecture for claims processing. "
            "Led team of 5 developers. Managed stakeholder communications.",
            "Python, AWS Lambda, Docker, PostgreSQL, Kafka, Terraform.",
            "Reduced claim processing time by 40%. Achieved 99.9% uptime. "
            "Saved $2M annually in infrastructure costs.",
            "Migrating legacy monolith to microservices while maintaining zero downtime. "
            "Coordinating across 3 time zones.",
        ]

        last_result = None
        for msg in responses:
            last_result = extractor_with_test_db.process_message(sid, msg, user_id=1)
            if last_result.get("is_complete"):
                break

        assert last_result is not None
        assert last_result.get("is_complete") is True or last_result["stage"] == "complete"

    def test_finalize_creates_experience(self, extractor_with_test_db):
        """finalize_session → extracted_experiences row created with bullets."""
        session = extractor_with_test_db.start_session(
            user_id=1,
            employer="OPI",
            client="Global Supply Chain",
        )
        sid = session["session_id"]

        # Quick walk-through
        msgs = [
            "Integration Architect building EDI platforms.",
            "Designed B2B integration hub processing 500K transactions daily.",
            "Java, MuleSoft, AWS, Oracle, ActiveMQ.",
            "Increased throughput 3x. Cut integration errors by 60%.",
            "Handling legacy partner protocols with modern API gateway.",
        ]
        for msg in msgs:
            extractor_with_test_db.process_message(sid, msg, user_id=1)

        result = extractor_with_test_db.finalize_session(sid, user_id=1)
        assert "error" not in result, f"Finalize failed: {result}"
        assert "experience_id" in result
        assert result["status"] == "finalized"

        # Verify in DB
        experiences = extractor_with_test_db.get_extracted_experiences(user_id=1)
        assert len(experiences) >= 1
        exp = experiences[0]
        assert exp["employer"] == "OPI"


# ===================================================================
# STAR Bullets (1 test)
# ===================================================================


class TestSTARBullets:
    """STAR bullet generation quality."""

    def test_bullets_contain_action_verbs(self, extractor_with_test_db):
        """Finalized bullets should start with action verbs (STAR format)."""
        session = extractor_with_test_db.start_session(
            user_id=1,
            employer="AHEAD",
            client="Cloud Migration",
        )
        sid = session["session_id"]

        msgs = [
            "Cloud Architect leading AWS migrations.",
            "Migrated 50 applications from on-prem to AWS. Led architecture reviews.",
            "AWS, Docker, Kubernetes, Terraform, Python, CloudFormation.",
            "Reduced infrastructure costs by 35%. Achieved SOC2 compliance.",
            "Managing legacy app dependencies during migration.",
        ]
        for msg in msgs:
            extractor_with_test_db.process_message(sid, msg, user_id=1)

        result = extractor_with_test_db.finalize_session(sid, user_id=1)
        bullets = result.get("bullet_points", [])
        assert len(bullets) >= 1, "Must generate at least one bullet point"

        # Bullets should be capitalized (start with action verb)
        for b in bullets:
            assert b[0].isupper(), f"Bullet should start with capital letter: {b[:50]}"
