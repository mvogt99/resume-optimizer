"""
ArangoDB client for resume optimizer knowledge graph.
Uses `ro_` prefix on all collections to avoid gateway collisions.
SHA-1 keys for deterministic upserts (proven gateway pattern).
"""

import hashlib
import os

from arango_client_domain import ArangoClientDomainMixin

_arango_client = None

# ArangoDB connection settings
ARANGO_HOST = os.environ.get("ARANGO_HOST", "http://localhost:8529")
ARANGO_DB = os.environ.get("ARANGO_DB", "hybrid_ai")
ARANGO_USER = os.environ.get("ARANGO_USER", "root")
ARANGO_PASSWORD = os.environ.get("ARANGO_PASSWORD", "hybrid_ai_root")

# Phase 9 collections
P9_VERTEX_COLLECTIONS = [
    "ro_client_projects",
    "ro_technologies",
    "ro_governance_controls",
    "ro_outcomes",
    "ro_source_documents",
    "ro_skills",
]
P9_EDGE_COLLECTIONS = [
    "ro_client_used_tech",
    "ro_client_required_governance",
    "ro_client_produced_outcome",
    "ro_document_supports",
    "ro_client_demonstrated_skill",
]

# Phase 10 collections
P10_VERTEX_COLLECTIONS = [
    "ro_journey_milestones",
    "ro_ai_skills",
    "ro_journey_projects",
]
P10_EDGE_COLLECTIONS = [
    "ro_milestone_demonstrated_skill",
    "ro_project_used_skill",
    "ro_milestone_belongs_to_project",
]

# Phase 11 collections
P11_VERTEX_COLLECTIONS = [
    "ro_campaigns",
    "ro_campaign_posts",
]
P11_EDGE_COLLECTIONS = [
    "ro_campaign_contains_post",
    "ro_post_references_client",
    "ro_post_references_skill",
    "ro_post_references_milestone",
    "ro_post_references_outcome",
]

# Phase 13 collections — business outcomes
P13_VERTEX_COLLECTIONS = [
    "ro_business_outcomes",
]
P13_EDGE_COLLECTIONS = [
    "ro_outcome_driven_by_skill",
    "ro_outcome_enabled_by_tech",
    "ro_client_achieved_outcome",
]

# Phase 14 collections — deep profile
P14_VERTEX_COLLECTIONS = [
    "ro_deep_profiles",
]
P14_EDGE_COLLECTIONS = [
    "ro_profile_demonstrates_skill",
    "ro_profile_achieved_outcome",
]

# Phase P2-B collections — resume version traceability
P2B_VERTEX_COLLECTIONS = [
    "ro_resume_versions",
]
P2B_EDGE_COLLECTIONS = [
    "ro_version_sourced_from",
]

ALL_VERTEX = (
    P9_VERTEX_COLLECTIONS
    + P10_VERTEX_COLLECTIONS
    + P11_VERTEX_COLLECTIONS
    + P13_VERTEX_COLLECTIONS
    + P14_VERTEX_COLLECTIONS
    + P2B_VERTEX_COLLECTIONS
)
ALL_EDGE = (
    P9_EDGE_COLLECTIONS
    + P10_EDGE_COLLECTIONS
    + P11_EDGE_COLLECTIONS
    + P13_EDGE_COLLECTIONS
    + P14_EDGE_COLLECTIONS
    + P2B_EDGE_COLLECTIONS
)
GRAPH_NAME = "ro_knowledge_graph"


def _sha1_key(text):
    return hashlib.sha1(text.encode()).hexdigest()


