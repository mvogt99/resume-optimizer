"""JSON Schemas for auth routes (/api/register, /api/login)."""

# Registration is APPROVAL-GATED. The ordinary path returns only a message and
# pending=true -- NO credential. The admin path is the only one that returns
# user_id/token/role, so those stay allowed but are not required.
#
# Do not "tighten" this by requiring token again: handing a usable credential to
# an unapproved account defeats the approval gate entirely. The absence is
# deliberate, not an oversight.
REGISTER_201 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
        "pending": {"type": "boolean"},
        "user_id": {"type": ["string", "integer"]},
        "token": {"type": "string"},
        "role": {"type": "string"},
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
