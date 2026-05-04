"""JSON Schemas for session routes (/api/sessions/*)."""

CREATE_SESSION_201 = {
    "type": "object",
    "required": ["id"],
    "properties": {
        "id": {"type": "integer"},
        "user_id": {"type": "integer"},
        "session_name": {"type": "string"},
        "resume_id": {"type": ["integer", "null"]},
        "resume_version_id": {"type": ["integer", "null"]},
        "job_description_text": {"type": "string"},
        "ats_score": {"type": ["number", "null"]},
        "created_at": {"type": "string"},
        "updated_at": {"type": "string"},
    },
    "additionalProperties": True,
}

LIST_SESSIONS_200 = {
    "type": "object",
    "required": ["sessions"],
    "properties": {
        "sessions": {"type": "array"},
    },
    "additionalProperties": True,
}

GET_SESSION_200 = CREATE_SESSION_201

UPDATE_SESSION_200 = {
    "type": "object",
    "additionalProperties": True,
}

DELETE_SESSION_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
    },
    "additionalProperties": True,
}

OPTIMIZE_SESSION_200 = {
    "type": "object",
    "required": ["optimized_resume", "ats_compliance_score"],
    "properties": {
        "optimized_resume": {"type": "object"},
        "ats_compliance_score": {"type": "number"},
        "keywords_added": {"type": "integer"},
        "relevance_score": {"type": "number"},
    },
    "additionalProperties": True,
}
