"""JSON Schemas for background job routes (/api/jobs/*)."""

LIST_JOBS_200 = {
    "type": "object",
    "required": ["jobs"],
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "user_id": {"type": "integer"},
                    "status": {"type": "string"},
                    "progress": {"type": "number"},
                },
            },
        },
    },
    "additionalProperties": False,
}

JOB_STATUS_200 = {
    "type": "object",
    "required": ["id", "status"],
    "properties": {
        "id": {"type": "string"},
        "type": {"type": "string"},
        "user_id": {"type": "integer"},
        "status": {"type": "string"},
        "progress": {"type": "number"},
        "result": {"type": ["object", "null"]},
        "error": {"type": ["string", "null"]},
        "created_at": {"type": ["string", "null"]},
        "started_at": {"type": ["string", "null"]},
        "completed_at": {"type": ["string", "null"]},
    },
    "additionalProperties": False,
}

CANCEL_JOB_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
    },
    "additionalProperties": False,
}
