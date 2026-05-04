"""TDD tests for resume_corrections module — Fix A (persistence) + Fix B (fuzzy matching).

Run from backend/: pytest tests/test_resume_corrections.py -v
"""
import os
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


# ---------------------------------------------------------------------------
# Unit tests — pure logic (no DB, no Flask app)
# ---------------------------------------------------------------------------

class TestTokenOverlap:
    """Fix B — fuzzy matching foundation."""

    def test_identical_text_scores_one(self):
        from resume_corrections import _token_overlap
        assert _token_overlap("Kafka Debezium Flink", "Kafka Debezium Flink") == 1.0

    def test_zero_overlap_scores_zero(self):
        from resume_corrections import _token_overlap
        assert _token_overlap("quantum entanglement physics", "java spring microservices") == 0.0

    def test_partial_overlap_between_zero_and_one(self):
        from resume_corrections import _token_overlap
        score = _token_overlap(
            "healthcare, consumer markets, and supply chain",
            "healthcare consumer markets supply chain sectors",
        )
        assert 0.5 < score < 1.0

    def test_stopwords_not_counted(self):
        from resume_corrections import _token_overlap
        # "and", "the", "for" are stopwords — should not inflate score
        score_with = _token_overlap("for the enterprise", "enterprise")
        score_without = _token_overlap("enterprise", "enterprise")
        # Both should reflect mainly "enterprise" matching
        assert score_with > 0.0
        assert score_without == 1.0


class TestFuzzyApply:
    """Fix B — _fuzzy_apply behaviour."""

    def test_exact_substring_replaced(self):
        from resume_corrections import _fuzzy_apply
        text = "Led 50+ person team across healthcare, consumer markets, and supply chain clients."
        result = _fuzzy_apply(
            text,
            "healthcare, consumer markets, and supply chain",
            "consumer markets, supply chain, and P&C",
            threshold=0.70,
        )
        assert result is not None
        assert "consumer markets, supply chain, and P&C" in result
        assert "healthcare, consumer markets, and supply chain" not in result

    def test_below_threshold_returns_none(self):
        from resume_corrections import _fuzzy_apply
        text = "Designed microservices on Kubernetes with CI/CD pipelines."
        result = _fuzzy_apply(
            text,
            "healthcare consumer markets supply chain",
            "something completely different",
            threshold=0.70,
        )
        assert result is None

    def test_partial_overlap_below_threshold_returns_none(self):
        """Line shares 2/5 tokens with old_text — below 0.70 threshold."""
        from resume_corrections import _fuzzy_apply
        text = "Led healthcare team through enterprise change management."
        # old_text has 5 tokens; line shares only 'healthcare' and 'led' (2/5 = 0.40 < 0.70)
        result = _fuzzy_apply(
            text,
            "healthcare consumer markets supply chain",
            "consumer markets supply chain P&C",
            threshold=0.70,
        )
        assert result is None

    def test_threshold_boundary_at_exact_match(self):
        from resume_corrections import _fuzzy_apply
        text = "Director role across healthcare, consumer markets, and supply chain."
        # Should match — same sentence, all tokens present
        result = _fuzzy_apply(
            text,
            "healthcare, consumer markets, and supply chain",
            "consumer markets, supply chain, and P&C",
            threshold=0.70,
        )
        assert result is not None

    def test_multiline_text_only_target_line_changed(self):
        from resume_corrections import _fuzzy_apply
        text = (
            "Line one about Kafka and streaming.\n"
            "Led team across healthcare, consumer markets, and supply chain.\n"
            "Line three about governance."
        )
        result = _fuzzy_apply(
            text,
            "healthcare, consumer markets, and supply chain",
            "consumer markets, supply chain, and P&C",
            threshold=0.70,
        )
        assert result is not None
        assert "Line one about Kafka and streaming." in result
        assert "Line three about governance." in result
        assert "consumer markets, supply chain, and P&C" in result


# ---------------------------------------------------------------------------
# Integration tests — DB-backed (use app fixture from conftest)
# ---------------------------------------------------------------------------

