"""JSON Schemas for profile routes.

Covers /api/profile/*, /api/deep-profile/*, /api/deep-interview/*, /api/interview-guide/*.
"""

IMPORT_LINKEDIN_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
        "skills_count": {"type": "integer"},
        "experience_count": {"type": "integer"},
        "education_count": {"type": "integer"},
        "recommendations_count": {"type": "integer"},
    },
    "additionalProperties": False,
}

GET_LINKEDIN_200 = {
    "type": "object",
    "additionalProperties": True,
}

BUILD_DEEP_PROFILE_200 = {
    "type": "object",
    "required": ["profile"],
    "properties": {
        "profile": {"type": "object"},
        "source_summary": {"type": "string"},
        "updated_at": {"type": "string"},
    },
    "additionalProperties": False,
}

GET_DEEP_PROFILE_200 = {
    "type": "object",
    "additionalProperties": True,
}

ROLE_SYNTHESIS_200 = {
    "type": "object",
    "additionalProperties": True,
}

DEEP_INTERVIEW_START_200 = {
    "type": "object",
    "required": ["session_id"],
    "properties": {
        "session_id": {"type": "string"},
        "message": {"type": "string"},
    },
    "additionalProperties": False,
}

DEEP_INTERVIEW_MESSAGE_200 = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "response": {"type": "string"},
    },
    "additionalProperties": False,
}

DEEP_INTERVIEW_STATUS_200 = {
    "type": "object",
    "additionalProperties": True,
}

DEEP_INTERVIEW_FINALIZE_200 = {
    "type": "object",
    "additionalProperties": True,
}

DEEP_INTERVIEW_INSIGHTS_200 = {
    "type": "object",
    "additionalProperties": True,
}

INTERVIEW_GUIDE_200 = {
    "type": "object",
    "required": ["interview_personas", "star_examples", "talking_points"],
    "properties": {
        "interview_personas": {"type": "array"},
        "star_examples": {"type": "array"},
        "talking_points": {"type": "array"},
        "key_skills_to_highlight": {"type": "array"},
        "skills_gaps_to_address": {"type": "array"},
        "response_framework": {"type": "object"},
    },
    "additionalProperties": False,
}
