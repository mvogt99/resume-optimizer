"""Core tests for nlp_engine.py — keyword extraction, skill phrases, similarity, entity extraction."""

import pytest
from test_helpers import JD_TEXT, RESUME_TEXT

# ---------------------------------------------------------------------------
# extract_keywords
# ---------------------------------------------------------------------------


class TestExtractKeywords:
    """Tests for extract_keywords() with real spaCy processing."""

    def test_returns_list(self):
        from nlp_engine import extract_keywords

        result = extract_keywords("Python developer with AWS experience")
        assert isinstance(result, list)

    def test_empty_input_returns_empty(self):
        from nlp_engine import extract_keywords

        assert extract_keywords("") == []
        assert extract_keywords(None) == []
        assert extract_keywords("   ") == []

    def test_extracts_relevant_keywords(self):
        from nlp_engine import extract_keywords

        result = extract_keywords(
            "Senior Python developer with 10 years of experience in AWS, "
            "Docker, and Kubernetes. Expert in microservices architecture."
        )
        # Should find technical terms
        result_lower = [k.lower() for k in result]
        found_tech = any(
            term in " ".join(result_lower)
            for term in ["python", "docker", "kubernetes", "microservice"]
        )
        assert found_tech, f"Expected technical keywords, got: {result}"

    def test_respects_num_keywords_limit(self):
        from nlp_engine import extract_keywords

        result = extract_keywords(RESUME_TEXT, num_keywords=5)
        assert len(result) <= 5

    def test_filters_stopwords(self):
        from nlp_engine import extract_keywords

        result = extract_keywords("The quick brown fox jumps over the lazy dog with Python skills")
        result_lower = [k.lower() for k in result]
        # Common stopwords should not appear as standalone
        assert "the" not in result_lower
        assert "over" not in result_lower

    def test_includes_bigrams_and_trigrams(self):
        from nlp_engine import extract_keywords

        result = extract_keywords(
            "Machine learning engineer with deep learning experience "
            "and natural language processing skills"
        )
        joined = " ".join(result)
        # Multi-word phrases should appear
        has_multiword = any(" " in kw for kw in result)
        assert has_multiword or "machine" in joined.lower(), f"Expected phrases, got: {result}"

    def test_resume_text_yields_substantial_keywords(self):
        from nlp_engine import extract_keywords

        result = extract_keywords(RESUME_TEXT, num_keywords=30)
        assert len(result) >= 10, f"Expected >=10 keywords from resume, got {len(result)}"

    def test_lemmatization_normalizes_words(self):
        from nlp_engine import extract_keywords

        result = extract_keywords(
            "Designing distributed systems. Designed multiple architectures. "
            "The designer implemented solutions."
        )
        # Lemmatization should produce base forms
        result_lower = [k.lower() for k in result]
        # "designing", "designed", "designer" should all map to "design"
        has_design = any("design" in k for k in result_lower)
        assert has_design, f"Expected lemmatized 'design', got: {result}"


# ---------------------------------------------------------------------------
# extract_skill_phrases
# ---------------------------------------------------------------------------


