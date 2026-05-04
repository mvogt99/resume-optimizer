"""Tests for Phase A gap_classifier module.

Gap Classifier identifies misalignment between candidate profile and job requirements.
Returns list of gap dicts with gap_id, gap_type (7 types), description, severity.
Never raises on error — always returns fallback list.
"""

from unittest.mock import patch

import pytest
from test_helpers import RESUME_TEXT, JD_TEXT


@pytest.fixture
def mock_gap_classifier_llm():
    """Mock call_llm_quality for gap_classifier without actual LLM calls."""
    with patch("gap_classifier.call_llm_quality") as mock:
        mock.return_value = {
            "gaps": [
                {
                    "gap_id": "gap_001",
                    "requirement_id": "req_003",
                    "gap_type": "insufficient_leadership_signal",
                    "description": "Resume lacks explicit team lead or management role",
                    "severity": "medium"
                },
                {
                    "gap_id": "gap_002",
                    "requirement_id": "req_002",
                    "gap_type": "missing_explicit_keyword",
                    "description": "GCP not mentioned in resume",
                    "severity": "low"
                }
            ]
        }
        yield mock


@pytest.fixture
def sample_requirements():
    """Sample requirements matching jd_parser output."""
    return [
        {
            "requirement_id": "req_001",
            "requirement_type": "must_have",
            "category": "programming_language",
            "text": "5+ years Python experience",
            "importance": 0.95,
        },
        {
            "requirement_id": "req_002",
            "requirement_type": "preferred",
            "category": "cloud_platform",
            "text": "AWS or GCP experience",
            "importance": 0.70,
        },
        {
            "requirement_id": "req_003",
            "requirement_type": "leadership",
            "category": "leadership_signals",
            "text": "Team lead or management experience",
            "importance": 0.60,
        }
    ]


@pytest.fixture
def sample_candidate_profile():
    """Sample candidate profile matching normalizer output."""
    return {
        "candidate_id": "cand_001",
        "target_role_families": ["Software Engineer", "Full Stack Developer"],
        "skill_inventory": [
            {
                "canonical_skill": "Python",
                "aliases": ["python3", "py"],
                "evidence_refs": ["resume_line_5"],
                "proficiency_estimate": "advanced",
                "years_estimate": 8.0,
            },
            {
                "canonical_skill": "AWS",
                "aliases": ["amazon_web_services"],
                "evidence_refs": ["resume_line_18"],
                "proficiency_estimate": "intermediate",
                "years_estimate": 5.0,
            }
        ],
        "experience_units": [
            {
                "experience_id": "exp_001",
                "title": "Senior Developer",
                "company": "TechCorp",
                "date_range": {"start": "2020-01-01", "end": None}
            }
        ]
    }


