"""Pytest fixtures and helpers for test_phase_b_hybrid_scorer.py.

Separated to keep test files under 500-line limit.
"""

import pytest
from datetime import date, timedelta


@pytest.fixture
def sample_requirement():
    """Standard requirement for must_have skill."""
    return {
        "requirement_id": "req_kafka_001",
        "requirement_type": "must_have",
        "text": "5+ years Apache Kafka experience in streaming architectures",
        "canonical_skills": ["Apache Kafka"],
        "importance": 1.0,
    }


@pytest.fixture
def sample_requirement_domain():
    """Domain-type requirement for healthcare context."""
    return {
        "requirement_id": "req_hipaa_001",
        "requirement_type": "domain",
        "text": "HIPAA compliance expertise with healthcare claims systems",
        "canonical_skills": ["HIPAA", "Claims"],
        "importance": 0.8,
    }


@pytest.fixture
def sample_requirement_leadership():
    """Leadership-type requirement."""
    return {
        "requirement_id": "req_lead_001",
        "requirement_type": "leadership",
        "text": "Led teams of 8+ engineers; established development standards",
        "canonical_skills": ["Team Leadership"],
        "importance": 0.7,
    }


@pytest.fixture
def sample_candidate_senior():
    """Candidate with high seniority signals and extensive Kafka experience."""
    return {
        "candidate_id": "cand_001",
        "target_role_families": ["data_architect", "consultant"],
        "skill_inventory": [
            {
                "canonical_skill": "Apache Kafka",
                "aliases": ["Kafka", "MSK"],
                "evidence_refs": ["proj_001", "proj_002", "proj_003"],
                "proficiency_estimate": "expert",
            },
            {
                "canonical_skill": "Python",
                "aliases": ["Python 3", "Py"],
                "evidence_refs": ["proj_001"],
                "proficiency_estimate": "expert",
            },
        ],
        "experience_units": [
            {
                "experience_id": "exp_001",
                "title": "Data Platform Architect",
                "company": "Navitus",
                "skills": ["Apache Kafka", "Python"],
                "leadership_signals": ["led teams", "strategy"],
                "date_range": {"start": "2022-01-01", "end": None},
            },
            {
                "experience_id": "exp_002",
                "title": "Principal Engineer",
                "company": "OPI",
                "skills": ["Kafka", "Spark"],
                "leadership_signals": ["mentored"],
                "date_range": {"start": "2019-01-01", "end": "2022-01-01"},
            },
        ],
    }


@pytest.fixture
def sample_candidate_junior():
    """Candidate with minimal experience and junior role signals."""
    return {
        "candidate_id": "cand_002",
        "target_role_families": ["engineer", "analyst"],
        "skill_inventory": [
            {
                "canonical_skill": "SQL",
                "aliases": ["T-SQL"],
                "evidence_refs": ["proj_001"],
                "proficiency_estimate": "intermediate",
            }
        ],
        "experience_units": [
            {
                "experience_id": "exp_003",
                "title": "Software Engineer",
                "company": "StartupXYZ",
                "skills": ["SQL"],
                "leadership_signals": [],
                "date_range": {"start": "2024-01-01", "end": None},
            }
        ],
    }


@pytest.fixture
def sample_candidate_healthcare():
    """Candidate with healthcare domain experience."""
    return {
        "candidate_id": "cand_003",
        "target_role_families": ["healthcare_data"],
        "skill_inventory": [
            {
                "canonical_skill": "HIPAA",
                "aliases": ["PHI", "HIPAA Compliance"],
                "evidence_refs": ["proj_001", "proj_002"],
                "proficiency_estimate": "expert",
            },
            {
                "canonical_skill": "Claims Processing",
                "aliases": ["Claims", "Pharmacy Claims"],
                "evidence_refs": ["proj_001"],
                "proficiency_estimate": "expert",
            },
        ],
        "experience_units": [
            {
                "experience_id": "exp_004",
                "title": "Healthcare Data Architect",
                "company": "Navitus Health Solutions",
                "skills": ["HIPAA", "Claims Processing"],
                "leadership_signals": ["led compliance"],
                "date_range": {"start": "2020-01-01", "end": None},
            }
        ],
    }


@pytest.fixture
def empty_candidate():
    """Candidate with no experience or skills."""
    return {
        "candidate_id": "cand_empty",
        "target_role_families": [],
        "skill_inventory": [],
        "experience_units": [],
    }


@pytest.fixture
def candidate_old_skill():
    """Candidate with skill from 5+ years ago."""
    return {
        "candidate_id": "cand_old",
        "target_role_families": [],
        "skill_inventory": [],
        "experience_units": [
            {
                "experience_id": "exp",
                "skills": ["Apache Kafka"],
                "date_range": {
                    "start": "2018-01-01",
                    "end": (date.today() - timedelta(days=1825)).isoformat(),
                },
            }
        ],
    }


@pytest.fixture
def candidate_recent_skill():
    """Candidate with skill used 2 years ago."""
    return {
        "candidate_id": "cand_recent",
        "target_role_families": [],
        "skill_inventory": [],
        "experience_units": [
            {
                "experience_id": "exp",
                "skills": ["Apache Kafka"],
                "date_range": {
                    "start": "2021-01-01",
                    "end": (date.today() - timedelta(days=730)).isoformat(),
                },
            }
        ],
    }
