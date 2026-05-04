"""NLP pipeline + optimization correctness tests — pure function tests.

No Flask client, no HTTP routes. Tests scoring engine, keyword extraction,
and optimization pipeline directly via module imports.
"""

import pytest
from test_helpers import JD_TEXT, LINKEDIN_PROFILE, RESUME_TEXT

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def high_match_resume_data():
    """Resume data dict that closely matches the JD."""
    from nlp_engine import extract_keywords

    return {
        "text": RESUME_TEXT,
        "skills": extract_keywords(RESUME_TEXT, num_keywords=30),
    }


@pytest.fixture()
def zero_match_resume_data():
    """Resume text with zero overlap to the tech JD."""
    text = (
        "JANE DOE\nPastry Chef | 15 Years in Fine Dining\n\n"
        "SUMMARY\nPassionate culinary artist specializing in French pastry and "
        "artisan bread. Led kitchen teams of 8 at three Michelin-starred restaurants.\n\n"
        "EXPERIENCE\nHead Pastry Chef — Le Grand Restaurant (2015-Present)\n"
        "- Created seasonal dessert menus increasing guest satisfaction by 40%\n"
        "- Trained junior pastry cooks in laminated dough techniques\n\n"
        "EDUCATION\nCulinary Arts Diploma — Le Cordon Bleu\n"
    )
    return {"text": text, "skills": ["pastry", "baking", "french cuisine"]}


@pytest.fixture()
def job_keywords():
    from nlp_engine import extract_keywords

    return extract_keywords(JD_TEXT, num_keywords=30)


# ---------------------------------------------------------------------------
# Scoring discrimination
# ---------------------------------------------------------------------------


class TestScoringDiscrimination:

    def test_high_match_score_above_60(self, high_match_resume_data, job_keywords):
        """Well-matched resume gets score >= 60 with valid breakdown values."""
        from utils import optimize_resume

        result = optimize_resume(
            high_match_resume_data,
            job_keywords,
            job_text=JD_TEXT,
            linkedin_profile=LINKEDIN_PROFILE,
        )
        assert result["score"] >= 60, f"Score {result['score']} too low for a well-matched resume"
        bd = result["score_breakdown"]
        for key in (
            "keyword_coverage",
            "semantic_similarity",
            "skills_match",
            "section_completeness",
        ):
            assert isinstance(bd[key], (int, float)), f"{key} must be numeric"
            assert 0.0 <= bd[key] <= 100.0, f"{key}={bd[key]} outside [0,100]"
        assert bd["keyword_coverage"] > 10.0, f"keyword_coverage={bd['keyword_coverage']} too low"
        assert bd["skills_match"] > 5.0, f"skills_match={bd['skills_match']} too low"

    def test_zero_match_score_below_30(self, zero_match_resume_data, job_keywords):
        """Unrelated resume gets score <= 30 with low breakdown values."""
        from utils import optimize_resume

        result = optimize_resume(
            zero_match_resume_data,
            job_keywords,
            job_text=JD_TEXT,
        )
        assert (
            result["score"] <= 30
        ), f"Score {result['score']} too high for a pastry chef vs architect JD"
        bd = result["score_breakdown"]
        assert bd["keyword_coverage"] < 20.0
        assert bd["skills_match"] < 15.0

    def test_score_breakdown_has_four_components(self, high_match_resume_data, job_keywords):
        """Score breakdown contains all 4 signal components."""
        from utils import optimize_resume

        result = optimize_resume(
            high_match_resume_data,
            job_keywords,
            job_text=JD_TEXT,
        )
        breakdown = result["score_breakdown"]
        assert "keyword_coverage" in breakdown
        assert "semantic_similarity" in breakdown
        assert "skills_match" in breakdown
        assert "section_completeness" in breakdown


# ---------------------------------------------------------------------------
# Content preservation and enhancement
# ---------------------------------------------------------------------------


class TestContentQuality:

    def test_optimized_text_preserves_top_linkedin_skills(
        self, high_match_resume_data, job_keywords
    ):
        """Optimized text mentions at least 5 of the top-10 LinkedIn skills."""
        from utils import optimize_resume

        result = optimize_resume(
            high_match_resume_data,
            job_keywords,
            job_text=JD_TEXT,
            linkedin_profile=LINKEDIN_PROFILE,
        )
        top_skills = [
            s["skill"].lower()
            for s in sorted(
                LINKEDIN_PROFILE["skills_and_endorsements"],
                key=lambda x: x["endorsements_count"],
                reverse=True,
            )[:10]
        ]
        optimized_lower = result["optimized_text"].lower()
        found = sum(1 for skill in top_skills if skill in optimized_lower)
        assert found >= 5, f"Only {found}/10 top LinkedIn skills found"

    def test_added_keywords_include_jd_terms(self, high_match_resume_data, job_keywords):
        """added_keywords includes terms from JD not in original resume."""
        from utils import optimize_resume

        result = optimize_resume(
            high_match_resume_data,
            job_keywords,
            job_text=JD_TEXT,
        )
        added = [kw.lower() for kw in result["added_keywords"]]
        assert all(isinstance(kw, str) and len(kw) > 0 for kw in result["added_keywords"])
        jd_lower = JD_TEXT.lower()
        jd_sourced = [kw for kw in added if kw in jd_lower]
        assert len(jd_sourced) >= 1, "added_keywords should include JD-sourced terms"
        resume_lower = RESUME_TEXT.lower()
        not_in_resume = [kw for kw in added if kw not in resume_lower]
        assert len(not_in_resume) >= 1

    def test_matching_keywords_list_common_terms(self, high_match_resume_data, job_keywords):
        """matching_keywords has at least 1 term present in both resume and JD."""
        from utils import optimize_resume

        result = optimize_resume(
            high_match_resume_data,
            job_keywords,
            job_text=JD_TEXT,
        )
        matching = result["matching_keywords"]
        assert len(matching) >= 1
        resume_lower = RESUME_TEXT.lower()
        jd_lower = JD_TEXT.lower()
        combined = resume_lower + " " + jd_lower
        for kw in matching[:5]:
            words = kw.lower().split()
            found = any(w in combined for w in words)
            assert found, f"No word from matching keyword '{kw}' found in resume or JD"
        added_set = {kw.lower() for kw in result["added_keywords"]}
        matching_set = {kw.lower() for kw in matching}
        overlap = matching_set & added_set
        assert len(overlap) <= len(matching_set) * 0.5


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------