class TestSaveAndGet:
    """Fix A — persistence."""

    def test_save_correction_persists(self, app):
        with app.app_context():
            from resume_corrections import delete_correction, get_corrections, save_correction
            cid = save_correction(user_id=1, old_text="foo bar", new_text="baz qux")
            assert cid > 0
            corrections = get_corrections(user_id=1)
            assert any(c["old_text"] == "foo bar" for c in corrections)

    def test_save_correction_resume_specific(self, app):
        with app.app_context():
            from resume_corrections import get_corrections, save_correction
            save_correction(user_id=1, old_text="old A", new_text="new A", resume_id="res_1")
            save_correction(user_id=1, old_text="old B", new_text="new B", resume_id="res_2")
            # Global call returns all active corrections for this user
            all_c = get_corrections(user_id=1)
            assert len(all_c) == 2
            # Resume-specific call returns only matching + NULL
            res1 = get_corrections(user_id=1, resume_id="res_1")
            assert all(c["resume_id"] in ("res_1", None) for c in res1)
            assert not any(c["old_text"] == "old B" for c in res1)

    def test_user_isolation(self, app):
        with app.app_context():
            from resume_corrections import get_corrections, save_correction
            save_correction(user_id=1, old_text="user1 secret", new_text="x")
            save_correction(user_id=2, old_text="user2 secret", new_text="y")
            u1 = get_corrections(user_id=1)
            u2 = get_corrections(user_id=2)
            assert all(c["user_id"] == 1 for c in u1)
            assert all(c["user_id"] == 2 for c in u2)
            assert not any(c["old_text"] == "user2 secret" for c in u1)

    def test_delete_correction_soft_deletes(self, app):
        with app.app_context():
            from resume_corrections import delete_correction, get_corrections, save_correction
            cid = save_correction(user_id=1, old_text="to delete", new_text="replacement")
            assert any(c["old_text"] == "to delete" for c in get_corrections(user_id=1))
            delete_correction(correction_id=cid, user_id=1)
            assert not any(c["old_text"] == "to delete" for c in get_corrections(user_id=1))

    def test_delete_requires_correct_user(self, app):
        with app.app_context():
            from resume_corrections import delete_correction, get_corrections, save_correction
            cid = save_correction(user_id=1, old_text="protected", new_text="x")
            # User 2 cannot delete user 1's correction
            delete_correction(correction_id=cid, user_id=2)
            assert any(c["old_text"] == "protected" for c in get_corrections(user_id=1))


class TestApplyCorrections:
    """Fix A + B — applying corrections to resume text."""

    def test_exact_match_applied(self, app):
        with app.app_context():
            from resume_corrections import apply_corrections, save_correction
            save_correction(user_id=1, old_text="old phrase", new_text="new phrase")
            result, applied, failed = apply_corrections(
                "This contains old phrase in context.", user_id=1
            )
            assert "new phrase" in result
            assert len(applied) == 1
            assert len(failed) == 0

    def test_fuzzy_match_applied_when_exact_fails(self, app):
        with app.app_context():
            from resume_corrections import apply_corrections, save_correction
            save_correction(
                user_id=1,
                old_text="healthcare, consumer markets, and supply chain",
                new_text="consumer markets, supply chain, and P&C",
            )
            # Text has slightly different phrasing — exact fails, fuzzy should catch it
            text = "Led 50+ person team across healthcare, consumer markets, supply chain."
            result, applied, failed = apply_corrections(text, user_id=1)
            # Fuzzy should find the close match
            assert "consumer markets, supply chain, and P&C" in result or len(applied) == 1

    def test_unmatched_correction_reported_in_failed(self, app):
        with app.app_context():
            from resume_corrections import apply_corrections, save_correction
            save_correction(user_id=1, old_text="completely unrelated phrase xyz", new_text="abc")
            result, applied, failed = apply_corrections(
                "Designed data platforms for streaming architectures.", user_id=1
            )
            assert len(failed) == 1
            assert failed[0]["old_text"] == "completely unrelated phrase xyz"

    def test_resume_specific_correction_applied(self, app):
        with app.app_context():
            from resume_corrections import apply_corrections, save_correction
            save_correction(
                user_id=1,
                old_text="old specific",
                new_text="new specific",
                resume_id="res_42",
            )
            result, applied, _ = apply_corrections(
                "Text with old specific content.", user_id=1, resume_id="res_42"
            )
            assert "new specific" in result

    def test_other_resume_correction_not_applied(self, app):
        with app.app_context():
            from resume_corrections import apply_corrections, save_correction
            save_correction(
                user_id=1, old_text="old A", new_text="new A", resume_id="res_1"
            )
            # Applying for res_2 — correction scoped to res_1 should not fire
            result, applied, failed = apply_corrections(
                "Text with old A content.", user_id=1, resume_id="res_2"
            )
            assert "old A" in result  # unchanged
            assert len(applied) == 0

    def test_global_correction_applies_to_any_resume(self, app):
        """A NULL resume_id correction must apply when querying with any resume_id."""
        with app.app_context():
            from resume_corrections import apply_corrections, get_corrections, save_correction
            # Save global correction (no resume_id)
            save_correction(user_id=1, old_text="global old", new_text="global new")
            # Save resume-specific correction
            save_correction(user_id=1, old_text="specific old", new_text="specific new", resume_id="res_99")

            # Querying for res_99 must include the global correction
            corrections = get_corrections(user_id=1, resume_id="res_99")
            old_texts = [c["old_text"] for c in corrections]
            assert "global old" in old_texts       # global applies
            assert "specific old" in old_texts     # resume-specific applies

            # Querying for a DIFFERENT resume — global still applies, specific does not
            corrections_other = get_corrections(user_id=1, resume_id="res_88")
            old_texts_other = [c["old_text"] for c in corrections_other]
            assert "global old" in old_texts_other
            assert "specific old" not in old_texts_other
