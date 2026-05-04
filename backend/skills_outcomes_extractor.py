"""
Combined skills + business outcomes extraction in a single LLM call.
Halves the number of LLM calls vs running two separate extractors.
"""

from llm_helper import analyze_with_chunking, analyze_with_context, merge_extracted_items

COMBINED_PROMPT = (
    "Analyze this project document chunk ({chunk_num}/{total_chunks})"
    " and extract BOTH skills AND business outcomes.\n\n"
    'Return a JSON object with two keys: "skills" and "outcomes".\n\n'
    "=== SKILLS ===\n"
    "Extract ALL skills, technologies, methodologies, and competencies:\n"
    "1. **Explicit technologies**: tools, languages, platforms directly named\n"
    "2. **Implied technical skills**: activities that imply skills"
    ' (e.g., "built data pipeline" → ETL, data engineering)\n'
    "3. **Soft skills**: leadership, communication, collaboration patterns\n"
    "4. **Methodologies**: Agile, DevOps, CI/CD, ITIL, etc.\n"
    "5. **Domain expertise**: industry knowledge, regulatory, business domains\n\n"
    "Each skill object:\n"
    '  {{"name": "...", "category": "technology|implied_technical|soft_skill|'
    'methodology|domain_expertise", "evidence": "...", '
    '"proficiency_signal": "mentioned|used|led|expert", "confidence": 0.0-1.0}}\n\n'
    "=== OUTCOMES ===\n"
    "Extract ALL quantified business outcomes across 11 types:\n"
    "revenue_growth, cost_reduction, efficiency_improvement, scale_achievement, "
    "quality_improvement, customer_satisfaction, risk_reduction, team_org_impact, "
    "process_automation, capability_enablement, time_savings\n\n"
    "Each outcome object:\n"
    '  {{"outcome_title": "...", "outcome_type": "...", "description": "...", '
    '"metric_value": "...", "metric_unit": "...", "baseline": "...", '
    '"result": "...", "time_period": "...", "beneficiary": "...", '
    '"confidence": 0.0-1.0}}\n\n'
    'Return JSON: {{"skills": [...], "outcomes": [...]}}\n'
    "Be thorough — extract 10-25 skills and 3-10 outcomes per chunk.\n\n"
    "Document chunk:\n{chunk}"
)


def _split_combined_result(items):
    """Split combined extraction results into separate skills and outcomes lists."""
    skills = []
    outcomes = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # If the item IS the combined object with skills/outcomes keys
        if "skills" in item and "outcomes" in item:
            s = item["skills"]
            o = item["outcomes"]
            if isinstance(s, list):
                skills.extend(s)
            if isinstance(o, list):
                outcomes.extend(o)
        # If individual items leaked through (fallback)
        elif "outcome_title" in item or "outcome_type" in item:
            outcomes.append(item)
        elif "name" in item and ("category" in item or "proficiency_signal" in item):
            skills.append(item)
    return skills, outcomes


def extract_skills_and_outcomes(document_text, context_summary=""):
    """Extract both skills and outcomes in a single LLM pass.

    Args:
        document_text: Full document text to analyze.
        context_summary: Optional cross-document context.

    Returns:
        (skills_list, outcomes_list) tuple.
    """
    if context_summary:
        items = analyze_with_context(
            document_text,
            COMBINED_PROMPT,
            context_summary,
            task_type="reasoning",
            max_tokens=8192,
        )
    else:
        items = analyze_with_chunking(
            document_text,
            COMBINED_PROMPT,
            task_type="reasoning",
            max_tokens=8192,
        )

    skills, outcomes = _split_combined_result(items)
    skills = merge_extracted_items(skills, "name")
    outcomes = merge_extracted_items(outcomes, "outcome_title")
    return skills, outcomes
