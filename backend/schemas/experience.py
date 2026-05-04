"""JSON Schemas for experience routes.

Covers /api/experience/*, /api/skills-interview/*, /api/ats-improve/*.
"""

START_SESSION_201 = {
    "type": "object",
    "required": ["session_id"],
    "properties": {
        "session_id": {"type": "string"},
        "message": {"type": "string"},
        "stage": {"type": "string"},
    },
    "additionalProperties": False,
}

SEND_MESSAGE_200 = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "response": {"type": "string"},
        "stage": {"type": "string"},
        "session_id": {"type": "string"},
        "suggestions": {"type": "array"},
        "extracted": {"type": "object"},
    },
    "additionalProperties": False,
}

SUMMARY_200 = {
    "type": "object",
    "properties": {
        "is_finalized": {"type": "boolean"},
        "title": {"type": "string"},
        "employer": {"type": "string"},
        "bullets": {"type": "array"},
    },
    "additionalProperties": False,
}

FINALIZE_200 = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "experience": {"type": "object"},
    },
    "additionalProperties": False,
}

APPLY_201 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
        "resume_id": {"type": ["string", "integer"]},
        "version_id": {"type": ["string", "integer"]},
        "text": {"type": "string"},
    },
    "additionalProperties": False,
}

LIST_200 = {
    "type": "object",
    "required": ["experiences"],
    "properties": {
        "experiences": {"type": "array"},
    },
    "additionalProperties": False,
}

SKILLS_INTERVIEW_START_200 = {
    "type": "object",
    "required": ["session_id"],
    "properties": {
        "session_id": {"type": "string"},
        "message": {"type": "string"},
    },
    "additionalProperties": False,
}

SKILLS_INTERVIEW_SUMMARY_200 = {
    "type": "object",
    "properties": {
        "results": {"type": "object"},
    },
    "additionalProperties": False,
}

ATS_IMPROVE_START_200 = {
    "type": "object",
    "required": ["session_id"],
    "properties": {
        "session_id": {"type": "string"},
        "message": {"type": "string"},
    },
    "additionalProperties": False,
}

ATS_IMPROVE_RESUME_200 = {
    "type": "object",
    "properties": {
        "improved_text": {"type": "string"},
    },
    "additionalProperties": False,
}
