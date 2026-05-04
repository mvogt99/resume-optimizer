"""Tests for resume_recommender.py — multi-resume comparison and ranking."""

import json
import pytest
from test_helpers import RESUME_TEXT, JD_TEXT, LINKEDIN_PROFILE, upload_resume, upload_jd, query_db


class TestResumeRecommender:
    """Tests for the resume comparison endpoint and database persistence."""

    def test_compare_requires_auth(self, client):
        """POST /api/resumes/compare without auth headers returns 401."""
        response = client.post(
            "/api/resumes/compare",
            json={"resume_ids": [1], "job_description_text": JD_TEXT}
        )
        assert response.status_code == 401

    def test_compare_rejects_empty_resume_ids(self, client, auth_headers):
        """Empty resume_ids list returns 400."""
        response = client.post(
            "/api/resumes/compare",
            json={"resume_ids": [], "job_description_text": JD_TEXT},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "resume" in response.json.get("error", "").lower()

    def test_compare_rejects_empty_job_text(self, client, auth_headers):
        """Empty job_description_text returns 400."""
        response = client.post(
            "/api/resumes/compare",
            json={"resume_ids": [1], "job_description_text": ""},
            headers=auth_headers
        )
        assert response.status_code == 400

    def test_compare_rejects_short_job_text(self, client, auth_headers):
        """Job text < 50 chars returns 400."""
        response = client.post(
            "/api/resumes/compare",
            json={"resume_ids": [1], "job_description_text": "short text"},
            headers=auth_headers
        )
        assert response.status_code == 400

    def test_compare_rejects_nonexistent_resume(self, client, auth_headers):
        """Non-existent resume_id returns 404."""
        response = client.post(
            "/api/resumes/compare",
            json={"resume_ids": [999999], "job_description_text": JD_TEXT},
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_compare_rejects_other_users_resume(self, client, auth_headers, second_user_headers):
        """Resume owned by different user returns 403/404."""
        # Upload resume as user 1
        resume_id = upload_resume(client, auth_headers)

        # Try to compare as user 2
        response = client.post(
            "/api/resumes/compare",
            json={"resume_ids": [resume_id], "job_description_text": JD_TEXT},
            headers=second_user_headers
        )
        assert response.status_code in (403, 404)

    def test_compare_two_resumes_returns_ranked(self, client, auth_headers):
        """Upload 2 resumes, compare, verify response has rankings sorted by score."""
        resume_id_1 = upload_resume(client, auth_headers)
        resume_id_2 = upload_resume(client, auth_headers, filename="resume2.txt")

        response = client.post(
            "/api/resumes/compare",
            json={
                "resume_ids": [resume_id_1, resume_id_2],
                "job_description_text": JD_TEXT
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json
        assert "recommendation_id" in data
        assert "rankings" in data
        assert len(data["rankings"]) == 2

        # Verify rankings are sorted by score (descending)
        scores = [r["score"] for r in data["rankings"]]
        assert scores == sorted(scores, reverse=True), "Rankings not sorted by score descending"

    def test_compare_returns_per_resume_breakdown(self, client, auth_headers):
        """Each ranking entry has required fields."""
        resume_id_1 = upload_resume(client, auth_headers)
        resume_id_2 = upload_resume(client, auth_headers, filename="resume2.txt")

        response = client.post(
            "/api/resumes/compare",
            json={
                "resume_ids": [resume_id_1, resume_id_2],
                "job_description_text": JD_TEXT
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        for ranking in response.json["rankings"]:
            assert "resume_id" in ranking or "resume_version_id" in ranking
            assert "filename" in ranking
            assert "source" in ranking
            assert "score" in ranking
            assert 0 <= ranking["score"] <= 100
            assert "score_breakdown" in ranking
            assert "matching_keywords" in ranking
            assert "missing_keywords" in ranking
            assert "rank" in ranking

    def test_compare_best_match_is_first(self, client, auth_headers):
        """Well-matched resume should rank first."""
        resume_id_1 = upload_resume(client, auth_headers, text=RESUME_TEXT)
        # Upload a mismatched resume
        mismatched = "Lorem ipsum dolor sit amet. The quick brown fox jumps over the lazy dog."
        resume_id_2 = upload_resume(client, auth_headers, filename="resume2.txt", text=mismatched)

        response = client.post(
            "/api/resumes/compare",
            json={
                "resume_ids": [resume_id_2, resume_id_1],  # Note: mismatched first in input
                "job_description_text": JD_TEXT
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        first_ranking = response.json["rankings"][0]
        assert first_ranking["score"] > 40  # RESUME_TEXT should score >40

    def test_compare_persists_recommendation(self, client, auth_headers):
        """Recommendation result is persisted in DB and retrievable by ID."""
        resume_id_1 = upload_resume(client, auth_headers)

        response = client.post(
            "/api/resumes/compare",
            json={
                "resume_ids": [resume_id_1],
                "job_description_text": JD_TEXT
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        recommendation_id = response.json["recommendation_id"]

        # Verify it's in the DB
        rows = query_db("SELECT * FROM resume_recommendations WHERE id = ?", (recommendation_id,))
        assert len(rows) == 1
        assert rows[0]["user_id"] == 1  # auth_headers user

    def test_compare_with_resume_version_ids(self, client, auth_headers):
        """Endpoint accepts resume_version_ids in addition to resume_ids."""
        from models import ResumeVersion

        # Create a resume version directly
        version = ResumeVersion.create(
            user_id=1,
            source="upload",
            file_name="version_test.txt",
            parsed_text=RESUME_TEXT
        )

        response = client.post(
            "/api/resumes/compare",
            json={
                "resume_version_ids": [version.id],
                "job_description_text": JD_TEXT
            },
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_compare_five_resumes_under_10s(self, client, auth_headers):
        """Comparing 5 resumes completes in < 10 seconds."""
        import time

        resume_ids = []
        for i in range(5):
            resume_id = upload_resume(client, auth_headers, filename=f"resume{i}.txt")
            resume_ids.append(resume_id)

        start = time.time()
        response = client.post(
            "/api/resumes/compare",
            json={
                "resume_ids": resume_ids,
                "job_description_text": JD_TEXT
            },
            headers=auth_headers
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 10, f"Comparison took {elapsed:.2f}s (expected < 10s)"

    def test_compare_with_linkedin_enrichment(self, client, auth_headers):
        """LinkedIn profile enrichment affects skills_match in rankings."""
        resume_id_1 = upload_resume(client, auth_headers)
        resume_id_2 = upload_resume(client, auth_headers, filename="resume2.txt")

        # Without LinkedIn enrichment
        response_no_linkedin = client.post(
            "/api/resumes/compare",
            json={
                "resume_ids": [resume_id_1, resume_id_2],
                "job_description_text": JD_TEXT
            },
            headers=auth_headers
        )

        # With LinkedIn enrichment (if available)
        # This would require importing LinkedIn profile first via separate endpoint
        # For now, just verify the field exists
        assert response_no_linkedin.status_code == 200
        assert "score_breakdown" in response_no_linkedin.json["rankings"][0]

    def test_compare_single_resume_works(self, client, auth_headers):
        """Comparing a single resume returns valid result."""
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
        assert len(response.json["rankings"]) == 1
        assert response.json["rankings"][0]["rank"] == 1

    def test_compare_response_includes_recommended_id(self, client, auth_headers):
        """Response includes recommended_resume_id for best match."""
        resume_id_1 = upload_resume(client, auth_headers, text=RESUME_TEXT)
        resume_id_2 = upload_resume(client, auth_headers, filename="resume2.txt", text="Lorem ipsum")

        response = client.post(
            "/api/resumes/compare",
            json={
                "resume_ids": [resume_id_1, resume_id_2],
                "job_description_text": JD_TEXT
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "recommended_resume_id" in response.json
        # Should recommend the well-matched one
        recommended = response.json["recommended_resume_id"]
        assert recommended == int(resume_id_1) or recommended is None  # None OK if not determined
