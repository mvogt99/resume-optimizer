"""Phase 3: Mutation-verified tests for significance scoring.

TDD Contract:
- test_feat_commit_scores_3: feat commits score 3 (1 baseline + 2 bonus)
- test_docs_commit_scores_1: docs commits score 1 (baseline, no bonus)
- test_governance_scores_high: governance achievements score 3+ (baseline + 2 bonus)
- test_max_score_capped_at_5: score is never > 5
- test_classify_feat_is_achievement: feat commits classify as 'achievement'
- test_classify_fix_is_fix: fix commits classify as 'fix'
"""

import json
import sqlite3
import tempfile

import pytest

from journey_scorer import score_event, classify_event


class TestScoreEventFeatCommit:
    """Mutation: Change feat commit bonus from +2 to +0."""

    def test_feat_commit_scores_3(self):
        """Verify: feat commits score 3 (baseline 1 + feat bonus 2)."""
        source = {
            "source_type": "git_commit",
            "title": "feat(phase1): Add watermark tracking",
            "full_text": "Implement watermark system for incremental mining",
            "classification": ""
        }
        event = {"technologies": ["Python", "SQLite"]}

        score = score_event(source, event)

        # ASSERTION: Must be 3 (baseline 1 + feat +2)
        assert score == 3

    def test_feat_commit_with_completion_keyword(self):
        """Verify: feat + completion keyword scores 4."""
        source = {
            "source_type": "git_commit",
            "title": "feat(auth): Implement JWT authentication",
            "full_text": "Deployed authentication system to production",
            "classification": ""
        }
        event = {"technologies": []}

        score = score_event(source, event)

        # ASSERTION: 1 (baseline) + 2 (feat) + 1 (deployed) = 4
        assert score == 4


class TestScoreEventDocsCommit:
    """Mutation: Change docs commit bonus from +0 to +2."""

    def test_docs_commit_scores_1(self):
        """Verify: docs commits score 1 (baseline, no bonus)."""
        source = {
            "source_type": "git_commit",
            "title": "docs: Update API documentation",
            "full_text": "Added docs for new endpoints",
            "classification": ""
        }
        event = {"technologies": []}

        score = score_event(source, event)

        # ASSERTION: Must be 1 (baseline, docs get no bonus)
        assert score == 1

    def test_chore_commit_scores_1(self):
        """Verify: chore commits score 1."""
        source = {
            "source_type": "git_commit",
            "title": "chore: Update dependencies",
            "full_text": "Bump package versions",
            "classification": ""
        }
        event = {"technologies": []}

        score = score_event(source, event)

        assert score == 1


class TestScoreEventGovernance:
    """Mutation: Remove governance bonus (+2)."""

    def test_governance_scores_high(self):
        """Verify: governance achievements score 3+ (baseline 1 + governance +2)."""
        source = {
            "source_type": "governance",
            "title": "Security audit passed",
            "full_text": "Completed GDPR compliance review",
            "classification": ""
        }
        event = {"technologies": []}

        score = score_event(source, event)

        # ASSERTION: Must be at least 3 (1 baseline + 2 governance)
        assert score >= 3

    def test_governance_with_impact_keyword(self):
        """Verify: governance + impact keyword scores higher."""
        source = {
            "source_type": "governance",
            "title": "Milestone: First production deployment",
            "full_text": "Critical security review completed",
            "classification": ""
        }
        event = {"technologies": []}

        score = score_event(source, event)

        # ASSERTION: 1 (baseline) + 2 (governance) + 1 (critical) = 4
        assert score >= 4


class TestScoreEventMaxCap:
    """Mutation: Remove `min(score, 5)` capping."""

    def test_max_score_capped_at_5(self):
        """Verify: No event scores > 5."""
        source = {
            "source_type": "governance",
            "title": "CRITICAL BREAKTHROUGH MILESTONE",
            "full_text": (
                "First time deploying production shipped critical system "
                "launched breakthrough milestone"
            ),
            "classification": "report"
        }
        event = {"technologies": ["Python", "Go", "Rust", "Java", "C++"]}

        score = score_event(source, event)

        # ASSERTION: Must be capped at 5 regardless of bonuses
        assert score == 5

    def test_min_score_is_1(self):
        """Verify: All events score at least 1."""
        source = {
            "source_type": "unknown",
            "title": "Random file",
            "full_text": "",
            "classification": ""
        }
        event = {"technologies": []}

        score = score_event(source, event)

        # ASSERTION: Must be at least 1
        assert score >= 1


class TestClassifyEventFeat:
    """Mutation: Return "development" for feat commits instead of "achievement"."""

    def test_classify_feat_is_achievement(self):
        """Verify: feat commits classify as 'achievement'."""
        source = {
            "source_type": "git_commit",
            "title": "feat(auth): Add JWT",
            "classification": ""
        }

        classification = classify_event(source)

        # ASSERTION: Must be 'achievement'
        assert classification == "achievement"

    def test_classify_fix_is_fix(self):
        """Verify: fix commits classify as 'fix'."""
        source = {
            "source_type": "git_commit",
            "title": "fix(bug): Resolve auth token leak",
            "classification": ""
        }

        classification = classify_event(source)

        # ASSERTION: Must be 'fix'
        assert classification == "fix"

    def test_classify_test_is_development(self):
        """Verify: test commits classify as 'development'."""
        source = {
            "source_type": "git_commit",
            "title": "test(auth): Add token validation tests",
            "classification": ""
        }

        classification = classify_event(source)

        # ASSERTION: Must be 'development'
        assert classification == "development"


class TestClassifyEventGovernance:
    """Verify governance events classify correctly."""

    def test_classify_governance(self):
        """Verify: governance source_type classifies as 'governance'."""
        source = {
            "source_type": "governance",
            "title": "Security audit",
            "classification": ""
        }

        classification = classify_event(source)

        # ASSERTION: Must be 'governance'
        assert classification == "governance"


class TestClassifyEventLearning:
    """Verify learning/teaching events classify correctly."""

    def test_classify_teaching_is_learning(self):
        """Verify: classification='teaching' → 'learning'."""
        source = {
            "source_type": "file",
            "title": "Teaching doc",
            "classification": "teaching"
        }

        classification = classify_event(source)

        assert classification == "learning"

    def test_classify_report_is_milestone(self):
        """Verify: classification='report' → 'milestone'."""
        source = {
            "source_type": "file",
            "title": "Project report",
            "classification": "report"
        }

        classification = classify_event(source)

        assert classification == "milestone"


class TestTechBreadthBonus:
    """Verify technology breadth bonus (+1 for 5+ techs)."""

    def test_tech_breadth_bonus(self):
        """Verify: 5+ technologies grant +1 to score."""
        source = {
            "source_type": "git_commit",
            "title": "chore: Update deps",
            "full_text": "Updated all dependencies",
            "classification": ""
        }
        event = {
            "technologies": ["Python", "Go", "Rust", "Java", "C++", "JavaScript"]
        }

        score = score_event(source, event)

        # ASSERTION: baseline (1) + tech breadth (1) = 2
        assert score >= 2

    def test_no_tech_breadth_under_5(self):
        """Verify: < 5 technologies get no breadth bonus."""
        source = {
            "source_type": "git_commit",
            "title": "chore: Update deps",
            "full_text": "",
            "classification": ""
        }
        event = {"technologies": ["Python", "Go", "Rust"]}

        score = score_event(source, event)

        # ASSERTION: baseline (1), no tech bonus
        assert score == 1
