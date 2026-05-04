"""
Extract structured business outcomes from project documents.
Finds ALL quantified business outcomes: revenue growth, cost reduction,
efficiency improvements, scale achievements, and more.
"""

from llm_helper import analyze_with_chunking, analyze_with_context, merge_extracted_items

OUTCOMES_PROMPT = (
    "Analyze this project document chunk ({chunk_num}/{total_chunks})"
    " and extract ALL quantified business outcomes.\n\n"
    "Look for these 11 outcome types:\n"
    "1. **revenue_growth**: increased revenue, new revenue streams\n"
    "2. **cost_reduction**: reduced costs, eliminated expenses\n"
    "3. **efficiency_improvement**: faster processing, reduced latency, throughput gains\n"
    "4. **scale_achievement**: handled more volume, users, transactions\n"
    "5. **quality_improvement**: reduced defects, improved accuracy\n"
    "6. **customer_satisfaction**: NPS improvement, user adoption, retention\n"
    "7. **risk_reduction**: compliance improvements, audit findings reduced\n"
    "8. **team_org_impact**: team growth, org restructuring, cross-functional leadership\n"
    "9. **process_automation**: manual steps eliminated, automated workflows\n"
    "10. **capability_enablement**: enabled self-service, new capabilities for users\n"
    "11. **time_savings**: reduced time-to-market, faster delivery cycles\n\n"
    "For each outcome, return a JSON object with:\n"
    '- "outcome_title": short descriptive title (e.g. "Reduced query latency by 75%")\n'
    '- "outcome_type": one of the 11 types listed above\n'
    '- "description": 1-2 sentence description of the outcome\n'
    '- "metric_value": the quantified value (e.g. "75%", "$4.5M", "10x")\n'
    '- "metric_unit": unit type (e.g. "percent_reduction", "dollars", "count",'
    ' "multiplier", "hours", "days")\n'
    '- "baseline": what it was before (e.g. "12 seconds average query time")\n'
    '- "result": what it became (e.g. "3 seconds average query time")\n'
    '- "time_period": when this happened (e.g. "Q3 2025")\n'
    '- "beneficiary": who benefited (e.g. "data analytics team", "company")\n'
    '- "confidence": 0.0-1.0 — higher if baseline+result both stated,'
    " lower if inferred\n\n"
    "Be thorough — extract 5-15 outcomes per chunk. "
    "Don't skip any quantified results, percentages, dollar amounts, "
    "time savings, or scale metrics.\n"
    "Return a JSON array.\n\n"
    "Document chunk:\n{chunk}"
)


def extract_business_outcomes(document_text, context_summary=""):
    """Extract all quantified business outcomes from document text.

    Args:
        document_text: Full document text to analyze.
        context_summary: Optional cross-document context for richer extraction.

    Returns:
        List of outcome dicts with outcome_title, outcome_type, description,
        metric_value, metric_unit, baseline, result, time_period, beneficiary,
        confidence.
    """
    if context_summary:
        items = analyze_with_context(
            document_text, OUTCOMES_PROMPT, context_summary, task_type="reasoning"
        )
    else:
        items = analyze_with_chunking(document_text, OUTCOMES_PROMPT, task_type="reasoning")

    return merge_extracted_items(items, "outcome_title")
