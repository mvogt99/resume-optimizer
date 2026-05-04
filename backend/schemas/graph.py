"""JSON Schemas for graph traversal routes (/api/graph/*)."""

TECHNOLOGIES_200 = {
    "type": "object",
    "required": ["technologies"],
    "properties": {
        "technologies": {"type": "array"},
    },
    "additionalProperties": True,
}

CLIENTS_BY_TECH_200 = {
    "type": "object",
    "required": ["clients"],
    "properties": {
        "clients": {"type": "array"},
    },
    "additionalProperties": True,
}

KNOWLEDGE_CONTEXT_200 = {
    "type": "object",
    "additionalProperties": True,
}