class TestExtractSkillPhrases:
    """Tests for extract_skill_phrases() with curated vocab matching."""

    def test_returns_sorted_list(self):
        from nlp_engine import extract_skill_phrases

        result = extract_skill_phrases("Python and Docker experience")
        assert isinstance(result, list)
        assert result == sorted(result)

    def test_empty_input(self):
        from nlp_engine import extract_skill_phrases

        assert extract_skill_phrases("") == []
        assert extract_skill_phrases(None) == []

    def test_finds_single_word_skills(self):
        from nlp_engine import extract_skill_phrases

        result = extract_skill_phrases("Expert in Python, Java, and Docker containerization")
        assert "python" in result
        assert "java" in result
        assert "docker" in result

    def test_finds_multi_word_skills(self):
        from nlp_engine import extract_skill_phrases

        result = extract_skill_phrases(
            "Experience with machine learning, natural language processing, "
            "and infrastructure as code"
        )
        assert "machine learning" in result
        assert "natural language processing" in result

    def test_finds_cloud_providers(self):
        from nlp_engine import extract_skill_phrases

        result = extract_skill_phrases("Deployed on AWS and Azure with Kubernetes orchestration")
        assert "aws" in result
        assert "azure" in result
        assert "kubernetes" in result

    def test_case_insensitive(self):
        from nlp_engine import extract_skill_phrases

        result = extract_skill_phrases("PYTHON and DOCKER and AWS")
        assert "python" in result
        assert "docker" in result

    def test_resume_text_yields_many_skills(self):
        from nlp_engine import extract_skill_phrases

        result = extract_skill_phrases(RESUME_TEXT)
        assert len(result) >= 5, f"Expected >=5 skills from resume, got {len(result)}: {result}"

    def test_jd_text_yields_relevant_skills(self):
        from nlp_engine import extract_skill_phrases

        result = extract_skill_phrases(JD_TEXT)
        assert len(result) >= 3
        # JD mentions Python, AWS, Docker, Kubernetes
        result_set = set(result)
        assert "python" in result_set or "aws" in result_set

    def test_ambiguous_words_need_context(self):
        from nlp_engine import extract_skill_phrases

        # "go" alone without tech context should not match
        result = extract_skill_phrases("I want to go to the store")
        assert "go" not in result

    def test_ambiguous_words_with_tech_context(self):
        from nlp_engine import extract_skill_phrases

        # "lean" in tech context: "lean methodology" is in vocab and "lean" is ambiguous
        result = extract_skill_phrases(
            "Applied lean methodology and lean six sigma principles to optimize delivery"
        )
        assert "lean methodology" in result

    def test_governance_skills(self):
        from nlp_engine import extract_skill_phrases

        result = extract_skill_phrases(
            "HIPAA compliance and GDPR data governance with SOX compliance requirements"
        )
        assert "hipaa" in result
        assert "gdpr" in result

    def test_methodology_skills(self):
        from nlp_engine import extract_skill_phrases

        result = extract_skill_phrases(
            "Experienced in agile scrum methodology with CI/CD pipelines"
        )
        assert "agile" in result
        assert "scrum" in result


# ---------------------------------------------------------------------------
# extract_entities
# ---------------------------------------------------------------------------


class TestExtractEntities:
    """Tests for extract_entities() — named entity recognition."""

    def test_returns_list_of_tuples(self):
        from nlp_engine import extract_entities

        result = extract_entities("Mike works at Google in California")
        assert isinstance(result, list)
        if result:
            assert isinstance(result[0], tuple)
            assert len(result[0]) == 2

    def test_finds_organization_entities(self):
        from nlp_engine import extract_entities

        result = extract_entities("I worked at Microsoft and Google for 10 years")
        org_names = [ent[0] for ent in result if ent[1] == "ORG"]
        org_text = " ".join(org_names).lower()
        assert "microsoft" in org_text or "google" in org_text

    def test_empty_input(self):
        from nlp_engine import extract_entities

        result = extract_entities("")
        assert result == [] or result is not None


# ---------------------------------------------------------------------------
# calculate_similarity
# ---------------------------------------------------------------------------


class TestCalculateSimilarity:
    """Tests for calculate_similarity() — semantic text comparison."""

    def test_identical_texts_high_similarity(self):
        from nlp_engine import calculate_similarity

        score = calculate_similarity("Python developer", "Python developer")
        assert score >= 0.9, f"Identical texts should have high similarity, got {score}"

    def test_empty_text_returns_zero(self):
        from nlp_engine import calculate_similarity

        assert calculate_similarity("", "Python") == 0.0
        assert calculate_similarity("Python", "") == 0.0
        assert calculate_similarity("", "") == 0.0
        assert calculate_similarity(None, "test") == 0.0

    def test_similar_texts_moderate_score(self):
        from nlp_engine import calculate_similarity

        score = calculate_similarity(
            "Python developer with AWS experience",
            "Software engineer using Python and Amazon Web Services",
        )
        assert 0.3 <= score <= 1.0, f"Similar texts should score 0.3-1.0, got {score}"

    def test_unrelated_texts_low_score(self):
        from nlp_engine import calculate_similarity

        score = calculate_similarity(
            "Python developer with AWS experience",
            "French pastry chef specializing in croissants and sourdough bread",
        )
        assert score < 0.7, f"Unrelated texts should score low, got {score}"

    def test_returns_float(self):
        from nlp_engine import calculate_similarity

        score = calculate_similarity("hello world", "hello planet")
        assert isinstance(score, float)

    def test_score_between_zero_and_one(self):
        from nlp_engine import calculate_similarity

        score = calculate_similarity(RESUME_TEXT[:200], JD_TEXT[:200])
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# analyze_resume_vs_job
# ---------------------------------------------------------------------------


