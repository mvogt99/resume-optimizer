"""Tests for Phase A normalizer module.

Normalizer extracts candidate profile data from resume text.
Returns dict with candidate_id, target_role_families, skill_inventory, experience_units.
Never raises on error — always returns fallback dict.
"""

from unittest.mock import patch

import pytest
from test_helpers import RESUME_TEXT, JD_TEXT


@pytest.fixture
def mock_normalizer_llm():
    """Mock call_llm_quality for normalizer without actual LLM calls."""
    with patch("normalizer.call_llm_quality") as mock:
        mock.return_value = {
            "target_role_families": ["Software Engineer", "Full Stack Developer"],
            "skill_inventory": [
                {
                    "canonical_skill": "Python",
                    "aliases": ["python3", "py"],
                    "evidence_refs": ["resume_line_5", "resume_line_12"],
                    "proficiency_estimate": "advanced",
                    "years_estimate": 8.0,
                    "categories": ["programming_language", "backend"]
                },
                {
                    "canonical_skill": "AWS",
                    "aliases": ["amazon_web_services", "aws-services"],
                    "evidence_refs": ["resume_line_18"],
                    "proficiency_estimate": "intermediate",
                    "years_estimate": 5.0,
                    "categories": ["cloud_platform", "infrastructure"]
                }
            ]
        }
        yield mock


class TestNormalizerHappyPath:
    """Tests for normalizer.normalize_candidate() — happy path."""

    def test_returns_dict(self, mock_normalizer_llm):
        """normalize_candidate must return a dict."""
        from normalizer import normalize_candidate

        result = normalize_candidate("user_123", RESUME_TEXT)
        assert isinstance(result, dict)

    def test_has_required_keys(self, mock_normalizer_llm):
        """Result must contain: candidate_id, target_role_families, skill_inventory, experience_units."""
        from normalizer import normalize_candidate

        result = normalize_candidate("user_456", RESUME_TEXT)
        required_keys = {"candidate_id", "target_role_families", "skill_inventory", "experience_units"}
        assert required_keys.issubset(result.keys())

    def test_candidate_id_generated(self, mock_normalizer_llm):
        """candidate_id must be a non-empty string."""
        from normalizer import normalize_candidate

        result = normalize_candidate("user_789", RESUME_TEXT)
        assert "candidate_id" in result
        assert isinstance(result["candidate_id"], str)
        assert len(result["candidate_id"]) > 0

    def test_target_role_families_is_list(self, mock_normalizer_llm):
        """target_role_families must be a list of strings."""
        from normalizer import normalize_candidate

        result = normalize_candidate("user_abc", RESUME_TEXT)
        assert isinstance(result["target_role_families"], list)
        assert all(isinstance(role, str) for role in result["target_role_families"])

    def test_skill_inventory_has_required_fields(self, mock_normalizer_llm):
        """Each skill must have canonical_skill, aliases, evidence_refs."""
        from normalizer import normalize_candidate

        result = normalize_candidate("user_def", RESUME_TEXT)
        for skill in result["skill_inventory"]:
            assert "canonical_skill" in skill
            assert "aliases" in skill
            assert "evidence_refs" in skill
            assert isinstance(skill["aliases"], list)
            assert isinstance(skill["evidence_refs"], list)

    def test_experience_units_is_list(self, mock_normalizer_llm):
        """experience_units must be a list of dicts."""
        from normalizer import normalize_candidate

        result = normalize_candidate("user_ghi", RESUME_TEXT)
        assert isinstance(result["experience_units"], list)
        for unit in result["experience_units"]:
            assert isinstance(unit, dict)

    def test_skill_canonical_skill_is_nonempty_string(self, mock_normalizer_llm):
        """Each skill's canonical_skill must be non-empty string."""
        from normalizer import normalize_candidate

        result = normalize_candidate("user_skills", RESUME_TEXT)
        for skill in result["skill_inventory"]:
            assert isinstance(skill["canonical_skill"], str)
            assert len(skill["canonical_skill"]) > 0

    def test_contains_python_and_aws_from_mock(self, mock_normalizer_llm):
        """Normalized result should contain skills from mock response."""
        from normalizer import normalize_candidate

        result = normalize_candidate("user_mock", RESUME_TEXT)
        skill_names = [s.get("canonical_skill", "") for s in result["skill_inventory"]]
        assert "Python" in skill_names
        assert "AWS" in skill_names


