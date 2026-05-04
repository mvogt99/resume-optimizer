"""JSON Schemas for journey routes (/api/journey/*)."""

START_MINING_202 = {
    "type": "object",
    "required": ["message", "job_id"],
    "properties": {
        "message": {"type": "string"},
        "job_id": {"type": "string"},
    },
    "additionalProperties": True,
}

TIMELINE_200 = {
    "type": "object",
    "additionalProperties": True,
}

SKILLS_200 = {
    "type": "object",
    "required": ["skills"],
    "properties": {
        "skills": {"type": "array"},
    },
    "additionalProperties": True,
}

ACHIEVEMENTS_200 = {
    "type": "object",
    "required": ["achievements"],
    "properties": {
        "achievements": {"type": "array"},
    },
    "additionalProperties": True,
}

NARRATIVES_200 = {
    "type": "object",
    "required": ["narratives"],
    "properties": {
        "narratives": {"type": "array"},
    },
    "additionalProperties": True,
}

UPDATE_NARRATIVES_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
    },
    "additionalProperties": True,
}

APPROVE_NARRATIVES_200 = UPDATE_NARRATIVES_200

SOURCES_200 = {
    "type": "object",
    "required": ["sources"],
    "properties": {
        "sources": {"type": "array"},
    },
    "additionalProperties": True,
}

REVIEW_START_200 = {
    "type": "object",
    "required": ["session_id"],
    "properties": {
        "session_id": {"type": "string"},
        "message": {"type": "string"},
    },
    "additionalProperties": True,
}

REVIEW_MESSAGE_200 = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "response": {"type": "string"},
    },
    "additionalProperties": True,
}

REVIEW_APPLY_200 = {
    "type": "object",
    "additionalProperties": True,
}
