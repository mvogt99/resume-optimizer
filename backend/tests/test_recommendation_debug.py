"""Debug minimal test for recommendation flow."""
import json
import pytest
from test_helpers import RESUME_TEXT, JD_TEXT, upload_resume, upload_jd


@pytest.mark.integration
def test_compare_returns_recommendation_id(client, auth_headers):
    """Debug: verify compare endpoint returns valid recommendation_id."""
    resume_id = upload_resume(client, auth_headers, RESUME_TEXT, "resume1.txt")
    upload_jd(client, auth_headers, JD_TEXT)

    # Compare
    compare_resp = client.post(
        "/api/resumes/compare",
        json={
            "resume_ids": [resume_id],
            "job_description_text": JD_TEXT,
        },
        headers=auth_headers,
    )

    print(f"\nCompare response status: {compare_resp.status_code}")
    print(f"Compare response: {compare_resp.get_json()}")

    assert compare_resp.status_code == 200
    compare_data = compare_resp.get_json()
    assert "recommendation_id" in compare_data
    recommendation_id = compare_data["recommendation_id"]
    print(f"recommendation_id: {recommendation_id}")

    # Try to GET the recommendation immediately
    get_resp = client.get(
        f"/api/resumes/recommendations/{recommendation_id}",
        headers=auth_headers,
    )

    print(f"\nGET response status: {get_resp.status_code}")
    print(f"GET response: {get_resp.get_json()}")

    assert get_resp.status_code == 200, f"Expected 200, got {get_resp.status_code}: {get_resp.get_json()}"
