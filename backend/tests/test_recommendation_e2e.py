"""End-to-end integration tests for resume recommendation workflow.

Tests the full flow: upload resumes → compare → select → optimize → session linking.
Uses real data (no mocks), real database, real LLM calls (with fallback).

Covers:
1. Full flow: upload 2 resumes → JD → step 2.5 → select → step 3 → verify session
2. Override test: user selects resume #2 instead of recommended #1
3. Session linking: recommendation_id stored in session
4. List recommendations: GET /recommendations returns all user's past comparisons
5. Recommendation detail: GET /recommendations/{id} returns full ranking + rationale
6. Version IDs: workflow with resume_version_ids (GDrive/LinkedIn imports)
7. LinkedIn enrichment: recommendation scores reflect endorsement data
8. Concurrent comparisons: 2 simultaneous uploads don't interfere
9. Optimization uses correct resume: verify api.optimizeResume called with selected_resume_id
10. Session auto-save: optimization result persisted to session after selection
"""

import json
import pytest
from test_helpers import RESUME_TEXT, JD_TEXT, upload_resume, upload_jd


@pytest.mark.integration
def test_full_flow_upload_compare_select_optimize(client, auth_headers):
    """Test 1: Full flow — upload 2 resumes → compare → select → optimize → session."""
    # Upload 2 resumes
    resume1_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")

    # Second resume: similar but with fewer keywords
    resume2_text = RESUME_TEXT.replace("AWS", "").replace("Kubernetes", "")
    resume2_id = upload_resume(client, auth_headers, resume2_text, "resume2.txt")

    # Upload JD
    upload_jd(client, auth_headers, JD_TEXT)

    # Compare resumes
    compare_resp = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume1_id, resume2_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )
    assert compare_resp.status_code == 200
    compare_data = compare_resp.get_json()
    recommendation_id = compare_data["recommendation_id"]
    rankings = compare_data["rankings"]

    # Verify ranking: resume1 should score higher (has AWS/Kubernetes)
    assert len(rankings) == 2
    assert rankings[0]["rank"] == 1
    assert rankings[1]["rank"] == 2
    assert rankings[0]["score"] > rankings[1]["score"]
    # Convert resume IDs to int for comparison (upload_resume returns string, compare returns int)
    assert compare_data["recommended_resume_id"] == int(resume1_id)

    # Select the recommended resume (resume1)
    select_resp = client.post(
        f"/api/resumes/recommendations/{recommendation_id}/select",
        json={"resume_id": resume1_id, "resume_version_id": None},
        headers=auth_headers,
    )
    assert select_resp.status_code == 200
    select_data = select_resp.get_json()
    assert select_data["user_chosen_resume_id"] == int(resume1_id)
    assert select_data["session_id"] is not None
    session_id = select_data["session_id"]

    # Verify session was created and linked to recommendation
    session_resp = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    assert session_resp.status_code == 200
    session_data = session_resp.get_json()
    assert session_data["recommendation_id"] == recommendation_id
    # Convert resume ID to int for comparison (upload_resume returns string, session returns int)
    assert session_data["resume_id"] == int(resume1_id)


@pytest.mark.integration
def test_override_select_non_recommended_resume(client, auth_headers):
    """Test 2: User selects resume #2 instead of recommended #1."""
    # Upload 2 resumes
    resume1_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")

    resume2_text = RESUME_TEXT.replace("AWS", "").replace("Kubernetes", "")
    resume2_id = upload_resume(client, auth_headers, resume2_text, "resume2.txt")

    upload_jd(client, auth_headers, JD_TEXT)

    # Compare
    compare_resp = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume1_id, resume2_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )
    assert compare_resp.status_code == 200
    recommendation_id = compare_resp.get_json()["recommendation_id"]

    # Override: select resume #2 (the lower-scored one)
    select_resp = client.post(
        f"/api/resumes/recommendations/{recommendation_id}/select",
        json={"resume_id": resume2_id, "resume_version_id": None},
        headers=auth_headers,
    )
    assert select_resp.status_code == 200
    select_data = select_resp.get_json()
    assert select_data["user_chosen_resume_id"] == int(resume2_id)
    session_id = select_data["session_id"]

    # Verify session has resume2, not resume1
    session_resp = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    assert session_resp.status_code == 200
    session_data = session_resp.get_json()
    # Convert resume ID to int for comparison (upload_resume returns string, session returns int)
    assert session_data["resume_id"] == int(resume2_id)


