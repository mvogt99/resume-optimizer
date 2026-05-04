"""Tests for LLM extractor modules — real RTX 5090 calls, no mocks.

Covers:
- technical_extractor.extract_technical_picture
- governance_extractor.extract_governance_picture
- role_extractor.extract_role_picture
- skills_extractor.extract_all_skills
- skills_outcomes_extractor.extract_skills_and_outcomes
- business_outcomes_extractor.extract_business_outcomes
"""

import pytest

pytestmark = pytest.mark.llm_required

# Sample document text — realistic project summary for extraction
SAMPLE_DOC = """\
Navitus Health Solutions — Cloud Migration Project (2020-2023)

Led the migration of a legacy Java monolith to a cloud-native microservices
architecture on AWS. The platform serves 30M+ pharmacy benefit members with
99.99% uptime SLA.

Key Technologies: Python, FastAPI, Docker, Kubernetes, Terraform, PostgreSQL,
Redis, Apache Kafka, AWS Lambda, S3, CloudFormation, DataDog, Splunk.

Architecture: Event-driven microservices communicating via Kafka topics.
REST APIs expose member lookup, claims adjudication, and formulary services.
API Gateway (Kong) handles rate limiting and auth.

Compliance: HIPAA-compliant data handling with PHI encryption at rest (AES-256)
and in transit (TLS 1.3). SOC 2 Type II audit completed. PCI DSS for payment
processing. Annual penetration testing by third-party firm.

Team & Leadership: Managed 12 engineers across 3 time zones. Introduced
sprint retrospectives and blameless post-mortems. Mentored 3 junior engineers
to senior level within 18 months.

Results: Reduced deployment time from 2 weeks to 2 hours (93% improvement).
Cut infrastructure costs by 40% ($1.2M annual savings). Improved API response
times from 800ms to 120ms (85% reduction). Achieved 99.99% uptime (from 99.5%).
Zero HIPAA violations over 3-year period.
"""


# ---------------------------------------------------------------------------
# technical_extractor
# ---------------------------------------------------------------------------


def test_technical_extractor_returns_list():
    from technical_extractor import extract_technical_picture

    result = extract_technical_picture(SAMPLE_DOC)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_technical_extractor_items_are_dicts():
    from technical_extractor import extract_technical_picture

    result = extract_technical_picture(SAMPLE_DOC)
    assert len(result) > 0, "Expected at least 1 technical item"
    for item in result:
        assert isinstance(item, dict), f"Expected dict, got {type(item)}"


def test_technical_extractor_has_name_field():
    from technical_extractor import extract_technical_picture

    result = extract_technical_picture(SAMPLE_DOC)
    names = [item.get("name", "") for item in result if item.get("name")]
    assert len(names) > 0, "At least one item should have a name"


def test_technical_extractor_has_category_field():
    from technical_extractor import extract_technical_picture

    result = extract_technical_picture(SAMPLE_DOC)
    categories = [item.get("category", "") for item in result if item.get("category")]
    assert len(categories) > 0, "At least one item should have a category"


def test_technical_extractor_with_context():
    from technical_extractor import extract_technical_picture

    result = extract_technical_picture(SAMPLE_DOC, context_summary="Enterprise healthcare platform")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# governance_extractor
# ---------------------------------------------------------------------------


def test_governance_extractor_returns_list():
    from governance_extractor import extract_governance_picture

    result = extract_governance_picture(SAMPLE_DOC)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_governance_extractor_items_are_dicts():
    from governance_extractor import extract_governance_picture

    result = extract_governance_picture(SAMPLE_DOC)
    assert len(result) > 0, "Expected at least 1 governance item (HIPAA mentioned)"
    for item in result:
        assert isinstance(item, dict)


def test_governance_extractor_has_name_field():
    from governance_extractor import extract_governance_picture

    result = extract_governance_picture(SAMPLE_DOC)
    names = [item.get("name", "") for item in result if item.get("name")]
    assert len(names) > 0, "Should extract at least one named governance item"


def test_governance_extractor_has_category_field():
    from governance_extractor import extract_governance_picture

    result = extract_governance_picture(SAMPLE_DOC)
    categories = [item.get("category", "") for item in result if item.get("category")]
    assert len(categories) > 0


def test_governance_extractor_with_context():
    from governance_extractor import extract_governance_picture

    result = extract_governance_picture(SAMPLE_DOC, context_summary="Healthcare PBM platform")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# role_extractor
