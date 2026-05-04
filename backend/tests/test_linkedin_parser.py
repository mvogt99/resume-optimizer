"""Tests for linkedin_parser.py — pure logic, no external services."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from linkedin_parser import extract_accomplishments, parse_linkedin_json

# ---------------------------------------------------------------------------
# Real LinkedIn profile fixture (from working-docs)
# ---------------------------------------------------------------------------
REAL_PROFILE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "working-docs",
    "linkedin",
    "linkedin_profile_merged_api_preferred.json",
)


@pytest.fixture
def real_profile():
    """Load the real LinkedIn JSON if available."""
    if not os.path.exists(REAL_PROFILE_PATH):
        pytest.skip("Real LinkedIn profile JSON not found")
    with open(REAL_PROFILE_PATH, "r") as f:
        return json.load(f)


@pytest.fixture
def minimal_profile():
    """Minimal valid LinkedIn profile dict."""
    return {
        "full_name": "Jane Doe",
        "headline": "Software Engineer",
        "summary": "Experienced developer.",
        "email": "jane@example.com",
        "current_job": {"title": "Staff Engineer", "company": "Acme Corp", "location": "NYC"},
        "previous_jobs": [
            {
                "title": "Senior Dev",
                "company": "OldCo",
                "location": "Boston",
                "started_on": "2018",
                "finished_on": "2022",
                "description": "Built things.\nKEY ACCOMPLISHMENTS\n- Led team of 5\n- Reduced build time by 40%",
            }
        ],
        "education_history": [
            {
                "school_name": "MIT",
                "degree_name": "BS",
                "field_of_study": "Computer Science",
                "started_on": "2010",
                "finished_on": "2014",
            }
        ],
        "skills_and_endorsements": [
            {"skill": "Python", "endorsements_count": 50},
            {"name": "Java", "endorsement_count": 30},
            {"skill": "Kubernetes", "endorsements_count": 0},
        ],
        "recommendations_received": [
            {
                "author_first_name": "Bob",
                "author_last_name": "Smith",
                "author_job_title": "CTO at Acme",
                "text": "Jane is an exceptional engineer.",
            }
        ],
    }


# ---------------------------------------------------------------------------
# extract_accomplishments tests
# ---------------------------------------------------------------------------
class TestExtractAccomplishments:
    def test_extracts_bullet_points_after_header(self):
        text = "Some intro.\nKEY ACCOMPLISHMENTS\n- Led migration project\n- Saved $2M annually"
        result = extract_accomplishments(text)
        assert len(result) == 2
        assert "Led migration project" in result
        assert "Saved $2M annually" in result

    def test_empty_input_returns_empty(self):
        assert extract_accomplishments("") == []
        assert extract_accomplishments(None) == []

    def test_no_accomplishments_header(self):
        text = "Senior Engineer at Acme Corp.\n- Built APIs\n- Managed team"
        result = extract_accomplishments(text)
        # Bullets exist but no KEY ACCOMPLISHMENTS header — should still extract bullets
        assert len(result) == 2

    def test_various_bullet_characters(self):
        text = "KEY ACCOMPLISHMENTS\n• Bullet one\n▪ Bullet two\n— Bullet three"
        result = extract_accomplishments(text)
        assert len(result) == 3
        assert "Bullet one" in result

    def test_stops_at_non_bullet_after_section(self):
        text = (
            "KEY ACCOMPLISHMENTS\n"
            "- First accomplishment\n"
            "- Second accomplishment\n"
            "Some other text that's not a bullet\n"
            "- This should NOT be included"
        )
        result = extract_accomplishments(text)
        assert len(result) == 2

    def test_case_insensitive_header(self):
        text = "key accomplishments\n- Item one"
        result = extract_accomplishments(text)
        assert len(result) == 1

    def test_skips_empty_bullets(self):
        text = "KEY ACCOMPLISHMENTS\n- \n- Real accomplishment\n-  "
        result = extract_accomplishments(text)
        assert len(result) == 1
        assert "Real accomplishment" in result

    def test_handles_carriage_returns(self):
        text = "KEY ACCOMPLISHMENTS\r\n- Windows line ending\r\n- Another one"
        result = extract_accomplishments(text)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# parse_linkedin_json tests (from dict)
# ---------------------------------------------------------------------------
class TestParseLinkedInJson:
    def test_core_fields_extracted(self, minimal_profile):
        result = parse_linkedin_json(minimal_profile)
        assert result["name"] == "Jane Doe"
        assert result["headline"] == "Software Engineer"
        assert result["summary"] == "Experienced developer."
        assert result["contact"]["email"] == "jane@example.com"

    def test_current_job_has_present_end_date(self, minimal_profile):
        result = parse_linkedin_json(minimal_profile)
        current = result["experience"][0]
        assert current["title"] == "Staff Engineer"
        assert current["company"] == "Acme Corp"
        assert current["end_date"] == "Present"

    def test_previous_jobs_included(self, minimal_profile):
        result = parse_linkedin_json(minimal_profile)
        assert len(result["experience"]) == 2
        prev = result["experience"][1]
        assert prev["title"] == "Senior Dev"
        assert prev["start_date"] == "2018"
        assert prev["end_date"] == "2022"

    def test_accomplishments_extracted_from_description(self, minimal_profile):
        result = parse_linkedin_json(minimal_profile)
        prev = result["experience"][1]
        assert len(prev["accomplishments"]) == 2
        assert "Led team of 5" in prev["accomplishments"]

    def test_education_extracted(self, minimal_profile):
        result = parse_linkedin_json(minimal_profile)
        assert len(result["education"]) == 1
        edu = result["education"][0]
        assert edu["school"] == "MIT"
        assert edu["degree"] == "BS"
        assert edu["field"] == "Computer Science"

    def test_skills_with_endorsements_preserved(self, minimal_profile):
        result = parse_linkedin_json(minimal_profile)
        assert len(result["skills"]) == 3
        python_skill = next(s for s in result["skills"] if s["name"] == "Python")
        assert python_skill["endorsements"] == 50

    def test_dual_skill_field_names(self, minimal_profile):
        """Both 'skill'/'endorsements_count' and 'name'/'endorsement_count' formats work."""
        result = parse_linkedin_json(minimal_profile)
        java_skill = next(s for s in result["skills"] if s["name"] == "Java")
        assert java_skill["endorsements"] == 30

    def test_zero_endorsement_skills_included(self, minimal_profile):
        result = parse_linkedin_json(minimal_profile)
        k8s = next(s for s in result["skills"] if s["name"] == "Kubernetes")
        assert k8s["endorsements"] == 0

    def test_recommendations_extraction(self, minimal_profile):
        result = parse_linkedin_json(minimal_profile)
        assert len(result["recommendations"]) == 1
        rec = result["recommendations"][0]
        assert rec["author"] == "Bob Smith"
        assert rec["author_title"] == "CTO at Acme"
        assert "exceptional" in rec["text"]

    def test_missing_fields_graceful_defaults(self):
        result = parse_linkedin_json({})
        assert result["name"] == ""
        assert result["experience"] == []
        assert result["skills"] == []
        assert result["education"] == []
        assert result["recommendations"] == []

    def test_no_current_job(self):
        data = {"previous_jobs": [{"title": "Dev", "company": "Co"}]}
        result = parse_linkedin_json(data)
        assert len(result["experience"]) == 1

    def test_from_file_path(self, minimal_profile):
        """parse_linkedin_json accepts a file path string."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(minimal_profile, f)
            path = f.name
        try:
            result = parse_linkedin_json(path)
            assert result["name"] == "Jane Doe"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Tests against real LinkedIn profile data
# ---------------------------------------------------------------------------
class TestRealLinkedInProfile:
    def test_real_profile_parses(self, real_profile):
        result = parse_linkedin_json(real_profile)
        assert result["name"]  # Non-empty name
        assert len(result["skills"]) > 10  # Real profile has 70+ skills
        assert len(result["experience"]) >= 1

    def test_real_profile_skills_have_endorsements(self, real_profile):
        result = parse_linkedin_json(real_profile)
        endorsed = [s for s in result["skills"] if s["endorsements"] > 0]
        assert len(endorsed) > 5  # Real profile has many endorsed skills

    def test_real_profile_education_present(self, real_profile):
        result = parse_linkedin_json(real_profile)
        assert len(result["education"]) >= 2  # Stevens + USMMA