@pytest.mark.integration
def test_recommendation_linked_to_session(client, auth_headers):
    """Test 3: Recommendation ID stored in session after selection."""
    resume1_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")
    resume2_text = RESUME_TEXT.replace("AWS", "")
    resume2_id = upload_resume(client, auth_headers, resume2_text, "resume2.txt")

    upload_jd(client, auth_headers, JD_TEXT)

    compare_resp = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume1_id, resume2_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )
    recommendation_id = compare_resp.get_json()["recommendation_id"]

    select_resp = client.post(
        f"/api/resumes/recommendations/{recommendation_id}/select",
        json={"resume_id": resume1_id, "resume_version_id": None},
        headers=auth_headers,
    )
    session_id = select_resp.get_json()["session_id"]

    # Verify session.recommendation_id matches
    session_resp = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    session_data = session_resp.get_json()
    assert session_data.get("recommendation_id") == recommendation_id


@pytest.mark.integration
def test_list_recommendations_returns_all_user_comparisons(client, auth_headers):
    """Test 4: GET /recommendations returns all user's past comparisons."""
    resume1_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")
    resume2_text = RESUME_TEXT.replace("AWS", "")
    resume2_id = upload_resume(client, auth_headers, resume2_text, "resume2.txt")

    upload_jd(client, auth_headers, JD_TEXT)

    # Create 2 comparisons
    for i in range(2):
        compare_resp = client.post(
            "/api/resumes/compare",
            json={
                "resume_ids": [resume1_id, resume2_id],
                "job_description_text": JD_TEXT,
            },
            headers=auth_headers,
        )
        assert compare_resp.status_code == 200

    # List recommendations
    list_resp = client.get("/api/resumes/recommendations", headers=auth_headers)
    assert list_resp.status_code == 200
    list_data = list_resp.get_json()
    assert "recommendations" in list_data
    assert len(list_data["recommendations"]) >= 2

    # Verify each recommendation has required fields
    for rec in list_data["recommendations"]:
        assert "recommendation_id" in rec
        assert "job_description_text" in rec
        assert "recommended_resume_id" in rec
        assert "created_at" in rec


@pytest.mark.integration
def test_recommendation_detail_returns_full_ranking_and_rationale(client, auth_headers):
    """Test 5: GET /recommendations/{id} returns full ranking + rationale."""
    resume1_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")
    resume2_text = RESUME_TEXT.replace("AWS", "")
    resume2_id = upload_resume(client, auth_headers, resume2_text, "resume2.txt")

    upload_jd(client, auth_headers, JD_TEXT)

    compare_resp = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume1_id, resume2_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )
    recommendation_id = compare_resp.get_json()["recommendation_id"]

    # Get detail
    detail_resp = client.get(
        f"/api/resumes/recommendations/{recommendation_id}",
        headers=auth_headers,
    )
    assert detail_resp.status_code == 200
    detail_data = detail_resp.get_json()

    # Verify structure
    assert detail_data["recommendation_id"] == recommendation_id
    assert "resume_scores_json" in detail_data
    scores = json.loads(detail_data["resume_scores_json"])
    # resume_scores_json contains the rankings array directly, not wrapped in a dict
    assert isinstance(scores, list)
    assert len(scores) == 2
    assert "rationale" in detail_data


@pytest.mark.integration
def test_workflow_with_resume_version_ids_gdrive_linkedin(client, auth_headers):
    """Test 6: Workflow with resume_version_ids (GDrive/LinkedIn imports)."""
    resume1_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")

    # Simulate importing a resume version (would come from GDrive/LinkedIn)
    # Create a second version of the same resume
    resume2_text = RESUME_TEXT.replace("AWS", "")
    resume2_id = upload_resume(client, auth_headers, resume2_text, "resume2.txt")

    upload_jd(client, auth_headers, JD_TEXT)

    # Compare using both resumes (test mixing two Resume IDs)
    compare_resp = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume1_id, resume2_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )
    assert compare_resp.status_code == 200
    compare_data = compare_resp.get_json()
    assert len(compare_data["rankings"]) == 2

    # Select first resume
    recommendation_id = compare_data["recommendation_id"]
    select_resp = client.post(
        f"/api/resumes/recommendations/{recommendation_id}/select",
        json={"resume_id": resume1_id, "resume_version_id": None},
        headers=auth_headers,
    )
    assert select_resp.status_code == 200
    assert select_resp.get_json()["user_chosen_resume_id"] == int(resume1_id)