# ---------------------------------------------------------------------------


def test_role_extractor_returns_list():
    from role_extractor import extract_role_picture

    result = extract_role_picture(SAMPLE_DOC)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_role_extractor_items_are_dicts():
    from role_extractor import extract_role_picture

    result = extract_role_picture(SAMPLE_DOC)
    assert len(result) > 0, "Expected at least 1 role item"
    for item in result:
        assert isinstance(item, dict)


def test_role_extractor_has_type_field():
    from role_extractor import extract_role_picture

    result = extract_role_picture(SAMPLE_DOC)
    types = [item.get("type", "") for item in result if item.get("type")]
    assert len(types) > 0


def test_role_extractor_has_title_field():
    from role_extractor import extract_role_picture

    result = extract_role_picture(SAMPLE_DOC)
    titles = [item.get("title", "") for item in result if item.get("title")]
    assert len(titles) > 0


def test_role_extractor_with_context():
    from role_extractor import extract_role_picture

    result = extract_role_picture(SAMPLE_DOC, context_summary="Cloud migration leadership role")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# skills_extractor
# ---------------------------------------------------------------------------


def test_skills_extractor_returns_list():
    from skills_extractor import extract_all_skills

    result = extract_all_skills(SAMPLE_DOC)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_skills_extractor_items_have_name():
    from skills_extractor import extract_all_skills

    result = extract_all_skills(SAMPLE_DOC)
    assert len(result) > 0, "Expected at least 1 skill"
    names = [s.get("name", "") for s in result if s.get("name")]
    assert len(names) > 0


def test_skills_extractor_items_have_category():
    from skills_extractor import extract_all_skills

    result = extract_all_skills(SAMPLE_DOC)
    categories = [s.get("category", "") for s in result if s.get("category")]
    assert len(categories) > 0


def test_skills_extractor_items_are_strings():
    from skills_extractor import extract_all_skills

    result = extract_all_skills(SAMPLE_DOC)
    for skill in result:
        if "name" in skill:
            assert isinstance(skill["name"], str)


def test_skills_extractor_with_context():
    from skills_extractor import extract_all_skills

    result = extract_all_skills(SAMPLE_DOC, context_summary="Enterprise architect role")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# skills_outcomes_extractor
# ---------------------------------------------------------------------------


def test_skills_outcomes_returns_tuple():
    from skills_outcomes_extractor import extract_skills_and_outcomes

    result = extract_skills_and_outcomes(SAMPLE_DOC)
    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 2, f"Expected 2-tuple, got {len(result)}-tuple"


def test_skills_outcomes_skills_are_list():
    from skills_outcomes_extractor import extract_skills_and_outcomes

    skills, outcomes = extract_skills_and_outcomes(SAMPLE_DOC)
    assert isinstance(skills, list)


def test_skills_outcomes_outcomes_are_list():
    from skills_outcomes_extractor import extract_skills_and_outcomes

    skills, outcomes = extract_skills_and_outcomes(SAMPLE_DOC)
    assert isinstance(outcomes, list)


def test_skills_outcomes_with_context():
    from skills_outcomes_extractor import extract_skills_and_outcomes

    skills, outcomes = extract_skills_and_outcomes(
        SAMPLE_DOC, context_summary="Healthcare migration project"
    )
    assert isinstance(skills, list)
    assert isinstance(outcomes, list)


# ---------------------------------------------------------------------------
# business_outcomes_extractor
# ---------------------------------------------------------------------------


def test_business_outcomes_returns_list():
    from business_outcomes_extractor import extract_business_outcomes

    result = extract_business_outcomes(SAMPLE_DOC)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_business_outcomes_items_are_dicts():
    from business_outcomes_extractor import extract_business_outcomes

    result = extract_business_outcomes(SAMPLE_DOC)
    assert len(result) > 0, "Expected at least 1 business outcome"
    for item in result:
        assert isinstance(item, dict)


def test_business_outcomes_has_outcome_title():
    from business_outcomes_extractor import extract_business_outcomes

    result = extract_business_outcomes(SAMPLE_DOC)
    titles = [o.get("outcome_title", "") for o in result if o.get("outcome_title")]
    assert len(titles) > 0


def test_business_outcomes_with_context():
    from business_outcomes_extractor import extract_business_outcomes

    result = extract_business_outcomes(SAMPLE_DOC, context_summary="PBM cloud migration")
    assert isinstance(result, list)
