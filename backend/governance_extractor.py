"""
LLM-powered governance picture extraction from project documents.
Extracts: data classifications, compliance frameworks, security controls,
PII handling, regulatory requirements.
"""

from llm_helper import analyze_with_chunking, analyze_with_context, merge_extracted_items

GOV_PROMPT = (
    "Analyze this project document chunk ({chunk_num}/{total_chunks})"
    " and extract a JSON array of data governance and"
    " compliance elements found.\n\n"
    "For each element, return an object with these fields:\n"
    '- "name": the control, framework, or requirement name\n'
    '- "category": one of "compliance_framework", "security_control",'
    ' "data_classification", "pii_handling", "regulatory",'
    ' "access_control", "audit"\n'
    '- "description": what it entails in this project context'
    " (1-2 sentences)\n"
    '- "confidence": 0.0-1.0 how certain you are this was in scope\n\n'
    "Only include items that are clearly referenced."
    " Return a JSON array.\n\n"
    "Document chunk:\n{chunk}"
)


def extract_governance_picture(document_text, context_summary=""):
    """Extract governance/compliance elements. Returns list of dicts."""
    if context_summary:
        items = analyze_with_context(
            document_text, GOV_PROMPT, context_summary, task_type="reasoning"
        )
    else:
        items = analyze_with_chunking(document_text, GOV_PROMPT, task_type="reasoning")
    return merge_extracted_items(items, "name")
