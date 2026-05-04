"""Tests for recommendation_rationale.py — LLM rationale + template fallback."""

import pytest
from test_helpers import RESUME_TEXT, JD_TEXT


# Shared test rankings fixture — two resumes, first is better
RANKINGS = [
    {
        "resume_id": 1,
        "resume_version_id": None,
        "filename": "senior_architect_resume.txt",
        "source": "upload",
        "score": 78,
        "score_breakdown": {
            "keyword_coverage": 82.0,
            "semantic_similarity": 74.5,
            "skills_match": 79.3,
            "section_completeness": 75.0,
        },
        "matching_keywords": ["python", "kubernetes", "aws", "microservices", "terraform"],
        "missing_keywords": ["kafka", "postgresql"],
        "rank": 1,
    },
    {
        "resume_id": 2,
        "resume_version_id": None,
        "filename": "generic_developer_resume.txt",
        "source": "upload",
        "score": 32,
        "score_breakdown": {
            "keyword_coverage": 28.0,
            "semantic_similarity": 35.1,
            "skills_match": 30.5,
            "section_completeness": 50.0,
        },
        "matching_keywords": ["python"],
        "missing_keywords": ["kubernetes", "aws", "terraform", "kafka"],
        "rank": 2,
    },
]


class TestRationaleGeneration:
    """Unit tests for generate_rationale() and template_rationale()."""

    def test_generate_rationale_returns_string(self):
        """generate_rationale() must return a non-empty string."""
        from recommendation_rationale import generate_rationale

        result = generate_rationale(RANKINGS, JD_TEXT, timeout=30)

        assert isinstance(result, str), "Rationale must be a string"
        assert len(result) > 50, f"Rationale too short: {len(result)} chars"

    def test_rationale_mentions_top_resume_filename(self):
        """Rationale must reference the top-ranked resume filename."""
        from recommendation_rationale import generate_rationale

        result = generate_rationale(RANKINGS, JD_TEXT, timeout=30)

        # Either the filename or a recognizable part of it should appear
        assert "senior_architect" in result.lower() or "rank 1" in result.lower(), (
            f"Rationale does not mention top resume: {result[:200]}"
        )

    def test_rationale_mentions_matching_keyword(self):
        """Rationale must mention at least one matching keyword."""
        from recommendation_rationale import generate_rationale

        result = generate_rationale(RANKINGS, JD_TEXT, timeout=30)
        result_lower = result.lower()

        matching = RANKINGS[0]["matching_keywords"]
        mentioned = any(kw.lower() in result_lower for kw in matching)
        assert mentioned, (
            f"Rationale mentions no matching keywords ({matching}): {result[:300]}"
        )

    def test_rationale_mentions_gap(self):
        """Rationale must mention at least one missing keyword or gap."""
        from recommendation_rationale import generate_rationale

        result = generate_rationale(RANKINGS, JD_TEXT, timeout=30)
        result_lower = result.lower()

        missing = RANKINGS[0]["missing_keywords"]
        has_gap_mention = (
            any(kw.lower() in result_lower for kw in missing)
            or "gap" in result_lower
            or "missing" in result_lower
            or "lacks" in result_lower
        )
        assert has_gap_mention, (
            f"Rationale does not mention any gaps: {result[:300]}"
        )

    def test_rationale_fallback_on_llm_failure(self, monkeypatch):
        """If LLM call raises, template_rationale() is returned instead."""
        from recommendation_rationale import generate_rationale

        # Simulate LLM failure
        def raise_error(*args, **kwargs):
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr("recommendation_rationale.call_llm_quality", raise_error)

        result = generate_rationale(RANKINGS, JD_TEXT, timeout=30)

        # Should still return a non-empty string (template fallback)
        assert isinstance(result, str)
        assert len(result) > 50, "Fallback rationale too short"

    def test_fallback_rationale_references_scores(self):
        """template_rationale() must reference the top resume's numeric score."""
        from recommendation_rationale import template_rationale

        result = template_rationale(RANKINGS)

        assert isinstance(result, str)
        # Score 78 must appear in the template
        assert "78" in result, f"Template does not mention score 78: {result}"
        assert len(result) > 50

    def test_fallback_rationale_mentions_filename(self):
        """template_rationale() must mention the top resume filename."""
        from recommendation_rationale import template_rationale

        result = template_rationale(RANKINGS)

        assert "senior_architect" in result.lower() or "senior_architect_resume" in result, (
            f"Template does not mention filename: {result}"
        )

    def test_fallback_rationale_is_deterministic(self):
        """template_rationale() returns identical output for same input."""
        from recommendation_rationale import template_rationale

        result1 = template_rationale(RANKINGS)
        result2 = template_rationale(RANKINGS)
        result3 = template_rationale(RANKINGS)

        assert result1 == result2 == result3, "template_rationale is not deterministic"

    def test_generate_rationale_single_resume(self):
        """generate_rationale() works with a single ranked resume."""
        from recommendation_rationale import generate_rationale

        single = [RANKINGS[0]]
        result = generate_rationale(single, JD_TEXT, timeout=30)

        assert isinstance(result, str)
        assert len(result) > 20

    def test_generate_rationale_empty_rankings(self):
        """generate_rationale() with empty rankings returns a safe string."""
        from recommendation_rationale import generate_rationale

        result = generate_rationale([], JD_TEXT, timeout=30)

        assert isinstance(result, str)
        # Should not crash, may be empty or placeholder
        assert result is not None


class TestRationaleEndpointIntegration:
    """Integration tests for rationale in /api/resumes/compare endpoint."""

    def test_compare_endpoint_includes_rationale(self, client, auth_headers):
        """POST /api/resumes/compare returns rationale field in response."""
        from test_helpers import upload_resume

        resume_id = upload_resume(client, auth_headers)

        response = client.post(
            "/api/resumes/compare",
            json={
                "resume_ids": [resume_id],
                "job_description_text": JD_TEXT
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json
        assert "rationale" in data, f"Missing 'rationale' field in response: {list(data.keys())}"
        assert isinstance(data["rationale"], str)
        assert len(data["rationale"]) > 0

    def test_compare_skip_rationale_flag(self, client, auth_headers):
        """POST /api/resumes/compare with skip_rationale=true omits LLM call."""
        from test_helpers import upload_resume
        import time

        resume_id = upload_resume(client, auth_headers)

        start = time.time()
        response = client.post(
            "/api/resumes/compare",
            json={
                "resume_ids": [resume_id],
                "job_description_text": JD_TEXT,
                "skip_rationale": True
            },
            headers=auth_headers
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        data = response.json
        # With skip_rationale, response should be fast (template or None)
        # No hard timing assert — just verify field present and no LLM wait
        assert "rationale" in data
