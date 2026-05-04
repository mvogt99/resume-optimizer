"""JSON Schemas for resume routes."""

UPLOAD_RESUME_201 = {
    "type": "object",
    "required": ["message", "resume_id"],
    "properties": {
        "message": {"type": "string"},
        "resume_id": {"type": ["string", "integer"]},
    },
    "additionalProperties": False,
}

UPLOAD_JD_201 = {
    "type": "object",
    "required": ["message", "job_id"],
    "properties": {
        "message": {"type": "string"},
        "job_id": {"type": ["string", "integer"]},
    },
    "additionalProperties": False,
}

OPTIMIZE_200 = {
    "type": "object",
    "required": ["optimized_resume", "ats_compliance_score"],
    "properties": {
        "optimized_resume": {"type": "object"},
        "keywords_added": {"type": "integer"},
        "relevance_score": {"type": "number"},
        "ats_compliance_score": {"type": "number"},
        "score_breakdown": {"type": "object"},
        "accomplishments": {"type": "array"},
        "recommendations": {"type": "array"},
        "original_resume_text": {"type": "string"},
        "job_description_text": {"type": "string"},
        "sections_found": {"type": "object"},
        "skill_phrases_matched": {"type": "array"},
        "resume_source": {"type": "string"},
        "resume_name": {"type": "string"},
    },
    "additionalProperties": False,
}

SKILLS_GAP_200 = {
    "type": "object",
    "required": ["skills_gap"],
    "properties": {
        "skills_gap": {"type": "object"},
        "relevant_accomplishments": {"type": "array"},
        "relevant_recommendations": {"type": "array"},
    },
    "additionalProperties": False,
}

FROM_LINKEDIN_201 = {
    "type": "object",
    "required": ["message", "resume_id"],
    "properties": {
        "message": {"type": "string"},
        "resume_id": {"type": ["string", "integer"]},
        "profile_summary": {"type": "object"},
    },
    "additionalProperties": False,
}
