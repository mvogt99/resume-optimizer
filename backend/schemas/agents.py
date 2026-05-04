"""JSON Schemas for agent routes (/api/agents/*)."""

# --- Job Scout ---

SCOUT_SEARCH_202 = {
    "type": "object",
    "required": ["job_id"],
    "properties": {
        "message": {"type": "string"},
        "job_id": {"type": "string"},
    },
    "additionalProperties": True,
}

SCOUT_POSTINGS_200 = {
    "type": "object",
    "required": ["postings"],
    "properties": {
        "postings": {"type": "array"},
    },
    "additionalProperties": True,
}

SCOUT_POSTING_GET_200 = {
    "type": "object",
    "required": ["id"],
    "properties": {
        "id": {"type": ["string", "integer"]},
        "title": {"type": "string"},
        "company": {"type": "string"},
        "job_description": {"type": "string"},
    },
    "additionalProperties": True,
}

SCOUT_POSTING_CREATE_201 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
        "id": {"type": ["string", "integer"]},
        "posting_id": {"type": ["string", "integer"]},
    },
    "additionalProperties": True,
}

SCOUT_POSTING_UPDATE_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
    },
    "additionalProperties": True,
}

SCOUT_POSTING_DELETE_200 = SCOUT_POSTING_UPDATE_200

SCOUT_CRITERIA_SAVE_201 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
        "criteria_id": {"type": ["string", "integer"]},
    },
    "additionalProperties": True,
}

SCOUT_CRITERIA_LIST_200 = {
    "type": "object",
    "required": ["criteria"],
    "properties": {
        "criteria": {"type": "array"},
    },
    "additionalProperties": True,
}

# --- Application Tracker ---

PIPELINE_GET_200 = {
    "type": "object",
    "required": ["pipeline"],
    "properties": {
        "pipeline": {"type": ["array", "object"]},
    },
    "additionalProperties": True,
}

PIPELINE_MOVE_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
    },
    "additionalProperties": True,
}

PIPELINE_ANALYTICS_200 = {
    "type": "object",
    "additionalProperties": True,
}

PIPELINE_REMINDERS_200 = {
    "type": "object",
    "required": ["reminders"],
    "properties": {
        "reminders": {"type": "array"},
    },
    "additionalProperties": True,
}

PIPELINE_FOLLOWUP_200 = {
    "type": "object",
    "additionalProperties": True,
}

PIPELINE_ANALYZE_200 = {
    "type": "object",
    "additionalProperties": True,
}

# --- Resume Tailor ---

TAILOR_POST_200 = {
    "type": "object",
    "additionalProperties": True,
}

TAILOR_GET_200 = {
    "type": "object",
    "additionalProperties": True,
}

# --- Cover Letter ---

COVER_LETTER_CREATE_201 = {
    "type": "object",
    "additionalProperties": True,
}

COVER_LETTER_GET_200 = {
    "type": "object",
    "additionalProperties": True,
}

# --- Interview Coach ---

COACH_START_201 = {
    "type": "object",
    "required": ["session_id"],
    "properties": {
        "session_id": {"type": "string"},
    },
    "additionalProperties": True,
}

COACH_SESSION_200 = {
    "type": "object",
    "additionalProperties": True,
}

COACH_SESSIONS_200 = {
    "type": "object",
    "required": ["sessions"],
    "properties": {
        "sessions": {"type": "array"},
    },
    "additionalProperties": True,
}

# --- Career Advisor ---

ADVISOR_ANALYZE_200 = {
    "type": "object",
    "additionalProperties": True,
}

# --- Agent System ---

AGENT_RUNS_200 = {
    "type": "object",
    "required": ["runs"],
    "properties": {
        "runs": {"type": "array"},
    },
    "additionalProperties": True,
}

AGENT_STATUS_200 = {
    "type": "object",
    "additionalProperties": True,
}

# --- Generic error ---

ERROR_RESPONSE = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {"type": "string"},
    },
    "additionalProperties": True,
}