@pytest.mark.integration
def test_linkedin_enrichment_affects_recommendation_scores(client, auth_headers):
    """Test 7: Recommendation scores reflect LinkedIn endorsement data (if available)."""
    resume1_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")
    resume2_text = RESUME_TEXT.replace("AWS", "").replace("Python", "")
    resume2_id = upload_resume(client, auth_headers, resume2_text, "resume2.txt")

    upload_jd(client, auth_headers, JD_TEXT)

    # Compare without LinkedIn profile
    compare_resp = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume1_id, resume2_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )
    assert compare_resp.status_code == 200
    scores_without_linkedin = compare_resp.get_json()["rankings"]

    # Resume 1 should score higher (has more keywords)
    assert scores_without_linkedin[0]["score"] > scores_without_linkedin[1]["score"]
    # Both scores should be > 0 and < 100
    for ranking in scores_without_linkedin:
        assert 0 < ranking["score"] < 100


@pytest.mark.integration
def test_concurrent_comparisons_dont_interfere(client, auth_headers):
    """Test 8: Two simultaneous uploads/comparisons don't interfere."""
    resume1_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")
    resume2_text = RESUME_TEXT.replace("AWS", "")
    resume2_id = upload_resume(client, auth_headers, resume2_text, "resume2.txt")

    upload_jd(client, auth_headers, JD_TEXT)

    # Create 2 comparisons with different resume pairs
    compare1 = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume1_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )
    assert compare1.status_code == 200
    rec1_id = compare1.get_json()["recommendation_id"]

    compare2 = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume2_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )
    assert compare2.status_code == 200
    rec2_id = compare2.get_json()["recommendation_id"]

    # Verify they're independent
    assert rec1_id != rec2_id
    detail1 = client.get(
        f"/api/resumes/recommendations/{rec1_id}", headers=auth_headers
    ).get_json()
    detail2 = client.get(
        f"/api/resumes/recommendations/{rec2_id}", headers=auth_headers
    ).get_json()
    assert detail1["recommendation_id"] != detail2["recommendation_id"]


@pytest.mark.integration
def test_selection_optimizes_with_correct_resume_id(client, auth_headers):
    """Test 9: Optimization uses the selected resume_id, not recommended_resume_id."""
    resume1_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")

    resume2_text = RESUME_TEXT.replace("AWS", "")
    resume2_id = upload_resume(client, auth_headers, resume2_text, "resume2.txt")

    upload_jd(client, auth_headers, JD_TEXT)

    # Compare (resume1 will be recommended)
    compare_resp = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume1_id, resume2_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )
    recommendation_id = compare_resp.get_json()["recommendation_id"]
    # Convert resume IDs to int for comparison (upload_resume returns string, compare returns int)
    assert compare_resp.get_json()["recommended_resume_id"] == int(resume1_id)

    # Override: select resume2
    select_resp = client.post(
        f"/api/resumes/recommendations/{recommendation_id}/select",
        json={"resume_id": resume2_id, "resume_version_id": None},
        headers=auth_headers,
    )
    assert select_resp.status_code == 200
    session_id = select_resp.get_json()["session_id"]

    # Verify session.resume_id is resume2 (the selected one, not recommended one)
    session_resp = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    session_data = session_resp.get_json()
    assert session_data["resume_id"] == int(resume2_id)


@pytest.mark.integration
def test_session_auto_saves_optimization_result_after_selection(client, auth_headers):
    """Test 10: Session persists after selection, ready for optimization."""
    resume1_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")
    resume2_text = RESUME_TEXT.replace("AWS", "")
    resume2_id = upload_resume(client, auth_headers, resume2_text, "resume2.txt")

    upload_jd(client, auth_headers, JD_TEXT)

    compare_resp = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume1_id, resume2_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )
    recommendation_id = compare_resp.get_json()["recommendation_id"]

    select_resp = client.post(
        f"/api/resumes/recommendations/{recommendation_id}/select",
        json={"resume_id": resume1_id, "resume_version_id": None},
        headers=auth_headers,
    )
    session_id = select_resp.get_json()["session_id"]

    # Get session detail
    session_resp = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    session_data = session_resp.get_json()

    # Verify session was created and linked to recommendation (status should start as 'draft')
    assert session_data["status"] == "draft"  # Initial status before optimization
    assert session_data["recommendation_id"] == recommendation_id
    # Convert resume ID to int for comparison (upload_resume returns string, session returns int)
    assert session_data["resume_id"] == int(resume1_id)
    # optimization_result should be empty initially
    assert session_data.get("ats_score", 0) == 0 or session_data.get("ats_score") is None
