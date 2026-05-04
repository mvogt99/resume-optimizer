"""JSON Schemas for campaign routes (/api/campaigns/*)."""

INTERVIEW_START_201 = {
    "type": "object",
    "required": ["session_id"],
    "properties": {
        "session_id": {"type": "string"},
        "message": {"type": "string"},
        "stage": {"type": "string"},
    },
    "additionalProperties": True,
}

INTERVIEW_MESSAGE_200 = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "response": {"type": "string"},
        "stage": {"type": "string"},
        "suggestions": {"type": "array"},
        "context": {"type": "object"},
    },
    "additionalProperties": True,
}

SESSION_STATE_200 = {
    "type": "object",
    "properties": {
        "stage": {"type": "string"},
        "session_id": {"type": "string"},
    },
    "additionalProperties": True,
}

CREATE_CAMPAIGN_201 = {
    "type": "object",
    "required": ["id"],
    "properties": {
        "id": {"type": "integer"},
        "theme": {"type": "string"},
        "audience": {"type": "string"},
        "tone": {"type": "string"},
        "cadence": {"type": "string"},
        "status": {"type": "string"},
        "storyline": {"type": "string"},
        "post_count": {"type": "integer"},
    },
    "additionalProperties": True,
}

LIST_CAMPAIGNS_200 = {
    "type": "object",
    "required": ["campaigns"],
    "properties": {
        "campaigns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "theme": {"type": "string"},
                    "audience": {"type": "string"},
                    "tone": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
        },
    },
    "additionalProperties": True,
}

GET_CAMPAIGN_200 = {
    "type": "object",
    "required": ["id"],
    "properties": {
        "id": {"type": "integer"},
        "theme": {"type": "string"},
        "audience": {"type": "string"},
        "tone": {"type": "string"},
        "cadence": {"type": "string"},
        "status": {"type": "string"},
        "storyline": {"type": "string"},
        "post_count": {"type": "integer"},
        "created_at": {"type": "string"},
        "metadata": {"type": "object"},
    },
    "additionalProperties": True,
}

UPDATE_CAMPAIGN_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
    },
    "additionalProperties": True,
}

DELETE_CAMPAIGN_200 = UPDATE_CAMPAIGN_200

GENERATE_POSTS_202 = {
    "type": "object",
    "required": ["message", "job_id"],
    "properties": {
        "message": {"type": "string"},
        "job_id": {"type": "string"},
    },
    "additionalProperties": True,
}

LIST_POSTS_200 = {
    "type": "object",
    "required": ["posts"],
    "properties": {
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "campaign_id": {"type": "integer"},
                    "position": {"type": "integer"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
    },
    "additionalProperties": True,
}

ADD_POST_201 = {
    "type": "object",
    "required": ["message", "post_id"],
    "properties": {
        "message": {"type": "string"},
        "post_id": {"type": "integer"},
    },
    "additionalProperties": True,
}

UPDATE_POST_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
    },
    "additionalProperties": True,
}

DELETE_POST_200 = UPDATE_POST_200

REORDER_POSTS_200 = UPDATE_POST_200

EXPORT_200 = {
    "type": "object",
    "required": ["text", "post_count"],
    "properties": {
        "text": {"type": "string"},
        "post_count": {"type": "integer"},
    },
    "additionalProperties": True,
}

ANALYTICS_200 = {
    "type": "object",
    "additionalProperties": True,
}

UPDATE_INTERVIEW_200 = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string"},
        "message": {"type": "string"},
        "stage": {"type": "string"},
        "context": {"type": "object"},
        "suggestions": {"type": "array"},
    },
    "additionalProperties": True,
}