class TestAnalyzeResumeVsJob:
    """Tests for analyze_resume_vs_job() — full resume-JD comparison."""

    def test_returns_expected_keys(self):
        from nlp_engine import analyze_resume_vs_job

        result = analyze_resume_vs_job(RESUME_TEXT, JD_TEXT)
        assert "match_score" in result
        assert "resume_keywords" in result
        assert "job_keywords" in result
        assert "matching_keywords" in result
        assert "missing_keywords" in result
        assert "additional_keywords" in result

    def test_match_score_is_numeric(self):
        from nlp_engine import analyze_resume_vs_job

        result = analyze_resume_vs_job(RESUME_TEXT, JD_TEXT)
        assert isinstance(result["match_score"], (int, float))
        assert 0 <= result["match_score"] <= 100

    def test_matching_keywords_not_empty(self):
        from nlp_engine import analyze_resume_vs_job

        result = analyze_resume_vs_job(RESUME_TEXT, JD_TEXT)
        assert len(result["matching_keywords"]) > 0, "Resume and JD should share keywords"

    def test_keywords_are_sorted(self):
        from nlp_engine import analyze_resume_vs_job

        result = analyze_resume_vs_job(RESUME_TEXT, JD_TEXT)
        assert result["matching_keywords"] == sorted(result["matching_keywords"])
        assert result["missing_keywords"] == sorted(result["missing_keywords"])

    def test_perfect_match_high_score(self):
        from nlp_engine import analyze_resume_vs_job

        text = "Python AWS Docker Kubernetes microservices"
        result = analyze_resume_vs_job(text, text)
        assert (
            result["match_score"] >= 50
        ), f"Self-comparison should score high, got {result['match_score']}"

    def test_no_overlap_low_score(self):
        from nlp_engine import analyze_resume_vs_job

        result = analyze_resume_vs_job(
            "French cooking pastry baking sourdough",
            "Python AWS Docker Kubernetes microservices",
        )
        assert result["match_score"] < 30

    def test_resume_keywords_list(self):
        from nlp_engine import analyze_resume_vs_job

        result = analyze_resume_vs_job(RESUME_TEXT, JD_TEXT)
        assert isinstance(result["resume_keywords"], list)
        assert len(result["resume_keywords"]) > 0


# ---------------------------------------------------------------------------
# TECH_SKILLS_VOCAB
# ---------------------------------------------------------------------------


class TestTechSkillsVocab:
    """Tests for the curated tech skills vocabulary."""

    def test_vocab_is_set(self):
        from nlp_engine import TECH_SKILLS_VOCAB

        assert isinstance(TECH_SKILLS_VOCAB, set)

    def test_vocab_has_substantial_entries(self):
        from nlp_engine import TECH_SKILLS_VOCAB

        assert len(TECH_SKILLS_VOCAB) >= 100

    def test_vocab_all_lowercase(self):
        from nlp_engine import TECH_SKILLS_VOCAB

        for skill in TECH_SKILLS_VOCAB:
            assert skill == skill.lower(), f"Vocab entry '{skill}' should be lowercase"

    def test_contains_common_languages(self):
        from nlp_engine import TECH_SKILLS_VOCAB

        for lang in ["python", "java", "javascript", "typescript"]:
            assert lang in TECH_SKILLS_VOCAB

    def test_contains_cloud_providers(self):
        from nlp_engine import TECH_SKILLS_VOCAB

        for cloud in ["aws", "azure", "gcp"]:
            assert cloud in TECH_SKILLS_VOCAB
