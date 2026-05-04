"""Tests for equivalency-aware scoring in resume_scorer.score_resume.

Mutation targets:
  ES1: equivalency phrase in resume text moves missing keyword to matching
  ES2: not_applicable status keywords removed from missing (not added to matching)
  ES3: equivalency phrase in skills list expands virtual skill set
  ES4: no equivalencies provided → original scoring behaviour unchanged
  ES5: optimize_resume passes equivalencies through to score_resume
  ES6: score_text_endpoint uses user equivalencies (integration)
"""

from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Unit tests for resume_scorer.score_resume
# ---------------------------------------------------------------------------

_RESUME_TEXT = (
    "Professional Summary\n\n"
    "Senior architect with deep expertise in Apache Kafka and event streaming pipelines. "
    "Experience with Debezium CDC for change data capture and real-time data replication. "
    "Skills: Python, SQL, Kafka, Debezium, AWS, Docker.\n\n"
    "Experience\n\nBuilt distributed systems at scale.\n\n"
    "Education\n\nBS Computer Science."
)

_JOB_KEYWORDS = ["event streaming", "change data capture", "microservices", "kubernetes"]

_EQUIVALENCIES = [
    {"job_keyword": "event streaming", "equivalent_phrase": "kafka", "confidence": 0.9, "status": "equivalent"},
    {"job_keyword": "change data capture", "equivalent_phrase": "debezium", "confidence": 0.85, "status": "equivalent"},
    {"job_keyword": "employer insurance", "equivalent_phrase": "not_applicable", "confidence": 1.0, "status": "not_applicable"},
]


class TestEquivalencyScoring:
    def _call(self, equivalencies=None):
        from resume_scorer import score_resume
        resume_data = {"text": _RESUME_TEXT, "skills": ["Kafka", "Debezium", "Python"]}
        return score_resume(
            resume_data,
            _JOB_KEYWORDS,
            job_text=" ".join(_JOB_KEYWORDS),
            equivalencies=equivalencies,
        )

    # ES1: equivalency phrase found in resume text → keyword moves to matching
    def test_equiv_phrase_in_text_moves_keyword_to_matching(self):
        """'kafka' in resume → 'event streaming' no longer missing (ES1)."""
        result_without = self._call(equivalencies=None)
        result_with = self._call(equivalencies=_EQUIVALENCIES)

        # With equivalencies, 'event streaming' must be in matching
        assert "event streaming" in result_with["matching_keywords"], (
            "event streaming should be matched via kafka equivalency"
        )
        # And not in missing
        assert "event streaming" not in result_with["missing_keywords"]

    # ES2: not_applicable keyword removed from missing list
    def test_not_applicable_removed_from_missing(self):
        """status=not_applicable removes keyword from missing without adding to matching (ES2)."""
        equivs = [
            {"job_keyword": "employer insurance", "equivalent_phrase": "not_applicable",
             "confidence": 1.0, "status": "not_applicable"},
        ]
        from resume_scorer import score_resume
        resume_data = {"text": "Professional experience. Education. Skills. Summary.", "skills": []}
        result = score_resume(
            resume_data,
            ["employer insurance"],
            job_text="employer insurance",
            equivalencies=equivs,
        )
        assert "employer insurance" not in result["missing_keywords"]
        assert "employer insurance" not in result["matching_keywords"]

    # ES3: equivalent phrase in skills list expands virtual skill set
    def test_equiv_phrase_in_skills_boosts_skills_match(self):
        """Resume skill 'kafka' credited for job keyword 'event streaming' → skills score increases (ES3)."""
        result_without = self._call(equivalencies=None)
        result_with = self._call(equivalencies=_EQUIVALENCIES)
        assert result_with["score_breakdown"]["skills_match"] >= result_without["score_breakdown"]["skills_match"]

    # ES4: no equivalencies → baseline behaviour unchanged
    def test_no_equivalencies_baseline_unchanged(self):
        """Passing equivalencies=None keeps original scoring logic (ES4)."""
        from resume_scorer import score_resume
        resume_data = {"text": _RESUME_TEXT, "skills": ["Kafka"]}
        baseline = score_resume(resume_data, _JOB_KEYWORDS, job_text=" ".join(_JOB_KEYWORDS))
        with_none = score_resume(resume_data, _JOB_KEYWORDS, job_text=" ".join(_JOB_KEYWORDS), equivalencies=None)
        assert baseline["score"] == with_none["score"]

    # ES5: optimize_resume passes equivalencies to score_resume
    def test_optimize_resume_passes_equivalencies(self):
        """optimize_resume(equivalencies=...) propagates to score_resume (ES5)."""
        from utils import optimize_resume
        resume_data = {"text": _RESUME_TEXT, "skills": ["Kafka", "Debezium", "Python"]}
        with patch("utils.score_resume") as mock_score:
            mock_score.return_value = {
                "score": 70,
                "score_breakdown": {"keyword_coverage": 60, "semantic_similarity": 70,
                                    "skills_match": 80, "section_completeness": 75},
                "sections_found": {"skills": True, "experience": True, "education": True, "summary": False},
                "matching_keywords": ["kafka"],
                "missing_keywords": [],
                "skill_phrases_matched": [],
                "missing_skills": [],
            }
            optimize_resume(
                resume_data,
                _JOB_KEYWORDS,
                job_text="event streaming kafka",
                equivalencies=_EQUIVALENCIES,
            )
        call_kwargs = mock_score.call_args
        assert call_kwargs.kwargs.get("equivalencies") == _EQUIVALENCIES or (
            len(call_kwargs.args) > 4 and call_kwargs.args[4] == _EQUIVALENCIES
        )


class TestEquivScoringEndpoint:
    # ES6: score_text_endpoint loads user equivalencies
    def test_score_text_uses_equivalencies(self, client, auth_headers):
        """POST /api/resume/score-text loads user equivalencies and passes to scoring (ES6)."""
        with patch("keyword_equivalency.get_equivalencies", return_value=_EQUIVALENCIES) as mock_get_eq, \
             patch("resume_scorer.score_resume") as mock_score, \
             patch("nlp_engine.extract_skill_phrases", return_value=_JOB_KEYWORDS), \
             patch("nlp_engine.analyze_resume_vs_job", return_value={
                 "match_score": 60, "resume_keywords": [], "job_keywords": [],
                 "matching_keywords": [], "missing_keywords": [],
             }):
            mock_score.return_value = {
                "score": 75,
                "score_breakdown": {"keyword_coverage": 70, "semantic_similarity": 75,
                                    "skills_match": 80, "section_completeness": 100},
                "matching_keywords": ["kafka"],
                "missing_keywords": [],
                "skill_phrases_matched": [],
            }
            resp = client.post(
                "/api/resume/score-text",
                json={"text": _RESUME_TEXT, "job_description": "event streaming kafka"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        mock_get_eq.assert_called_once()
        call_kwargs = mock_score.call_args
        passed_equivs = call_kwargs.kwargs.get("equivalencies")
        assert passed_equivs == _EQUIVALENCIES
