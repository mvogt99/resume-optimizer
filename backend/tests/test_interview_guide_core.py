"""Tests for interview_guide.py — persona generation, STAR examples, talking points.

Pure function tests (no Flask client, no LLM). Uses real spaCy NLP.
"""

import pytest
from test_helpers import JD_TEXT, LINKEDIN_PROFILE, RESUME_TEXT

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def resume_data():
    from nlp_engine import extract_keywords

    return {
        "text": RESUME_TEXT,
        "skills": extract_keywords(RESUME_TEXT, num_keywords=30),
        "experience": [
            {
                "title": "Senior Enterprise Architect",
                "company": "Navitus Health Solutions",
                "description": "Led microservices migration",
                "accomplishments": [
                    "Reduced deployment time by 60% through CI/CD pipeline redesign",
                    "Managed team of 12 engineers",
                ],
            },
            {
                "title": "Solutions Architect",
                "company": "OPI",
                "description": "Designed cloud infrastructure",
                "accomplishments": ["Migrated 50 services to AWS"],
            },
        ],
    }


@pytest.fixture()
def non_technical_jd():
    return (
        "Project Manager — Global Consulting Firm\n\n"
        "We're looking for a senior project manager with 10+ years of experience "
        "in client-facing consulting. Must have strong communication, leadership, "
        "and stakeholder management skills. PMP certification preferred. "
        "Experience with agile methodologies and budget management required. "
        "Travel up to 25%. Competitive salary and benefits."
    )


# ---------------------------------------------------------------------------
# generate_interview_guide — full pipeline
# ---------------------------------------------------------------------------


class TestGenerateInterviewGuide:
    def test_guide_has_required_keys(self, resume_data):
        from interview_guide import generate_interview_guide

        guide = generate_interview_guide(resume_data, JD_TEXT)
        assert "interview_personas" in guide
        assert "star_examples" in guide
        assert "talking_points" in guide
        assert "key_skills_to_highlight" in guide
        assert "skills_gaps_to_address" in guide
        assert "response_framework" in guide

    def test_response_framework_star_method(self, resume_data):
        from interview_guide import generate_interview_guide

        guide = generate_interview_guide(resume_data, JD_TEXT)
        star = guide["response_framework"]["star_method"]
        assert "situation" in star
        assert "task" in star
        assert "action" in star
        assert "result" in star

    def test_technical_jd_produces_three_personas(self, resume_data):
        from interview_guide import generate_interview_guide

        guide = generate_interview_guide(resume_data, JD_TEXT)
        personas = guide["interview_personas"]
        assert len(personas) == 3
        names = [p["persona"] for p in personas]
        assert "HR / Recruiter" in names
        assert "Hiring Manager" in names
        assert "Technical Interviewer" in names

    def test_non_technical_jd_produces_two_personas(self, resume_data, non_technical_jd):
        from interview_guide import generate_interview_guide

        guide = generate_interview_guide(resume_data, non_technical_jd)
        personas = guide["interview_personas"]
        assert len(personas) == 2
        names = [p["persona"] for p in personas]
        assert "Technical Interviewer" not in names

    def test_matching_skills_populated(self, resume_data):
        from interview_guide import generate_interview_guide

        guide = generate_interview_guide(resume_data, JD_TEXT)
        highlights = guide["key_skills_to_highlight"]
        assert isinstance(highlights, list)
        assert len(highlights) <= 10

    def test_skills_gaps_populated(self, resume_data):
        from interview_guide import generate_interview_guide

        guide = generate_interview_guide(resume_data, JD_TEXT)
        gaps = guide["skills_gaps_to_address"]
        assert isinstance(gaps, list)
        assert len(gaps) <= 5

    def test_with_linkedin_profile(self, resume_data):
        from interview_guide import generate_interview_guide

        guide = generate_interview_guide(resume_data, JD_TEXT, linkedin_profile=LINKEDIN_PROFILE)
        assert len(guide["star_examples"]) >= 1
        assert len(guide["interview_personas"]) >= 2


# ---------------------------------------------------------------------------
# _build_personas
# ---------------------------------------------------------------------------


class TestBuildPersonas:
    def test_hr_persona_always_first(self):
        from interview_guide import _build_personas

        personas = _build_personas(JD_TEXT, ["python", "aws"], ["python"], ["aws"])
        assert personas[0]["persona"] == "HR / Recruiter"
        assert "focus" in personas[0]
        assert "questions" in personas[0]
        assert "tips" in personas[0]

    def test_hr_questions_count(self):
        from interview_guide import _build_personas

        personas = _build_personas(JD_TEXT, ["python"], [], [])
        hr = personas[0]
        assert len(hr["questions"]) == 5
        assert len(hr["tips"]) >= 3

    def test_senior_hiring_manager_focus(self):
        from interview_guide import _build_personas

        jd = "Senior Solutions Architect — lead teams, design systems, mentor engineers"
        personas = _build_personas(jd, ["architect"], [], [])
        hm = [p for p in personas if p["persona"] == "Hiring Manager"][0]
        assert "Leadership" in hm["focus"] or "impact" in hm["focus"]

    def test_junior_hiring_manager_focus(self):
        from interview_guide import _build_personas

        jd = "Entry-level data analyst. Join our team and learn."
        personas = _build_personas(jd, ["data"], [], [])
        hm = [p for p in personas if p["persona"] == "Hiring Manager"][0]
        assert "growth" in hm["focus"] or "Problem" in hm["focus"]

    def test_technical_persona_has_tech_questions(self):
        from interview_guide import _build_personas

        personas = _build_personas(JD_TEXT, ["python", "docker", "aws"], ["python"], ["docker"])
        tech = [p for p in personas if p["persona"] == "Technical Interviewer"]
        assert len(tech) == 1
        assert "Technical depth" in tech[0]["focus"]
        assert len(tech[0]["questions"]) == 5

    def test_matching_skills_in_hr_tips(self):
        from interview_guide import _build_personas

        personas = _build_personas(JD_TEXT, ["python", "docker"], ["python", "docker"], [])
        hr = personas[0]
        tips_text = " ".join(hr["tips"])
        assert "python" in tips_text.lower() or "docker" in tips_text.lower()


