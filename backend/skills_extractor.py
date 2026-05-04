"""
Comprehensive skills extraction from project documents.
Finds ALL skills: explicit technologies, implied skills from activities,
soft skills, methodologies, and domain expertise.
"""

from llm_helper import analyze_with_chunking, analyze_with_context, merge_extracted_items

SKILLS_PROMPT = (
    "Analyze this project document chunk ({chunk_num}/{total_chunks})"
    " and extract EVERY skill, technology, methodology, and competency"
    " mentioned or implied.\n\n"
    "Extract ALL of these categories:\n"
    "1. **Explicit technologies**: tools, languages, platforms directly named\n"
    "2. **Implied technical skills**: activities that imply skills"
    ' (e.g., "built data pipeline" → ETL, data engineering)\n'
    "3. **Soft skills**: leadership, communication, collaboration patterns"
    ' (e.g., "coordinated across teams" → cross-functional leadership)\n'
    "4. **Methodologies**: Agile, DevOps, CI/CD, ITIL, etc.\n"
    "5. **Domain expertise**: industry knowledge, regulatory, business domains\n\n"
    "For each skill, return a JSON object with:\n"
    '- "name": skill/technology name\n'
    '- "category": one of "technology", "implied_technical", "soft_skill",'
    ' "methodology", "domain_expertise"\n'
    '- "evidence": the phrase or sentence that demonstrates this skill\n'
    '- "proficiency_signal": one of "mentioned", "used", "led", "expert"'
    " based on how it appears\n"
    '- "confidence": 0.0-1.0\n\n'
    "Be thorough — extract 15-30 skills per chunk. Don't skip anything.\n"
    "Return a JSON array.\n\n"
    "Document chunk:\n{chunk}"
)


def extract_all_skills(document_text, context_summary=""):
    """Extract every skill/technology/methodology mentioned or implied.

    Args:
        document_text: Full document text to analyze.
        context_summary: Optional cross-document context for richer extraction.

    Returns:
        List of skill dicts with name, category, evidence, proficiency_signal, confidence.
    """
    if context_summary:
        items = analyze_with_context(
            document_text, SKILLS_PROMPT, context_summary, task_type="reasoning"
        )
    else:
        items = analyze_with_chunking(document_text, SKILLS_PROMPT, task_type="reasoning")

    return merge_extracted_items(items, "name")
