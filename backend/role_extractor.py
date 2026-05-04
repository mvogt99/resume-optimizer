"""
LLM-powered role & impact extraction from project documents.
Extracts: contributions, leadership scope, business impact,
skills demonstrated.
"""

from llm_helper import analyze_with_chunking, analyze_with_context, merge_extracted_items

ROLE_PROMPT = (
    "Analyze this project document chunk ({chunk_num}/{total_chunks})"
    " and extract a JSON array of professional contributions,"
    " leadership activities, and business impacts found.\n\n"
    "For each element, return an object with these fields:\n"
    '- "type": one of "contribution", "leadership", "impact",'
    ' "skill_demonstrated"\n'
    '- "title": short description (5-10 words)\n'
    '- "description": detailed description (1-3 sentences)\n'
    '- "metrics": any quantifiable results mentioned'
    ' (e.g., "reduced costs by 30%")\n'
    '- "confidence": 0.0-1.0 how certain you are about this\n\n'
    "Focus on what the person DID, LED, or ACHIEVED."
    " Return a JSON array.\n\n"
    "Document chunk:\n{chunk}"
)


def extract_role_picture(document_text, context_summary=""):
    """Extract role/impact elements. Returns list of dicts."""
    if context_summary:
        items = analyze_with_context(
            document_text, ROLE_PROMPT, context_summary, task_type="reasoning"
        )
    else:
        items = analyze_with_chunking(document_text, ROLE_PROMPT, task_type="reasoning")
    return merge_extracted_items(items, "title")
