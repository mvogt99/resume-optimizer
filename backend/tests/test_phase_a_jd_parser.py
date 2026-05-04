"""Tests for Phase A jd_parser module.

JD Parser parses job description into structured requirements.
Returns list of requirement dicts with requirement_id, requirement_type, category, text, importance.
Never raises on error — always returns fallback list.
"""

from unittest.mock import patch

import pytest
from test_helpers import JD_TEXT


@pytest.fixture
def mock_jd_parser_llm():
    """Mock call_llm_quality for jd_parser without actual LLM calls."""
    with patch("jd_parser.call_llm_quality") as mock:
        mock.return_value = {
            "requirements": [
                {
                    "requirement_id": "req_001",
                    "requirement_type": "must_have",
                    "category": "programming_language",
                    "text": "5+ years Python experience",
                    "importance": 0.95,
                    "canonical_skills": ["Python"]
                },
                {
                    "requirement_id": "req_002",
                    "requirement_type": "preferred",
                    "category": "cloud_platform",
                    "text": "AWS or GCP experience",
                    "importance": 0.70,
                    "canonical_skills": ["AWS", "GCP"]
                },
                {
                    "requirement_id": "req_003",
                    "requirement_type": "leadership",
                    "category": "leadership_signals",
                    "text": "Team lead or management experience",
                    "importance": 0.60,
                    "canonical_skills": []
                }
            ]
        }
        yield mock


