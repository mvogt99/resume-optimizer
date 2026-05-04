"""CT-1: Tests for BaseCareerAgent claim recording methods."""

import pytest

from agents.base_agent import BaseCareerAgent


@pytest.fixture
def agent():
    return BaseCareerAgent()


def test_record_claim_returns_id(agent):
    claim_id = agent.record_claim("Led team of 5 engineers")
    assert claim_id
    assert isinstance(claim_id, str)


def test_record_claim_stores_claim(agent):
    claim_id = agent.record_claim("Reduced latency by 40%")
    claims = agent.get_claims()
    assert len(claims) == 1
    assert claims[0]["claim_id"] == claim_id
    assert claims[0]["claim_text"] == "Reduced latency by 40%"


def test_record_claim_default_type(agent):
    agent.record_claim("Launched product used by 10k users")
    claims = agent.get_claims()
    assert claims[0]["claim_type"] == "achievement"


def test_record_claim_custom_type(agent):
    agent.record_claim("Managed $2M budget", claim_type="responsibility")
    claims = agent.get_claims()
    assert claims[0]["claim_type"] == "responsibility"


def test_get_claims_returns_list(agent):
    agent.record_claim("Claim A")
    agent.record_claim("Claim B")
    result = agent.get_claims()
    assert isinstance(result, list)
    assert len(result) == 2


def test_clear_claims_empties_list(agent):
    agent.record_claim("Claim to clear")
    agent.clear_claims()
    assert agent.get_claims() == []
