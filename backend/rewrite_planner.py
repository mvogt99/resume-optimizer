"""
Module for planning resume rewrites based on gap analysis and scoring.
"""

import hashlib
import json
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

try:
    from llm_helper import call_llm_quality
except ImportError:
    call_llm_quality = None

def plan_rewrites(gaps: List[Dict], scores: List[Dict], candidate_profile: Dict, resume_text: str, use_llm: bool = True) -> List[Dict]:
    """
    Plans rewrite targets based on gap analysis and scoring.

    :param gaps: List of dicts with keys gap_id, requirement_id, gap_type, severity, description.
    :param scores: List of dicts with keys requirement_id, composite_score, match_type.
    :param candidate_profile: Candidate profile dictionary.
    :param resume_text: Full text of the resume.
    :param use_llm: Boolean flag to determine if LLM should be used for enrichment.
    :return: List of rewrite_target dicts sorted by priority ascending.
    """
    try:
        targets = _plan_heuristic_rewrites(gaps, scores, candidate_profile, resume_text)
        if use_llm:
            targets = _enrich_with_llm(targets, resume_text)
        return targets
    except Exception as e:
        logger.error(f"Error in plan_rewrites: {e}")
        return []

def _plan_heuristic_rewrites(gaps: List[Dict], scores: List[Dict], candidate_profile: Dict, resume_text: str) -> List[Dict]:
    """
    Generates heuristic rewrite targets for each gap.

    :param gaps: List of dicts with keys gap_id, requirement_id, gap_type, severity, description.
    :param scores: List of dicts with keys requirement_id, composite_score, match_type.
    :param candidate_profile: Candidate profile dictionary.
    :param resume_text: Full text of the resume.
    :return: List of rewrite_target dicts.
    """
    targets = []
    severity_weights = {'high': 3, 'medium': 2, 'low': 1}

    for gap in gaps:
        evidence_anchor = _find_evidence_anchor(gap, candidate_profile)
        estimated_impact = _estimate_impact(gap, scores)
        composite_score = next((s['composite_score'] for s in scores if s['requirement_id'] == gap['requirement_id']), 0)
        urgency_score = severity_weights.get(gap.get('severity', 'low'), 1) * (1 - composite_score)

        suggested_action = _generate_suggested_action(gap['gap_type'])
        rewrite_template = _generate_rewrite_template(gap['description'])

        target = {
            'target_id': hashlib.sha1(gap['gap_id'].encode()).hexdigest()[:12],
            'gap_id': gap['gap_id'],
            'requirement_id': gap['requirement_id'],
            'priority': 0,  # assigned after sorting
            'gap_type': gap['gap_type'],
            'suggested_action': suggested_action,
            'evidence_anchor': evidence_anchor,
            'rewrite_template': rewrite_template,
            'severity': gap['severity'],
            'estimated_impact': estimated_impact,
            '_urgency': urgency_score,
        }
        targets.append(target)

    # Sort descending (highest urgency = rank 1), then assign 1-based integer ranks
    targets.sort(key=lambda x: x['_urgency'], reverse=True)
    for idx, t in enumerate(targets):
        t['priority'] = idx + 1
        del t['_urgency']
    return targets

def _find_evidence_anchor(gap: Dict, candidate_profile: Dict) -> str:
    """
    Finds an evidence anchor in the candidate profile for the given gap.

    :param gap: Gap dictionary.
    :param candidate_profile: Candidate profile dictionary.
    :return: Human-readable evidence anchor string.
    """
    keywords = set(gap['description'].lower().split())
    skill_inventory = candidate_profile.get('skill_inventory', [])
    experience_units = candidate_profile.get('experience_units', [])

    matches = []
    for item in skill_inventory:
        canonical = item.get('canonical_skill', '')
        aliases = item.get('aliases', [])
        evidence_refs = item.get('evidence_refs', [])
        all_names = [canonical] + aliases
        if any(keyword in name.lower() for keyword in keywords for name in all_names if name):
            ref_count = len(evidence_refs)
            matches.append(f"{canonical} ({ref_count} evidence refs)")

    for unit in experience_units:
        unit_skills = [s.lower() for s in unit.get('skills', [])]
        if any(keyword in s for keyword in keywords for s in unit_skills):
            matches.append(unit.get('company', 'Unknown company'))

    if matches:
        return "; ".join(matches[:3])
    return "No direct evidence found"

