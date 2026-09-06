"""One-time migration: Qdrant hybrid_ai_learnings → journey_sources."""
import hashlib
import json
import logging

import httpx

logger = logging.getLogger(__name__)


def migrate_qdrant_to_journey_sources(conn, qdrant_base_url, collection, user_id=0) -> int:
    url = f"{qdrant_base_url}/collections/{collection}/points/scroll"
    body = {"limit": 100, "with_payload": True, "with_vector": False}
    next_page_offset = None
    total_inserted = 0

    while True:
        if next_page_offset is not None:
            body["offset"] = next_page_offset

        try:
            response = httpx.post(url, json=body, timeout=10)
            response.raise_for_status()
            result = response.json().get("result", {})
            points = result.get("points", [])
            next_page_offset = result.get("next_page_offset")

            for point in points:
                point_id = point["id"]
                payload = point.get("payload", {})
                content = payload.get("content", "")

                if len(content) < 20:
                    continue

                row = conn.execute(
                    "SELECT id FROM journey_sources WHERE source_path=?",
                    [f"hybrid_ai_learnings/{point_id}"],
                ).fetchone()
                if row:
                    continue

                content_hash = hashlib.sha256(content.encode()).hexdigest()
                category = payload.get("category", "")
                timestamp = payload.get("timestamp", "")

                cursor = conn.execute(
                    "INSERT INTO journey_sources "
                    "(source_type, source_path, content_hash, title, content_preview, "
                    "full_text, classification, event_date, metadata_json, user_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                    [
                        "qdrant",
                        f"hybrid_ai_learnings/{point_id}",
                        content_hash,
                        f"Qdrant: {category} ({str(point_id)[:8]})",
                        content[:500],
                        content,
                        "knowledge_base",
                        timestamp[:10] if timestamp else "",
                        json.dumps({"collection": collection, "qdrant_id": point_id, "category": category}),
                        user_id,
                    ],
                )
                if cursor.rowcount:
                    total_inserted += 1

            conn.commit()

        # BOTH are needed: httpx splits transport errors (RequestError) from
        # status errors (HTTPStatusError, raised by raise_for_status above),
        # whereas requests.RequestException was the base of both. Catching only
        # RequestError would let a 4xx/5xx escape where it used to be logged.
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning("Qdrant request failed: %s", e)
            break

        if next_page_offset is None:
            break

    return total_inserted


if __name__ == "__main__":
    import contextlib

    from models import get_db_connection

    logging.basicConfig(level=logging.WARNING)
    # closing() rather than a trailing close(): the migrate call talks to Qdrant
    # over HTTP and can raise, in which case the old trailing close never ran.
    with contextlib.closing(get_db_connection()) as db_conn:
        count = migrate_qdrant_to_journey_sources(db_conn, "http://localhost:6333", "hybrid_ai_learnings", user_id=10)
        print(f"Inserted {count} new records from Qdrant")