# ---------------------------------------------------------------------------
# _build_star_examples
# ---------------------------------------------------------------------------


class TestBuildStarExamples:
    def test_examples_from_experience(self):
        from interview_guide import _build_star_examples

        experience = [
            {"title": "Architect", "company": "ACME", "description": "Built systems"},
        ]
        examples = _build_star_examples(experience)
        assert len(examples) == 1
        assert "Architect" in examples[0]["role"]
        assert "ACME" in examples[0]["role"]
        assert "situation" in examples[0]
        assert "suggested_focus" in examples[0]

    def test_examples_with_linkedin(self):
        from interview_guide import _build_star_examples

        experience = [
            {"title": "Dev", "company": "A", "description": "Coded"},
        ]
        examples = _build_star_examples(experience, linkedin_profile=LINKEDIN_PROFILE)
        assert len(examples) >= 1
        roles = [e["role"] for e in examples]
        # LinkedIn profile adds Navitus roles
        assert any("Dev" in r for r in roles)

    def test_max_five_examples(self):
        from interview_guide import _build_star_examples

        experience = [
            {"title": f"Role {i}", "company": f"Co {i}", "description": "Work"} for i in range(10)
        ]
        examples = _build_star_examples(experience)
        assert len(examples) == 5

    def test_empty_experience(self):
        from interview_guide import _build_star_examples

        examples = _build_star_examples([])
        assert examples == []

    def test_quantified_accomplishment_preferred(self):
        from interview_guide import _build_star_examples

        experience = [
            {
                "title": "Lead",
                "company": "Corp",
                "description": "Led team",
                "accomplishments": [
                    "Improved team morale",
                    "Reduced deployment failures by 45% saving $200k annually",
                ],
            },
        ]
        examples = _build_star_examples(experience)
        assert "45%" in examples[0]["suggested_focus"] or "200k" in examples[0]["suggested_focus"]

    def test_deduplicates_same_title_company(self):
        from interview_guide import _build_star_examples

        experience = [
            {"title": "Dev", "company": "A", "description": "First"},
            {"title": "Dev", "company": "A", "description": "Duplicate"},
        ]
        examples = _build_star_examples(experience)
        assert len(examples) == 1


# ---------------------------------------------------------------------------
# _build_talking_points
# ---------------------------------------------------------------------------


class TestBuildTalkingPoints:
    def test_skill_alignment_topic(self):
        from interview_guide import _build_talking_points

        points = _build_talking_points(["python", "aws"], [], [], [])
        topics = [p["topic"] for p in points]
        assert "Skill Alignment" in topics
        alignment = [p for p in points if p["topic"] == "Skill Alignment"][0]
        assert "python" in alignment["point"].lower() or "aws" in alignment["point"].lower()
        assert "advice" in alignment

    def test_addressing_gaps_topic(self):
        from interview_guide import _build_talking_points

        points = _build_talking_points([], ["terraform", "kafka"], [], [])
        topics = [p["topic"] for p in points]
        assert "Addressing Gaps" in topics
        gap_point = [p for p in points if p["topic"] == "Addressing Gaps"][0]
        assert "terraform" in gap_point["point"].lower() or "kafka" in gap_point["point"].lower()

    def test_experience_depth_topic(self):
        from interview_guide import _build_talking_points

        exp = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
        points = _build_talking_points([], [], exp, [])
        topics = [p["topic"] for p in points]
        assert "Experience Depth" in topics
        depth = [p for p in points if p["topic"] == "Experience Depth"][0]
        assert "3" in depth["point"]

    def test_company_research_topic(self):
        from interview_guide import _build_talking_points

        points = _build_talking_points([], [], [], ["Google", "Microsoft"])
        topics = [p["topic"] for p in points]
        assert "Company Research" in topics
        research = [p for p in points if p["topic"] == "Company Research"][0]
        assert "Google" in research["point"]

    def test_all_topics_present(self):
        from interview_guide import _build_talking_points

        points = _build_talking_points(["python"], ["rust"], [{"title": "Dev"}], ["TechCo"])
        topics = [p["topic"] for p in points]
        assert len(topics) == 4
        assert "Skill Alignment" in topics
        assert "Addressing Gaps" in topics
        assert "Experience Depth" in topics
        assert "Company Research" in topics

    def test_empty_inputs(self):
        from interview_guide import _build_talking_points

        points = _build_talking_points([], [], [], [])
        assert points == []

    def test_each_point_has_required_fields(self):
        from interview_guide import _build_talking_points

        points = _build_talking_points(["python"], ["rust"], [{"title": "Dev"}], ["X"])
        for point in points:
            assert "topic" in point
            assert "point" in point
            assert "advice" in point
            assert isinstance(point["topic"], str)
            assert isinstance(point["point"], str)
            assert isinstance(point["advice"], str)