def _estimate_impact(gap: Dict, scores: List[Dict]) -> float:
    """
    Estimates the impact of addressing the given gap.

    :param gap: Gap dictionary.
    :param scores: List of dicts with keys requirement_id, composite_score, match_type.
    :return: Estimated impact as a float.
    """
    composite_score = next((s['composite_score'] for s in scores if s['requirement_id'] == gap['requirement_id']), 0)
    severity_ranges = {'high': (0.25, 0.35), 'medium': (0.10, 0.20), 'low': (0.05, 0.10)}
    base_impact = severity_ranges[gap['severity']][0] + (severity_ranges[gap['severity']][1] - severity_ranges[gap['severity']][0]) * (1 - composite_score)
    return min(base_impact, 1.0)

def _generate_suggested_action(gap_type: str) -> str:
    """
    Generates a suggested action based on the gap type.

    :param gap_type: Type of the gap.
    :return: Suggested action string.
    """
    actions = {
        'missing_experience': "Add relevant experience to your resume.",
        'weak_wording': "Rephrase to emphasize your achievements more clearly.",
        'missing_explicit_keyword': "Include specific keywords related to the job description.",
        'insufficient_leadership_signal': "Highlight leadership roles and responsibilities.",
        'seniority_mismatch': "Adjust your resume to better match the job's seniority level.",
        'domain_gap': "Demonstrate knowledge and experience in the required domain.",
        'unsupported_claim_risk': "Provide evidence to support claims made in your resume."
    }
    return actions.get(gap_type, "Take appropriate action to address the gap.")

def _generate_rewrite_template(description: str) -> str:
    """
    Generates a rewrite template based on the gap description.

    :param description: Description of the gap.
    :return: Rewrite template string.
    """
    return f"[Your role] at [Company], {description}"

def _enrich_with_llm(targets: List[Dict], resume_text: str) -> List[Dict]:
    """
    Enriches rewrite templates using a language model.

    :param targets: List of rewrite_target dicts.
    :param resume_text: Full text of the resume.
    :return: Updated list of rewrite_target dicts.
    """
    if call_llm_quality is None:
        return targets

    top_targets = sorted(targets, key=lambda x: x.get('priority', 999))[:10]
    prompt = f"Improve the rewrite templates for the following resume gaps:\n{resume_text}\nTemplates:\n"
    prompt += "\n".join([f"{t['target_id']}: {t['rewrite_template']}" for t in top_targets])

    try:
        raw = call_llm_quality(prompt, task_type="generation") or ""
        # LLM returns a string — extract JSON array from it
        json_match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if not json_match:
            return targets
        parsed = json.loads(json_match.group())
        improvements = {
            item['target_id']: item['improved_template']
            for item in parsed
            if isinstance(item, dict) and 'target_id' in item and 'improved_template' in item
        }
        for target in targets:
            if target['target_id'] in improvements:
                target['rewrite_template'] = improvements[target['target_id']]
    except Exception as e:
        logger.error(f"Error enriching with LLM: {e}")

    return targets

def summarize_rewrite_plan(targets: List[Dict]) -> Dict:
    """
    Summarizes the rewrite plan.

    :param targets: List of rewrite_target dicts.
    :return: Summary dictionary.
    """
    summary = {
        'total': len(targets),
        'high_priority_count': sum(1 for t in targets if t.get('severity') == 'high'),
        'by_gap_type': {},
        'estimated_overall_impact': 0.0
    }

    for target in targets:
        gap_type = target['gap_type']
        summary['by_gap_type'][gap_type] = summary['by_gap_type'].get(gap_type, 0) + 1

    top_impacts = sorted((t['estimated_impact'] for t in targets), reverse=True)[:5]
    summary['estimated_overall_impact'] = min(sum(top_impacts), 1.0)

    return summary