class ArangoClient(ArangoClientDomainMixin):
    """Direct python-arango client for the resume optimizer knowledge graph."""

    def __init__(self):
        self._db = None
        self._graph = None

    def initialize(self):
        try:
            from arango import ArangoClient as _ArangoClient

            client = _ArangoClient(hosts=ARANGO_HOST)
            self._db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASSWORD)

            # Ensure vertex collections exist
            existing = [c["name"] for c in self._db.collections() if not c["name"].startswith("_")]
            for coll in ALL_VERTEX:
                if coll not in existing:
                    self._db.create_collection(coll)

            # Ensure edge collections exist
            for coll in ALL_EDGE:
                if coll not in existing:
                    self._db.create_collection(coll, edge=True)

            # Create or get named graph
            if not self._db.has_graph(GRAPH_NAME):
                edge_defs = [
                    {
                        "edge_collection": "ro_client_used_tech",
                        "from_vertex_collections": ["ro_client_projects"],
                        "to_vertex_collections": ["ro_technologies"],
                    },
                    {
                        "edge_collection": "ro_client_required_governance",
                        "from_vertex_collections": ["ro_client_projects"],
                        "to_vertex_collections": ["ro_governance_controls"],
                    },
                    {
                        "edge_collection": "ro_client_produced_outcome",
                        "from_vertex_collections": ["ro_client_projects"],
                        "to_vertex_collections": ["ro_outcomes"],
                    },
                    {
                        "edge_collection": "ro_document_supports",
                        "from_vertex_collections": ["ro_source_documents"],
                        "to_vertex_collections": [
                            "ro_client_projects",
                            "ro_technologies",
                            "ro_outcomes",
                        ],
                    },
                    {
                        "edge_collection": "ro_milestone_demonstrated_skill",
                        "from_vertex_collections": ["ro_journey_milestones"],
                        "to_vertex_collections": ["ro_ai_skills"],
                    },
                    {
                        "edge_collection": "ro_project_used_skill",
                        "from_vertex_collections": ["ro_journey_projects"],
                        "to_vertex_collections": ["ro_ai_skills"],
                    },
                    {
                        "edge_collection": "ro_milestone_belongs_to_project",
                        "from_vertex_collections": ["ro_journey_milestones"],
                        "to_vertex_collections": ["ro_journey_projects"],
                    },
                    # Phase 11 edges
                    {
                        "edge_collection": "ro_campaign_contains_post",
                        "from_vertex_collections": ["ro_campaigns"],
                        "to_vertex_collections": ["ro_campaign_posts"],
                    },
                    {
                        "edge_collection": "ro_post_references_client",
                        "from_vertex_collections": ["ro_campaign_posts"],
                        "to_vertex_collections": ["ro_client_projects"],
                    },
                    {
                        "edge_collection": "ro_post_references_skill",
                        "from_vertex_collections": ["ro_campaign_posts"],
                        "to_vertex_collections": ["ro_ai_skills"],
                    },
                    {
                        "edge_collection": "ro_post_references_milestone",
                        "from_vertex_collections": ["ro_campaign_posts"],
                        "to_vertex_collections": ["ro_journey_milestones"],
                    },
                    {
                        "edge_collection": "ro_post_references_outcome",
                        "from_vertex_collections": ["ro_campaign_posts"],
                        "to_vertex_collections": ["ro_business_outcomes"],
                    },
                    {
                        "edge_collection": "ro_client_demonstrated_skill",
                        "from_vertex_collections": ["ro_client_projects"],
                        "to_vertex_collections": ["ro_skills"],
                    },
                    # Phase 13 edges — business outcomes
                    {
                        "edge_collection": "ro_outcome_driven_by_skill",
                        "from_vertex_collections": ["ro_business_outcomes"],
                        "to_vertex_collections": ["ro_skills"],
                    },
                    {
                        "edge_collection": "ro_outcome_enabled_by_tech",
                        "from_vertex_collections": ["ro_business_outcomes"],
                        "to_vertex_collections": ["ro_technologies"],
                    },
                    {
                        "edge_collection": "ro_client_achieved_outcome",
                        "from_vertex_collections": ["ro_client_projects"],
                        "to_vertex_collections": ["ro_business_outcomes"],
                    },
                    # Phase 14 edges — deep profile
                    {
                        "edge_collection": "ro_profile_demonstrates_skill",
                        "from_vertex_collections": ["ro_deep_profiles"],
                        "to_vertex_collections": ["ro_ai_skills"],
                    },
                    {
                        "edge_collection": "ro_profile_achieved_outcome",
                        "from_vertex_collections": ["ro_deep_profiles"],
                        "to_vertex_collections": ["ro_business_outcomes"],
                    },
                    # Phase P2-B edges — resume version traceability
                    {
                        "edge_collection": "ro_version_sourced_from",
                        "from_vertex_collections": ["ro_resume_versions"],
                        "to_vertex_collections": [
                            "ro_client_projects",
                            "ro_business_outcomes",
                            "ro_journey_milestones",
                        ],
                    },
                ]
                self._db.create_graph(GRAPH_NAME, edge_definitions=edge_defs)
            self._graph = self._db.graph(GRAPH_NAME)
            return True
        except Exception as e:
            print(f"[arango_client] Failed to initialize: {e}")
            self._db = None
            return False

    @property
    def is_connected(self):
        return self._db is not None

    def upsert_vertex(self, collection, data, key_source=None):
        if not self._db:
            return None
        key = _sha1_key(key_source or str(data))
        data["_key"] = key
        coll = self._db.collection(collection)
        if coll.has(key):
            coll.update(data)
        else:
            coll.insert(data)
        return f"{collection}/{key}"

    def upsert_edge(self, collection, from_id, to_id, data=None):
        if not self._db:
            return None
        edge_data = dict(data or {})
        edge_data["_from"] = from_id
        edge_data["_to"] = to_id
        key = _sha1_key(f"{from_id}->{to_id}")
        edge_data["_key"] = key
        if not self._db.has_collection(collection):
            self._db.create_collection(collection, edge=True)
        coll = self._db.collection(collection)
        if coll.has(key):
            coll.update(edge_data)
        else:
            coll.insert(edge_data)
        return f"{collection}/{key}"

    def query(self, aql, bind_vars=None):
        if not self._db:
            return []
        cursor = self._db.aql.execute(aql, bind_vars=bind_vars or {})
        return list(cursor)

    def get_vertex(self, collection, key):
        if not self._db:
            return None
        coll = self._db.collection(collection)
        if coll.has(key):
            return coll.get(key)
        return None

    def get_neighbors(self, vertex_id, edge_collection, direction="outbound"):
        if not self._db:
            return []
        direction_upper = direction.upper()
        if direction_upper not in ("OUTBOUND", "INBOUND", "ANY"):
            direction_upper = "OUTBOUND"
        if not self._db.has_collection(edge_collection):
            return []
        aql = f"""
            FOR v, e IN 1..1 {direction_upper} @start_vertex
                @@edge_coll
                RETURN v
        """
        return self.query(aql, {"start_vertex": vertex_id, "@edge_coll": edge_collection})

    def delete_vertex(self, collection, key):
        if not self._db:
            return False
        coll = self._db.collection(collection)
        if coll.has(key):
            coll.delete(key)
            return True
        return False

    # Domain methods (Phase 9–P2-B) are in ArangoClientDomainMixin (arango_client_domain.py).


# Module-level singleton
def get_arango_client():
    global _arango_client
    if _arango_client is None:
        _arango_client = ArangoClient()
        _arango_client.initialize()
    return _arango_client


def get_graph_client():
    """Return graph client for the current environment.

    CLOUDLIFT_ENV=aws  → DynamoDBGraphAdapter (Phase 3.2)
    CLOUDLIFT_ENV=local → ArangoClient (unchanged)
    """
    import os
    if os.environ.get("CLOUDLIFT_ENV") == "aws":
        from cloudlift_graph_adapter import get_dynamodb_graph_client
        return get_dynamodb_graph_client()
    return get_arango_client()
