"""DynamoDB graph adapter for resume-optimizer — thin shim following cloudlift.bridge pattern.

Drop-in replacement for ArangoClient when CLOUDLIFT_ENV=aws. RO-specific single-table
graph schema on DynamoDB — not replaceable by cloudlift's generic DynamoDBAdapter.
Domain methods live in cloudlift_graph_adapter_domain.py (ArangoClientDomainMixin equivalent).

Follows cloudlift.bridge pattern: no cloud SDK imports at module level; boto3 imported
lazily inside _table() only when CLOUDLIFT_ENV=aws.

Single-table design: ro-test-graph
  pk  = "vertex#{collection}" | "edge#{edge_collection}"
  sk  = _key (SHA-1 hex)

GSIs:
  gsi1-user-collection  PK=user_id,   SK=collection       → user-scoped vertex queries
  gsi2-from-edge        PK=from_id,   SK=edge_collection  → OUTBOUND traversal
  gsi3-to-edge          PK=to_id,     SK=edge_collection  → INBOUND traversal
  gsi4-collection-key   PK=collection, SK=sk              → collection scan / count
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from decimal import Decimal
from typing import Any

from cloudlift_graph_adapter_domain import DynamoDBGraphAdapterDomainMixin

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("DYNAMODB_GRAPH_TABLE", "ro-test-graph")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_SEARCHABLE_COLLECTIONS = {"ro_client_projects", "ro_ai_skills", "ro_journey_milestones"}


def _sha1_key(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def _floats_to_decimal(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_floats_to_decimal(v) for v in obj]
    return obj


def _decimal_to_float(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(v) for v in obj]
    return obj


class DynamoDBGraphAdapter(DynamoDBGraphAdapterDomainMixin):
    """Drop-in replacement for ArangoClient + ArangoClientDomainMixin using DynamoDB."""

    def __init__(self) -> None:
        self._resource = None

    @property
    def is_connected(self) -> bool:
        return True

    def initialize(self) -> bool:
        return True

    def _table(self):
        if self._resource is None:
            import boto3  # noqa: PLC0415
            self._resource = boto3.resource("dynamodb", region_name=AWS_REGION)
        return self._resource.Table(TABLE_NAME)

    def _query_gsi(self, index: str, pk_name: str, pk_val: str,
                   sk_name: str | None = None, sk_val: str | None = None,
                   limit: int | None = None, count_only: bool = False) -> list | int:
        from boto3.dynamodb.conditions import Key  # noqa: PLC0415
        kce = Key(pk_name).eq(pk_val)
        if sk_name and sk_val is not None:
            kce = kce & Key(sk_name).eq(sk_val)
        kwargs: dict[str, Any] = {"IndexName": index, "KeyConditionExpression": kce}
        if count_only:
            kwargs["Select"] = "COUNT"
        if limit:
            kwargs["Limit"] = limit
        resp = self._table().query(**kwargs)
        if count_only:
            return resp["Count"]
        return [_decimal_to_float(i) for i in resp["Items"]]

    # ── Core primitives ───────────────────────────────────────────────────────

    def upsert_vertex(self, collection: str, data: dict[str, Any],
                      key_source: str | None = None) -> str:
        key = _sha1_key(key_source or str(data))
        _id = f"{collection}/{key}"
        item: dict[str, Any] = {
            "pk": f"vertex#{collection}",
            "sk": key,
            "_id": _id,
            "_key": key,
            "collection": collection,
            "data": _floats_to_decimal(data),
        }
        uid = data.get("user_id")
        if uid is not None:
            item["user_id"] = str(uid)
        self._table().put_item(Item=item)
        if collection in _SEARCHABLE_COLLECTIONS:
            try:
                from cloudlift_search_adapter import index_graph_vertex  # noqa: PLC0415
                index_graph_vertex(collection, key, _id, data)
            except Exception as exc:
                logger.warning("[graph_adapter] OpenSearch dual-write failed for %s: %s", _id, exc)
        return _id

    def upsert_edge(self, collection: str, from_id: str, to_id: str,
                    data: dict[str, Any] | None = None) -> str:
        key = _sha1_key(f"{from_id}->{to_id}")
        _id = f"{collection}/{key}"
        self._table().put_item(Item={
            "pk": f"edge#{collection}",
            "sk": key,
            "_id": _id,
            "_key": key,
            "collection": collection,
            "from_id": from_id,
            "to_id": to_id,
            "edge_collection": collection,
            "data": _floats_to_decimal(data or {}),
        })
        return _id

    def get_vertex(self, collection: str, key: str) -> dict[str, Any] | None:
        resp = self._table().get_item(Key={"pk": f"vertex#{collection}", "sk": key})
        item = resp.get("Item")
        if not item:
            return None
        result = dict(_decimal_to_float(item.get("data", {})))
        result["_id"] = item["_id"]
        result["_key"] = item["_key"]
        return result

    def get_neighbors(self, vertex_id: str, edge_collection: str,
                      direction: str = "outbound") -> list[dict[str, Any]]:
        d = direction.upper()
        neighbors: list[dict] = []
        if d in ("OUTBOUND", "ANY"):
            for e in self._query_gsi("gsi2-from-edge", "from_id", vertex_id,
                                     "edge_collection", edge_collection):
                v = self._get_vertex_by_id(e["to_id"])
                if v:
                    neighbors.append(v)
        if d in ("INBOUND", "ANY"):
            for e in self._query_gsi("gsi3-to-edge", "to_id", vertex_id,
                                     "edge_collection", edge_collection):
                v = self._get_vertex_by_id(e["from_id"])
                if v:
                    neighbors.append(v)
        return neighbors

    def delete_vertex(self, collection: str, key: str) -> bool:
        self._table().delete_item(Key={"pk": f"vertex#{collection}", "sk": key})
        return True

    # ── Helpers used by domain mixin ──────────────────────────────────────────

    def _get_vertex_by_id(self, vertex_id: str) -> dict[str, Any] | None:
        parts = vertex_id.split("/", 1)
        if len(parts) != 2:
            return None
        return self.get_vertex(parts[0], parts[1])

    def _scan_collection(self, collection: str) -> list[dict[str, Any]]:
        items = self._query_gsi("gsi4-collection-key", "collection", collection)
        results = []
        for item in items:
            d = dict(item.get("data", {}))
            d["_id"] = item["_id"]
            d["_key"] = item["_key"]
            results.append(d)
        return results

    def _query_by_user_id(self, collection: str, user_id: Any,
                          limit: int | None = None) -> list[dict[str, Any]]:
        items = self._query_gsi("gsi1-user-collection", "user_id", str(user_id),
                                "collection", collection, limit=limit)
        results = []
        for item in items:
            d = dict(item.get("data", {}))
            d["_id"] = item["_id"]
            d["_key"] = item["_key"]
            results.append(d)
        return results

    def _count_collection(self, collection: str) -> int:
        return self._query_gsi("gsi4-collection-key", "collection", collection,
                               count_only=True)

    def _edge_exists(self, to_id: str, edge_collection: str) -> bool:
        return self._query_gsi("gsi3-to-edge", "to_id", to_id,
                               "edge_collection", edge_collection,
                               limit=1, count_only=True) > 0

    # ── Limited AQL translator ────────────────────────────────────────────────

    def query(self, aql: str, bind_vars: dict[str, Any] | None = None) -> list:
        """Translate simple AQL to DynamoDB. LET/complex queries log and return []."""
        bind_vars = bind_vars or {}
        s = " ".join(aql.split())

        if "LET" not in s:
            m = re.search(r"RETURN LENGTH\((\w+)\)", s)
            if m:
                return [self._count_collection(m.group(1))]

        m = re.search(r"FOR \w+ IN (\w+)\s+FILTER \w+\.user_id == @(\w+)", s)
        if m:
            uid = bind_vars.get(m.group(2))
            if uid is not None:
                return self._project_return(s, self._query_by_user_id(m.group(1), uid))

        if "FILTER" not in s and "LET" not in s:
            m = re.search(r"FOR \w+ IN (\w+)\s+RETURN", s)
            if m:
                return self._project_return(s, self._scan_collection(m.group(1)))

        logger.warning("[graph_adapter] unsupported AQL, returning []: %.80s", s)
        return []

    def _project_return(self, aql: str, items: list) -> list:
        m = re.search(r"RETURN\s+\{([^}]+)\}", aql)
        if not m:
            return items
        fields: dict[str, str] = {}
        for part in m.group(1).split(","):
            part = part.strip()
            if ":" in part:
                alias, src = [p.strip() for p in part.split(":", 1)]
                fields[alias] = src.split(".")[-1].strip()
            else:
                fields[part] = part
        return [{alias: item.get(src) for alias, src in fields.items()} for item in items]


# ── Module-level singleton + factory ─────────────────────────────────────────

_dynamo_client: DynamoDBGraphAdapter | None = None


def get_dynamodb_graph_client() -> DynamoDBGraphAdapter:
    global _dynamo_client
    if _dynamo_client is None:
        _dynamo_client = DynamoDBGraphAdapter()
    return _dynamo_client