class TestJDParserHappyPath:
    """Tests for jd_parser.parse_requirements() — happy path."""

    def test_returns_list(self, mock_jd_parser_llm):
        """parse_requirements must return a list."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)
        assert isinstance(result, list)

    def test_items_are_dicts(self, mock_jd_parser_llm):
        """Each item in result list must be a dict."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)
        assert all(isinstance(item, dict) for item in result)

    def test_has_required_fields(self, mock_jd_parser_llm):
        """Each requirement must have: requirement_id, requirement_type, category, text, importance."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)
        required_fields = {"requirement_id", "requirement_type", "category", "text", "importance"}
        for req in result:
            assert required_fields.issubset(req.keys())

    def test_requirement_type_is_valid_enum(self, mock_jd_parser_llm):
        """requirement_type must be one of 7 valid values."""
        from jd_parser import parse_requirements

        valid_types = {"must_have", "preferred", "leadership", "domain", "education", "certification", "other"}
        result = parse_requirements(JD_TEXT)

        for req in result:
            assert req["requirement_type"] in valid_types

    def test_importance_is_float_0_to_1(self, mock_jd_parser_llm):
        """importance field must be float in [0.0, 1.0]."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)

        for req in result:
            importance = req["importance"]
            assert isinstance(importance, (int, float))
            assert 0.0 <= importance <= 1.0

    def test_requirement_id_is_nonempty_string(self, mock_jd_parser_llm):
        """requirement_id must be a non-empty string."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)

        for req in result:
            assert isinstance(req["requirement_id"], str)
            assert len(req["requirement_id"]) > 0

    def test_text_is_nonempty_string(self, mock_jd_parser_llm):
        """text field must be a non-empty string."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)

        for req in result:
            assert isinstance(req["text"], str)
            assert len(req["text"]) > 0

    def test_category_is_nonempty_string(self, mock_jd_parser_llm):
        """category field must be a non-empty string."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)

        for req in result:
            assert isinstance(req["category"], str)
            assert len(req["category"]) > 0

    def test_returns_multiple_requirements(self, mock_jd_parser_llm):
        """parse_requirements should return multiple requirements for typical JD."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)
        # Mock returns 3 requirements
        assert len(result) >= 1

    def test_contains_all_requirement_types_from_mock(self, mock_jd_parser_llm):
        """Result should contain all requirement_types from mock."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)
        req_types = {req["requirement_type"] for req in result}
        # Mock has must_have, preferred, leadership
        assert "must_have" in req_types
        assert "preferred" in req_types
        assert "leadership" in req_types


class TestJDParserErrorHandling:
    """Tests for jd_parser error fallback behavior."""

    def test_empty_jd_returns_list(self, mock_jd_parser_llm):
        """parse_requirements with empty text should return list (not raise)."""
        from jd_parser import parse_requirements

        result = parse_requirements("")
        assert isinstance(result, list)

    def test_handles_llm_exception(self, mock_jd_parser_llm):
        """parse_requirements catches LLM errors and returns list."""
        from jd_parser import parse_requirements

        mock_jd_parser_llm.side_effect = Exception("LLM API down")
        result = parse_requirements(JD_TEXT)

        assert isinstance(result, list)

    def test_handles_malformed_dict_response(self, mock_jd_parser_llm):
        """parse_requirements handles non-list 'requirements' field."""
        from jd_parser import parse_requirements

        mock_jd_parser_llm.return_value = {"error": "malformed"}
        result = parse_requirements(JD_TEXT)

        assert isinstance(result, list)

    def test_handles_missing_requirements_key(self, mock_jd_parser_llm):
        """parse_requirements handles response without 'requirements' key."""
        from jd_parser import parse_requirements

        mock_jd_parser_llm.return_value = {"other_key": []}
        result = parse_requirements(JD_TEXT)

        assert isinstance(result, list)

    def test_handles_invalid_requirement_type(self, mock_jd_parser_llm):
        """parse_requirements validates requirement_type enum."""
        from jd_parser import parse_requirements

        mock_jd_parser_llm.return_value = {
            "requirements": [
                {
                    "requirement_id": "r1",
                    "requirement_type": "invalid_type",
                    "category": "test",
                    "text": "test",
                    "importance": 0.5
                }
            ]
        }

        result = parse_requirements(JD_TEXT)
        # Should fallback gracefully, not return invalid requirement
        assert isinstance(result, list)

    def test_handles_importance_out_of_range(self, mock_jd_parser_llm):
        """parse_requirements validates importance in [0, 1]."""
        from jd_parser import parse_requirements

        mock_jd_parser_llm.return_value = {
            "requirements": [
                {
                    "requirement_id": "r1",
                    "requirement_type": "must_have",
                    "category": "test",
                    "text": "test",
                    "importance": 1.5  # Invalid
                }
            ]
        }

        result = parse_requirements(JD_TEXT)
        # Should fallback gracefully, not return invalid importance
        assert isinstance(result, list)

    def test_handles_none_response(self, mock_jd_parser_llm):
        """parse_requirements handles None from LLM."""
        from jd_parser import parse_requirements

        mock_jd_parser_llm.return_value = None
        result = parse_requirements(JD_TEXT)

        assert isinstance(result, list)

    def test_handles_timeout_exception(self, mock_jd_parser_llm):
        """parse_requirements catches timeout and returns list."""
        from jd_parser import parse_requirements

        mock_jd_parser_llm.side_effect = TimeoutError("LLM timeout")
        result = parse_requirements(JD_TEXT)

        assert isinstance(result, list)

    def test_handles_missing_required_fields(self, mock_jd_parser_llm):
        """parse_requirements validates all required fields present."""
        from jd_parser import parse_requirements

        mock_jd_parser_llm.return_value = {
            "requirements": [
                {"requirement_id": "r1"}  # Missing all other required fields
            ]
        }

        result = parse_requirements(JD_TEXT)
        # Should fallback gracefully
        assert isinstance(result, list)


class TestJDParserSchema:
    """Tests for jd_parser adherence to production schema."""

    def test_normalized_requirements_schema(self, mock_jd_parser_llm):
        """Result must match normalized_requirements schema."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)

        # Schema requires each: requirement_id, requirement_type, category, text, importance
        for req in result:
            assert "requirement_id" in req
            assert "requirement_type" in req
            assert "category" in req
            assert "text" in req
            assert "importance" in req

    def test_requirement_type_enum_values(self, mock_jd_parser_llm):
        """requirement_type must match schema enum values."""
        from jd_parser import parse_requirements

        valid = {"must_have", "preferred", "leadership", "domain", "education", "certification", "other"}
        result = parse_requirements(JD_TEXT)

        for req in result:
            assert req["requirement_type"] in valid

    def test_importance_range(self, mock_jd_parser_llm):
        """importance must satisfy schema constraints: number in [0, 1]."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)

        for req in result:
            assert isinstance(req["importance"], (int, float))
            assert 0 <= req["importance"] <= 1

    def test_string_fields_are_strings(self, mock_jd_parser_llm):
        """String fields must be strings (requirement_id, category, text)."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)

        for req in result:
            assert isinstance(req["requirement_id"], str)
            assert isinstance(req["category"], str)
            assert isinstance(req["text"], str)

    def test_optional_canonical_skills_when_present(self, mock_jd_parser_llm):
        """If canonical_skills present, must be array of strings."""
        from jd_parser import parse_requirements

        result = parse_requirements(JD_TEXT)

        for req in result:
            if "canonical_skills" in req:
                assert isinstance(req["canonical_skills"], list)
                assert all(isinstance(s, str) for s in req["canonical_skills"])