class TestSectionDetection:

    def test_section_completeness_detects_all_four(self, high_match_resume_data, job_keywords):
        """SUMMARY, EXPERIENCE, EDUCATION, SKILLS all detected."""
        from utils import optimize_resume

        result = optimize_resume(
            high_match_resume_data,
            job_keywords,
            job_text=JD_TEXT,
        )
        sections = result["sections_found"]
        assert sections["summary"] is True
        assert sections["experience"] is True
        assert sections["education"] is True
        assert sections["skills"] is True


# ---------------------------------------------------------------------------
# NLP keyword extraction
# ---------------------------------------------------------------------------


class TestNLPKeywordExtraction:

    def test_extract_keywords_from_jd(self):
        """extract_keywords(JD_TEXT) returns key tech terms from the JD."""
        from nlp_engine import extract_keywords

        keywords = extract_keywords(JD_TEXT, num_keywords=50)
        assert len(keywords) >= 5
        assert all(isinstance(kw, str) and len(kw.strip()) > 0 for kw in keywords)
        keywords_lower = [kw.lower() for kw in keywords]
        all_kw_text = " ".join(keywords_lower)
        assert "python" in all_kw_text
        assert "docker" in all_kw_text or "kubernete" in all_kw_text
        assert "architecture" in all_kw_text or "microservice" in all_kw_text
        assert all(len(kw) <= 50 for kw in keywords)

    def test_extract_keywords_empty_input(self):
        """Empty input returns empty list."""
        from nlp_engine import extract_keywords

        assert extract_keywords("") == []
        assert extract_keywords("   ") == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:

    def test_optimize_empty_resume_text(self, job_keywords):
        """Empty resume text returns valid structure with low score."""
        from utils import optimize_resume

        result = optimize_resume(
            {"text": "", "skills": []},
            job_keywords,
            job_text=JD_TEXT,
        )
        assert isinstance(result["score"], (int, float))
        assert result["score"] <= 30
        assert isinstance(result["optimized_text"], str)
        assert isinstance(result["added_keywords"], list)
        assert isinstance(result["matching_keywords"], list)

    def test_optimize_preserves_original_resume(self, high_match_resume_data, job_keywords):
        """Optimization does not mutate the input dict."""
        from utils import optimize_resume

        original_text = high_match_resume_data["text"]
        original_skills = list(high_match_resume_data["skills"])
        optimize_resume(high_match_resume_data, job_keywords, job_text=JD_TEXT)
        assert high_match_resume_data["text"] == original_text
        assert high_match_resume_data["skills"] == original_skills

    def test_score_breakdown_components_sum_meaningful(self, high_match_resume_data, job_keywords):
        """Weighted breakdown components contribute proportionally."""
        from utils import optimize_resume

        result = optimize_resume(
            high_match_resume_data,
            job_keywords,
            job_text=JD_TEXT,
        )
        bd = result["score_breakdown"]
        nonzero = sum(1 for v in bd.values() if v > 0.0)
        assert nonzero >= 3
        assert 0 <= result["score"] <= 100

    def test_keywords_are_deduplicated(self, high_match_resume_data, job_keywords):
        """matching_keywords and added_keywords have no duplicates."""
        from utils import optimize_resume

        result = optimize_resume(
            high_match_resume_data,
            job_keywords,
            job_text=JD_TEXT,
        )
        matching = result["matching_keywords"]
        added = result["added_keywords"]
        assert len(matching) == len(set(kw.lower() for kw in matching))
        assert len(added) == len(set(kw.lower() for kw in added))

    def test_extract_keywords_num_keywords_limits_output(self):
        """num_keywords parameter caps the output."""
        from nlp_engine import extract_keywords

        kw5 = extract_keywords(JD_TEXT, num_keywords=5)
        kw20 = extract_keywords(JD_TEXT, num_keywords=20)
        assert len(kw5) <= 5
        assert len(kw20) <= 20
        assert len(kw20) >= len(kw5)
