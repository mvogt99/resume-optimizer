"""
Module to audit resume claims against candidate profile evidence.
Extracts specific claims from resume text, cross-references against skill_inventory and experience_units,
and flags unsupported or risky claims.
"""

import hashlib
import json
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

# Module-level LLM import — allows test patching via patch("claim_auditor.call_llm_quality")
try:
    from llm_helper import call_llm_quality
except ImportError:  # pragma: no cover
    call_llm_quality = None  # type: ignore[assignment]

def audit_claims(resume_text: str, candidate_profile: dict, use_llm: bool = True) -> List[Dict]:
    """
    Audits resume claims against candidate profile evidence.

    :param resume_text: Raw resume text.
    :param candidate_profile: Dict from normalizer with skill_inventory and experience_units.
    :param use_llm: Boolean flag to use LLM for refinement.
    :return: List of claim_audit dicts sorted by risk_level (high first).
    """
    try:
        claims = _extract_claims(resume_text)
        audits = [_check_claim_against_profile(claim, candidate_profile) for claim in claims]
        audits = [_classify_claim(claim, audit) for claim, audit in zip(claims, audits)]
        audits.sort(key=lambda x: {'high': 3, 'medium': 2, 'low': 1}[x['risk_level']], reverse=True)
        if use_llm:
            audits = _refine_with_llm(audits, resume_text, candidate_profile)
        return audits
    except Exception as e:
        logger.error(f"Error auditing claims: {e}")
        return []

def _extract_claims(resume_text: str) -> List[str]:
    """
    Extract specific, verifiable claims from resume text lines.

    :param resume_text: Raw resume text.
    :return: List of claim strings, max 30.
    """
    lines = resume_text.split('\n')
    claims = []
    tech_keywords = {
        # Languages
        "Python", "Java", "Go", "Rust", "Scala", "Ruby", "C++", "C#", "TypeScript",
        "JavaScript", "SQL", "R", "Bash", "Perl", "Swift", "Kotlin",
        # Cloud & infra
        "AWS", "Azure", "GCP", "Kubernetes", "Docker", "Terraform", "Helm",
        "CloudFormation", "Ansible", "Jenkins", "CircleCI", "GitHub Actions",
        # Data & streaming
        "Kafka", "Spark", "Flink", "Airflow", "dbt", "Snowflake", "Redshift",
        "BigQuery", "Databricks", "Hadoop", "Hive", "Presto", "Trino",
        # Frameworks & tools
        "React", "Node.js", "Django", "Flask", "FastAPI", "Spring", "Rails",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra",
        # ML/AI
        "PyTorch", "TensorFlow", "scikit-learn", "MLflow", "Kubeflow",
    }
    for line in lines:
        if any(keyword in line for keyword in tech_keywords):
            claims.append(line.strip())
        elif re.search(r'\d', line):
            claims.append(line.strip())
        elif re.search(r'\b(?:enterprise|cross-functional|global|organization-wide)\b', line):
            claims.append(line.strip())
    return claims[:30]

def _check_claim_against_profile(claim: str, candidate_profile: dict) -> Dict:
    """
    Search skill_inventory and experience_units for evidence supporting the claim.

    :param claim: Claim string.
    :param candidate_profile: Candidate profile dictionary.
    :return: Dictionary with is_supported, evidence_refs, and confidence.
    """
    evidence_refs = []
    skill_inventory = candidate_profile.get('skill_inventory', [])
    experience_units = candidate_profile.get('experience_units', [])

    for skill in skill_inventory:
        canonical = skill.get('canonical_skill', '')
        aliases = skill.get('aliases', [])
        all_names = [canonical] + aliases
        if any(name.lower() in claim.lower() for name in all_names if name):
            # Include the actual evidence refs (project/client IDs) for depth counting
            skill_refs = skill.get('evidence_refs', [])
            evidence_refs.extend(skill_refs if skill_refs else [canonical])

    for unit in experience_units:
        unit_skills = [s.lower() for s in unit.get('skills', [])]
        if any(s in claim.lower() for s in unit_skills):
            evidence_refs.append(unit.get('company', ''))

    # Deduplicate while preserving order
    seen: set = set()
    evidence_refs = [r for r in evidence_refs if r and not (r in seen or seen.add(r))]

    is_supported = len(evidence_refs) > 0
    confidence = 0.9 if len(evidence_refs) >= 3 else 0.6 if len(evidence_refs) >= 1 else 0.1

    return {
        'is_supported': is_supported,
        'evidence_refs': evidence_refs,
        'confidence': confidence
    }

