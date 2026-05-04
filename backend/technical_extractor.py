"""
LLM-powered technical picture extraction from project documents.
Extracts: technologies, architectures, integrations, data flows, outcomes.
"""

from llm_helper import analyze_with_chunking, analyze_with_context, merge_extracted_items

TECH_PROMPT = (
    "Analyze this project document chunk ({chunk_num}/{total_chunks})"
    " and extract a JSON array of technical elements found.\n\n"
    "For each element, return an object with these fields:\n"
    '- "name": technology/tool/platform name\n'
    '- "category": one of "language", "framework", "database",'
    ' "cloud", "integration", "architecture", "tool", "protocol"\n'
    '- "context": how it was used (1-2 sentences)\n'
    '- "confidence": 0.0-1.0 how certain you are this was actually used\n\n'
    "Only include technologies that are clearly mentioned or"
    " strongly implied. Return a JSON array.\n\n"
    "Document chunk:\n{chunk}"
)


def extract_technical_picture(document_text, context_summary=""):
    """Extract technical elements from a document. Returns list of dicts."""
    if context_summary:
        items = analyze_with_context(
            document_text, TECH_PROMPT, context_summary, task_type="reasoning"
        )
    else:
        items = analyze_with_chunking(document_text, TECH_PROMPT, task_type="reasoning")
    return merge_extracted_items(items, "name")
