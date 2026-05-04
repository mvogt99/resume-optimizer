"""JSON Schemas for Google Drive and resume version routes."""

GDRIVE_LIST_200 = {
    "type": "object",
    "additionalProperties": True,
}

GDRIVE_IMPORT_201 = {
    "type": "object",
    "required": ["message", "resume_id"],
    "properties": {
        "message": {"type": "string"},
        "resume_id": {"type": ["string", "integer"]},
        "version_id": {"type": ["string", "integer"]},
        "file_name": {"type": "string"},
        "file_type": {"type": "string"},
        "text_length": {"type": "integer"},
    },
    "additionalProperties": True,
}

VERSIONS_LIST_200 = {
    "type": "object",
    "required": ["versions"],
    "properties": {
        "versions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "source": {"type": "string"},
                    "file_name": {"type": "string"},
                    "file_type": {"type": "string"},
                },
            },
        },
    },
    "additionalProperties": True,
}

VERSION_GET_200 = {
    "type": "object",
    "required": ["id"],
    "properties": {
        "id": {"type": "integer"},
        "source": {"type": "string"},
        "file_name": {"type": "string"},
        "file_type": {"type": "string"},
        "parsed_text": {"type": "string"},
        "metadata": {"type": "object"},
    },
    "additionalProperties": True,
}

VERSION_UPDATE_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
        "id": {"type": "integer"},
    },
    "additionalProperties": True,
}

REIMPORT_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
        "version_id": {"type": "integer"},
        "file_name": {"type": "string"},
        "text_length": {"type": "integer"},
    },
    "additionalProperties": True,
}
