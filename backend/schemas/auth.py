"""JSON Schemas for auth routes (/api/register, /api/login)."""

REGISTER_201 = {
    "type": "object",
    "required": ["message", "user_id", "token"],
    "properties": {
        "message": {"type": "string"},
        "user_id": {"type": ["string", "integer"]},
        "token": {"type": "string"},
    },
    "additionalProperties": False,
}

REGISTER_409 = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {"type": "string"},
    },
    "additionalProperties": False,
}

LOGIN_200 = {
    "type": "object",
    "required": ["message", "user_id", "token"],
    "properties": {
        "message": {"type": "string"},
        "user_id": {"type": ["string", "integer"]},
        "token": {"type": "string"},
    },
    "additionalProperties": False,
}

LOGIN_401 = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {"type": "string"},
    },
    "additionalProperties": False,
}
