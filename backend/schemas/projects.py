"""JSON Schemas for project routes (/api/projects/*)."""

LIST_PROJECTS_200 = {
    "type": "object",
    "required": ["projects"],
    "properties": {
        "projects": {"type": "array"},
    },
    "additionalProperties": True,
}

CREATE_PROJECT_201 = {
    "type": "object",
    "required": ["message", "project_id"],
    "properties": {
        "message": {"type": "string"},
        "project_id": {"type": "integer"},
    },
    "additionalProperties": True,
}

START_ANALYSIS_202 = {
    "type": "object",
    "required": ["message", "job_id"],
    "properties": {
        "message": {"type": "string"},
        "job_id": {"type": "string"},
    },
    "additionalProperties": True,
}

GET_ANALYSIS_200 = {
    "type": "object",
    "additionalProperties": True,
}

UPDATE_ANALYSIS_200 = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "message": {"type": "string"},
    },
    "additionalProperties": True,
}

APPROVE_ANALYSIS_200 = UPDATE_ANALYSIS_200

LIST_DOCUMENTS_200 = {
    "type": "object",
    "required": ["documents"],
    "properties": {
        "documents": {"type": "array"},
    },
    "additionalProperties": True,
}

LIST_FOLDERS_200 = {
    "type": "object",
    "additionalProperties": True,
}

REANALYZE_202 = START_ANALYSIS_202

RESET_STATUS_200 = {
    "type": "object",
    "required": ["project_id"],
    "properties": {
        "project_id": {"type": "integer"},
        "analysis_status": {"type": "string"},
    },
    "additionalProperties": True,
}