def _classify_claim(claim: str, audit: Dict) -> Dict:
    """
    Classify claim type, risk level, and generate audit_id.

    :param claim: Claim string.
    :param audit: Audit dictionary.
    :return: Enhanced audit dictionary.
    """
    claim_type = _classify_claim_type(claim)
    risk_level = _classify_risk(claim, audit['is_supported'], audit['evidence_refs'], audit['confidence'])
    suggested_revision = _generate_suggested_revision(risk_level, claim)

    audit_id = hashlib.sha1(claim.encode()).hexdigest()[:12]

    return {
        'audit_id': audit_id,
        'claim_text': claim,
        'claim_type': claim_type,
        'is_supported': audit['is_supported'],
        'evidence_refs': audit['evidence_refs'],
        'risk_level': risk_level,
        'confidence': audit['confidence'],
        'suggested_revision': suggested_revision
    }

def _classify_risk(claim: str, is_supported: bool, evidence_refs: List, confidence: float) -> str:
    """
    Classify risk level based on claim details and audit results.

    :param claim: Claim string.
    :param is_supported: Boolean indicating if claim is supported.
    :param evidence_refs: List of evidence references.
    :param confidence: Confidence level.
    :return: Risk level string.
    """
    if not is_supported:
        return 'high'
    if confidence < 0.6:
        return 'medium'
    return 'low'

def _classify_claim_type(claim: str) -> str:
    """
    Classify claim type based on content.

    :param claim: Claim string.
    :return: Claim type string.
    """
    if re.search(r'\d+\+?\s*years?\s*(of\s+\w+|experience)', claim, re.IGNORECASE):
        return 'years_experience'
    if re.search(r'[\$£]?\d+[\.,]?\d*[MBKGmkg%]?\s*(events?|nodes?|engineers?|users?|TB|GB|MB|%|\$|M|B|K)', claim):
        return 'quantified_metric'
    if re.search(r'\d', claim):
        return 'quantified_metric'
    if any(keyword in claim for keyword in ["Python", "Kafka", "AWS", "Kubernetes", "Spark", "Databricks"]):
        return 'technology_skill'
    if re.search(r'\b(?:enterprise|cross-functional|global|organization-wide)\b', claim):
        return 'role_scope'
    return 'other'

def _generate_suggested_revision(risk_level: str, claim: str) -> str:
    """
    Generate suggested revision based on risk level.

    :param risk_level: Risk level string.
    :param claim: Claim string.
    :return: Suggested revision string.
    """
    if risk_level == 'high':
        return f"Verify the accuracy of this claim and add supporting evidence: '{claim[:80]}'."
    if risk_level == 'medium':
        return f"Strengthen this claim with quantified outcomes or additional context: '{claim[:80]}'."
    return "Claim is well-supported — no revision needed."

def _refine_with_llm(audits: List, resume_text: str, candidate_profile: dict) -> List:
    """
    Refine audits using LLM if available.

    :param audits: List of audit dictionaries.
    :param resume_text: Raw resume text.
    :param candidate_profile: Candidate profile dictionary.
    :return: Refined list of audit dictionaries.
    """
    if call_llm_quality is None:
        return audits

    high_medium_audits = [audit for audit in audits if audit['risk_level'] in ['high', 'medium']][:10]
    slim = [{"audit_id": a["audit_id"], "claim_text": a["claim_text"],
             "risk_level": a["risk_level"]} for a in high_medium_audits]
    prompt = (
        "Review these resume claim audits and return a JSON array with corrected risk_level "
        "(high/medium/low) and suggested_revision for each. "
        "Return ONLY a JSON array, no prose.\n\n"
        f"Claims:\n{json.dumps(slim, indent=2)}"
    )

    try:
        raw = call_llm_quality(prompt, task_type="generation") or ""
        json_match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if not json_match:
            return audits
        parsed = json.loads(json_match.group())
        llm_map = {
            item['audit_id']: item
            for item in parsed
            if isinstance(item, dict) and 'audit_id' in item
        }
        for audit in audits:
            if audit['audit_id'] in llm_map:
                llm_item = llm_map[audit['audit_id']]
                if llm_item.get('risk_level') in ('high', 'medium', 'low'):
                    audit['risk_level'] = llm_item['risk_level']
                if llm_item.get('suggested_revision'):
                    audit['suggested_revision'] = llm_item['suggested_revision']
        return audits
    except Exception as e:
        logger.error(f"LLM refinement failed: {e}")
        return audits

def summarize_audit(audits: List) -> Dict:
    """
    Summarize audit results.

    :param audits: List of audit dictionaries.
    :return: Summary dictionary.
    """
    total = len(audits)
    supported_count = sum(1 for audit in audits if audit['is_supported'])
    unsupported_count = total - supported_count
    high_risk_count = sum(1 for audit in audits if audit['risk_level'] == 'high')
    by_claim_type = {}

    for audit in audits:
        claim_type = audit['claim_type']
        by_claim_type[claim_type] = by_claim_type.get(claim_type, 0) + 1

    return {
        'total': total,
        'supported_count': supported_count,
        'unsupported_count': unsupported_count,
        'high_risk_count': high_risk_count,
        'by_claim_type': by_claim_type
    }