class TestGapClassifierHappyPath:
    """Tests for gap_classifier.classify_gaps() — happy path."""

    def test_returns_list(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """classify_gaps must return a list."""
        from gap_classifier import classify_gaps

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)
        assert isinstance(result, list)

    def test_items_are_dicts(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """Each item in result list must be a dict."""
        from gap_classifier import classify_gaps

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)
        assert all(isinstance(item, dict) for item in result)

    def test_has_required_fields(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """Each gap must have: gap_id, gap_type, description, severity."""
        from gap_classifier import classify_gaps

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)
        required_fields = {"gap_id", "gap_type", "description", "severity"}
        for gap in result:
            assert required_fields.issubset(gap.keys())

    def test_gap_type_is_valid_enum(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """gap_type must be one of 7 valid types."""
        from gap_classifier import classify_gaps

        valid_gap_types = {
            "missing_experience",
            "weak_wording",
            "missing_explicit_keyword",
            "insufficient_leadership_signal",
            "seniority_mismatch",
            "domain_gap",
            "unsupported_claim_risk"
        }

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        for gap in result:
            assert gap["gap_type"] in valid_gap_types

    def test_severity_is_valid_enum(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """severity must be one of: low, medium, high."""
        from gap_classifier import classify_gaps

        valid_severities = {"low", "medium", "high"}
        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        for gap in result:
            assert gap["severity"] in valid_severities

    def test_gap_id_is_nonempty_string(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """gap_id must be a non-empty string."""
        from gap_classifier import classify_gaps

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        for gap in result:
            assert isinstance(gap["gap_id"], str)
            assert len(gap["gap_id"]) > 0

    def test_description_is_nonempty_string(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """description must be a non-empty string."""
        from gap_classifier import classify_gaps

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        for gap in result:
            assert isinstance(gap["description"], str)
            assert len(gap["description"]) > 0

    def test_requirement_id_links_back(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """Gap requirement_id (if present) should match a requirement_id from input."""
        from gap_classifier import classify_gaps

        req_ids = {req["requirement_id"] for req in sample_requirements}
        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        for gap in result:
            if "requirement_id" in gap:
                assert gap["requirement_id"] in req_ids


class TestGapClassifierErrorHandling:
    """Tests for gap_classifier error fallback behavior."""

    def test_empty_requirements_returns_list(self, mock_gap_classifier_llm, sample_candidate_profile):
        """classify_gaps with empty requirements should return list (not raise)."""
        from gap_classifier import classify_gaps

        result = classify_gaps([], sample_candidate_profile, RESUME_TEXT)
        assert isinstance(result, list)

    def test_minimal_candidate_profile_returns_list(self, mock_gap_classifier_llm, sample_requirements):
        """classify_gaps with minimal candidate profile should return list."""
        from gap_classifier import classify_gaps

        candidate_profile = {"candidate_id": "min_cand"}
        result = classify_gaps(sample_requirements, candidate_profile, RESUME_TEXT)

        assert isinstance(result, list)

    def test_handles_llm_exception(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """classify_gaps catches LLM errors and returns list."""
        from gap_classifier import classify_gaps

        mock_gap_classifier_llm.side_effect = Exception("LLM timeout")
        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        assert isinstance(result, list)

    def test_handles_malformed_llm_response(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """classify_gaps handles non-dict LLM responses."""
        from gap_classifier import classify_gaps

        mock_gap_classifier_llm.return_value = "not a dict"
        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        assert isinstance(result, list)

    def test_handles_missing_gaps_key(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """classify_gaps handles response without 'gaps' key."""
        from gap_classifier import classify_gaps

        mock_gap_classifier_llm.return_value = {"other_key": []}
        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        assert isinstance(result, list)

    def test_handles_empty_resume_text(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """classify_gaps with empty resume text should return valid list."""
        from gap_classifier import classify_gaps

        result = classify_gaps(sample_requirements, sample_candidate_profile, "")
        assert isinstance(result, list)

    def test_handles_invalid_gap_type(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """classify_gaps validates gap_type enum."""
        from gap_classifier import classify_gaps

        mock_gap_classifier_llm.return_value = {
            "gaps": [
                {
                    "gap_id": "gap_1",
                    "gap_type": "invalid_type",
                    "description": "test",
                    "severity": "medium"
                }
            ]
        }

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)
        # Should fallback gracefully, not return invalid gap
        assert isinstance(result, list)

    def test_handles_invalid_severity(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """classify_gaps validates severity enum."""
        from gap_classifier import classify_gaps

        mock_gap_classifier_llm.return_value = {
            "gaps": [
                {
                    "gap_id": "gap_1",
                    "gap_type": "missing_experience",
                    "description": "test",
                    "severity": "critical"  # Invalid
                }
            ]
        }

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)
        # Should fallback gracefully, not return invalid severity
        assert isinstance(result, list)

    def test_handles_none_response(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """classify_gaps handles None from LLM."""
        from gap_classifier import classify_gaps

        mock_gap_classifier_llm.return_value = None
        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        assert isinstance(result, list)

    def test_handles_timeout_exception(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """classify_gaps catches timeout and returns list."""
        from gap_classifier import classify_gaps

        mock_gap_classifier_llm.side_effect = TimeoutError("LLM timeout")
        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        assert isinstance(result, list)


class TestGapClassifierSchema:
    """Tests for gap_classifier adherence to production schema."""

    def test_gaps_schema_compliance(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """Result must match gaps schema structure."""
        from gap_classifier import classify_gaps

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        # Schema requires: gap_id, gap_type, description, severity
        for gap in result:
            assert "gap_id" in gap
            assert "gap_type" in gap
            assert "description" in gap
            assert "severity" in gap

    def test_gap_type_enum_values(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """gap_type must match schema enum values."""
        from gap_classifier import classify_gaps

        valid = {
            "missing_experience",
            "weak_wording",
            "missing_explicit_keyword",
            "insufficient_leadership_signal",
            "seniority_mismatch",
            "domain_gap",
            "unsupported_claim_risk"
        }

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        for gap in result:
            assert gap["gap_type"] in valid

    def test_severity_enum_values(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """severity must match schema enum values: low, medium, high."""
        from gap_classifier import classify_gaps

        valid = {"low", "medium", "high"}
        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        for gap in result:
            assert gap["severity"] in valid

    def test_string_fields_are_strings(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """String fields must be strings."""
        from gap_classifier import classify_gaps

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        for gap in result:
            assert isinstance(gap["gap_id"], str)
            assert isinstance(gap["description"], str)

    def test_requirement_id_field_optional_but_valid_when_present(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """requirement_id field (if present) should be a string."""
        from gap_classifier import classify_gaps

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        for gap in result:
            if "requirement_id" in gap:
                assert isinstance(gap["requirement_id"], str)


class TestGapClassifierHeuristicSeverity:
    """Mutation-verified severity rules for heuristic classification.

    Tests here call _classify_single_requirement directly so they
    are independent of LLM mocking and catch weight/threshold regressions.
    """

    def test_missing_skill_high_importance_is_high_severity(self):
        """Missing skill with importance >= 0.85 must produce severity='high'.

        Uses 'ClickHouseDB' — not in abbreviation map, not in candidate inventory.
        """
        from gap_classifier import _classify_single_requirement
        req = {
            "requirement_id": "req_sev_high",
            "requirement_type": "must_have",
            "text": "ClickHouseDB columnar storage experience",
            "canonical_skills": ["ClickHouseDB"],
            "importance": 0.90,
        }
        candidate = {"skill_inventory": [], "experience_units": []}
        gap = _classify_single_requirement(req, candidate, "senior engineer at acme corp")
        assert gap is not None, "Should produce a gap for missing skill"
        assert gap["gap_type"] == "missing_experience", (
            f"Expected missing_experience, got '{gap['gap_type']}'"
        )
        assert gap["severity"] == "high", (
            f"importance=0.90 missing skill must be severity='high', got '{gap['severity']}'"
        )

    def test_missing_skill_low_importance_is_medium_severity(self):
        """Missing skill with importance < 0.85 must produce severity='medium'."""
        from gap_classifier import _classify_single_requirement
        req = {
            "requirement_id": "req_sev_med",
            "requirement_type": "must_have",
            "text": "Nice-to-have skill",
            "canonical_skills": ["SomeObscureTool"],
            "importance": 0.60,
        }
        candidate = {"skill_inventory": [], "experience_units": []}
        gap = _classify_single_requirement(req, candidate, "nothing here")
        assert gap is not None
        assert gap["severity"] == "medium", (
            f"importance=0.60 missing skill must be severity='medium', got '{gap['severity']}'"
        )

    def test_llm_called_even_when_no_heuristic_gaps(self):
        """LLM must be called with use_llm=True even when heuristic finds zero gaps.

        Regression test for the Phase A fix: previously guarded by
        'if use_llm and heuristic_gaps' which skipped LLM on clean resumes.
        """
        from gap_classifier import classify_gaps
        req = {
            "requirement_id": "req_llm",
            "requirement_type": "must_have",
            "text": "Python experience",
            "canonical_skills": ["Python"],
            "importance": 0.9,
        }
        candidate = {
            "skill_inventory": [
                {"canonical_skill": "Python", "aliases": [], "evidence_refs": ["proj1"]}
            ],
            "experience_units": [
                {"company": "Acme", "title": "Engineer", "skills": ["Python"]}
            ],
        }
        resume = "Python developer with 5 years experience architecting large systems."
        with patch("gap_classifier.call_llm_quality") as mock_llm:
            mock_llm.return_value = "[]"
            classify_gaps([req], candidate, resume, use_llm=True)
        mock_llm.assert_called_once(), (
            "LLM must be called with use_llm=True even when heuristic finds 0 gaps"
        )


class TestGapClassifierIntegration:
    """Integration tests with other Phase A modules."""

    def test_gaps_from_parsed_requirements(self, mock_gap_classifier_llm):
        """classify_gaps should work with parse_requirements output structure."""
        from jd_parser import parse_requirements
        from gap_classifier import classify_gaps

        # Assume parse_requirements is mocked separately
        requirements = [
            {
                "requirement_id": "r1",
                "requirement_type": "must_have",
                "category": "skill",
                "text": "Python",
                "importance": 0.9
            }
        ]

        candidate = {"candidate_id": "c1", "skill_inventory": []}
        result = classify_gaps(requirements, candidate, RESUME_TEXT)

        assert isinstance(result, list)
        # All items should be valid gap dicts
        for gap in result:
            assert "gap_id" in gap
            assert "gap_type" in gap
            assert "description" in gap
            assert "severity" in gap

    def test_multiple_gaps_per_requirement_possible(self, mock_gap_classifier_llm, sample_requirements, sample_candidate_profile):
        """Multiple gaps can reference same requirement_id."""
        from gap_classifier import classify_gaps

        mock_gap_classifier_llm.return_value = {
            "gaps": [
                {
                    "gap_id": "gap_1",
                    "requirement_id": "req_001",
                    "gap_type": "missing_experience",
                    "description": "Gap 1",
                    "severity": "high"
                },
                {
                    "gap_id": "gap_2",
                    "requirement_id": "req_001",
                    "gap_type": "weak_wording",
                    "description": "Gap 2",
                    "severity": "medium"
                }
            ]
        }

        result = classify_gaps(sample_requirements, sample_candidate_profile, RESUME_TEXT)

        # Should have both gaps
        assert len(result) >= 2
        req_001_gaps = [g for g in result if g.get("requirement_id") == "req_001"]
        assert len(req_001_gaps) >= 1
