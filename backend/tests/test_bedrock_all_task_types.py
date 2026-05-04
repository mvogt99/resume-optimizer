"""Live Bedrock coverage for all 14 resume-optimizer task types.

Verifies every task type in TASK_TYPE_MAP routes to Bedrock and returns
valid text. Only runs with CLOUDLIFT_ENV=aws.

Usage: CLOUDLIFT_ENV=aws AWS_REGION=us-east-1 pytest tests/test_bedrock_all_task_types.py -v
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CLOUDLIFT_ENV") != "aws",
    reason="Live Bedrock tests require CLOUDLIFT_ENV=aws",
)

# All 14 task types from TASK_TYPE_MAP
TASK_TYPES = [
    ("resume_analysis", "analysis"),
    ("skills_gap", "analysis"),
    ("ats_diagnostic", "analysis"),
    ("document_classification", "analysis"),
    ("outcome_extraction", "analysis"),
    ("interview", "reasoning"),
    ("experience_chat", "reasoning"),
    ("campaign_planning", "reasoning"),
    ("narrative_generation", "reasoning"),
    ("json_extraction", "coding"),
    ("technical_extraction", "coding"),
    ("resume_rewrite", "coding"),
    ("career_planning", "planning"),
    ("campaign_strategy", "planning"),
]

SHORT_PROMPTS = {
    "resume_analysis": "List 2 strengths in: 'Python developer, 5 years Django, led team of 4'",
    "skills_gap": "What skills gap exists? Role needs Kubernetes. Candidate has Docker only.",
    "ats_diagnostic": "ATS score for: 'Python Engineer' applying to 'Senior Python Developer' role?",
    "document_classification": "Is this a resume or cover letter? 'Dear Hiring Manager, I am writing to apply...'",
    "outcome_extraction": "Extract metric: 'Improved API latency by 40% serving 2M daily requests'",
    "interview": "Ask one behavioral interview question for a Python developer role.",
    "experience_chat": "In one sentence, how should I describe leading a migration project?",
    "campaign_planning": "Suggest one job application strategy for a backend engineer.",
    "narrative_generation": "Write one sentence describing: 5 years Python, team lead, fintech.",
    "json_extraction": 'Return JSON: {"skill": "Python", "years": 5} from: "5 years of Python experience"',
    "technical_extraction": "Extract tech stack from: 'Used Django, PostgreSQL, Redis, and AWS S3'",
    "resume_rewrite": "Rewrite in one strong bullet: 'I worked on improving the API'",
    "career_planning": "Give one career move suggestion for a Python dev wanting to grow.",
    "campaign_strategy": "One-line strategy for applying to FAANG with 3 years Python experience.",
}


@pytest.mark.parametrize("task_type,bedrock_tier", TASK_TYPES)
def test_bedrock_task_type(task_type, bedrock_tier):
    """Each task type must return non-empty text from Bedrock."""
    import sys
    sys.path.insert(0, ".")
    from cloudlift_llm_adapter import call_bedrock, BEDROCK_MODEL_MAP

    prompt = SHORT_PROMPTS[task_type]
    result = call_bedrock(prompt, task_type=bedrock_tier, max_tokens=256)

    assert result is not None, f"Bedrock returned None for task_type={task_type}"
    assert len(result.strip()) > 10, f"Response too short for task_type={task_type}: '{result}'"
    print(f"\n[{task_type} → {BEDROCK_MODEL_MAP.get(bedrock_tier, '?')}] {result[:100]}")