class TestNormalizerErrorHandling:
    """Tests for normalizer error fallback behavior."""

    def test_empty_resume_returns_fallback(self, mock_normalizer_llm):
        """Empty resume text should return valid fallback dict."""
        from normalizer import normalize_candidate

        result = normalize_candidate("user_empty", "")
        assert isinstance(result, dict)
        assert "candidate_id" in result
        assert isinstance(result["target_role_families"], list)
        assert isinstance(result["skill_inventory"], list)
        assert isinstance(result["experience_units"], list)

    def test_handles_llm_exception(self, mock_normalizer_llm):
        """normalize_candidate catches LLM errors and returns fallback."""
        from normalizer import normalize_candidate

        mock_normalizer_llm.side_effect = RuntimeError("API unavailable")
        result = normalize_candidate("user_error", RESUME_TEXT)

        assert isinstance(result, dict)
        assert "candidate_id" in result

    def test_handles_malformed_llm_response(self, mock_normalizer_llm):
        """normalize_candidate handles non-dict LLM responses."""
        from normalizer import normalize_candidate

        mock_normalizer_llm.return_value = "not a dict"
        result = normalize_candidate("user_malformed", RESUME_TEXT)

        assert isinstance(result, dict)
        assert "candidate_id" in result

    def test_handles_missing_required_fields(self, mock_normalizer_llm):
        """If LLM response lacks required fields, fallback gracefully."""
        from normalizer import normalize_candidate

        mock_normalizer_llm.return_value = {"skill_inventory": []}
        result = normalize_candidate("user_missing_fields", RESUME_TEXT)

        assert isinstance(result, dict)
        assert "candidate_id" in result
        assert "target_role_families" in result
        assert "experience_units" in result

    def test_handles_timeout(self, mock_normalizer_llm):
        """normalize_candidate catches timeout and returns fallback."""
        from normalizer import normalize_candidate

        mock_normalizer_llm.side_effect = TimeoutError("LLM timeout")
        result = normalize_candidate("user_timeout", RESUME_TEXT)

        assert isinstance(result, dict)
        assert "candidate_id" in result

    def test_handles_key_error_in_response(self, mock_normalizer_llm):
        """normalize_candidate gracefully handles malformed response structure."""
        from normalizer import normalize_candidate

        mock_normalizer_llm.return_value = None
        result = normalize_candidate("user_none", RESUME_TEXT)

        assert isinstance(result, dict)
        assert "candidate_id" in result


class TestNormalizerSchema:
    """Tests for normalizer adherence to production schema."""

    def test_candidate_profile_schema_compliance(self, mock_normalizer_llm):
        """Result must match candidate_profile schema."""
        from normalizer import normalize_candidate

        result = normalize_candidate("schema_test_1", RESUME_TEXT)

        assert "candidate_id" in result
        assert "target_role_families" in result
        assert "experience_units" in result
        assert "skill_inventory" in result
        assert isinstance(result["target_role_families"], list)
        assert isinstance(result["experience_units"], list)
        assert isinstance(result["skill_inventory"], list)

    def test_skill_inventory_item_schema(self, mock_normalizer_llm):
        """Each skill_inventory item must match schema."""
        from normalizer import normalize_candidate

        result = normalize_candidate("schema_skills", RESUME_TEXT)

        for skill in result["skill_inventory"]:
            assert "canonical_skill" in skill
            assert "aliases" in skill
            assert isinstance(skill["aliases"], list)

    def test_experience_units_item_schema(self, mock_normalizer_llm):
        """Each experience_unit item should have experience_id or standard fields."""
        from normalizer import normalize_candidate

        result = normalize_candidate("schema_exp", RESUME_TEXT)

        for unit in result["experience_units"]:
            assert isinstance(unit, dict)
            # At least one identifying field
            has_id_field = any(k in unit for k in ["experience_id", "title", "company"])
            assert has_id_field or len(unit) == 0
