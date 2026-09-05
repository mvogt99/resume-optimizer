"""Phase 4b: Event Clustering - Group related events within 7-day windows.

Algorithm:
1. Fetch all deduped events (post-Phase 4a) for user, sorted by created_at
2. Group events into 7-day rolling windows
3. Within each window, cluster by semantic similarity (>70% SequenceMatcher on titles)
4. Mark cluster head (highest significance_score in cluster)
5. Store cluster_id and is_cluster_head flags in journey_events
"""

from datetime import datetime, timedelta
from difflib import SequenceMatcher
from models import get_db
from db_engine import as_datetime


def cluster_events(user_id: int, window_days: int = 7, similarity_threshold: float = 0.7) -> dict:
    """Cluster events within 7-day windows and mark cluster heads.

    Returns summary dict with:
      - total_events: int
      - clusters_created: int
      - cluster_head_count: int
      - updates_applied: int
    """
    with get_db() as conn:
        # Fetch all events for user, sorted by created_at
        events = conn.execute(
            "SELECT id, title, significance_score, created_at FROM journey_events "
            "WHERE user_id = ? ORDER BY created_at",
            (user_id,)
        ).fetchall()

    if not events:
        return {
            "total_events": 0,
            "clusters_created": 0,
            "cluster_head_count": 0,
            "updates_applied": 0,
        }

    # Group into windows and cluster
    clusters = _create_clusters(events, window_days, similarity_threshold)

    # Apply cluster assignments
    if clusters:
        with get_db() as conn:
            for cluster_id, event_ids in clusters.items():
                for event_id in event_ids:
                    conn.execute(
                        "UPDATE journey_events SET cluster_id = ? WHERE id = ?",
                        (cluster_id, event_id)
                    )
            conn.commit()

    # Mark cluster heads
    cluster_heads = _mark_cluster_heads(user_id, clusters)

    if cluster_heads:
        with get_db() as conn:
            for event_id in cluster_heads:
                conn.execute(
                    "UPDATE journey_events SET is_cluster_head = 1 WHERE id = ?",
                    (event_id,)
                )
            conn.commit()

    # Count how many events were actually assigned to clusters
    clustered_count = len(events) if clusters else 0

    return {
        "total_events": len(events),
        "clusters_created": len(clusters),
        "clustered_events": clustered_count,
        "cluster_head_count": len(cluster_heads),
        "updates_applied": len(events),
    }


def _create_clusters(
    events: list, window_days: int, similarity_threshold: float
) -> dict:
    """Group events into 7-day windows and cluster by similarity.

    Returns {cluster_id: [event_ids]} mapping.
    """
    clusters = {}
    cluster_counter = 0
    processed = set()

    for i, event in enumerate(events):
        if event["id"] in processed:
            continue

        event_date = as_datetime(event["created_at"])
        window_start = event_date - timedelta(days=window_days // 2)
        window_end = event_date + timedelta(days=window_days // 2)

        # Find all events in this window
        window_events = []
        for j, candidate in enumerate(events):
            candidate_date = as_datetime(candidate["created_at"])
            if window_start <= candidate_date <= window_end:
                window_events.append((j, candidate))

        # Cluster within window by similarity
        assigned = set()
        for j, candidate in window_events:
            if candidate["id"] in processed or candidate["id"] in assigned:
                continue

            # Check similarity with cluster seed
            sim = string_similarity(event["title"], candidate["title"])
            if sim >= similarity_threshold or candidate["id"] == event["id"]:
                if cluster_counter not in clusters:
                    clusters[cluster_counter] = []
                clusters[cluster_counter].append(candidate["id"])
                assigned.add(candidate["id"])
                processed.add(candidate["id"])

        cluster_counter += 1

    return clusters


def _mark_cluster_heads(user_id: int, clusters: dict) -> list:
    """Mark highest-significance event in each cluster as cluster head.

    Returns list of cluster head event IDs.
    """
    if not clusters:
        return []

    with get_db() as conn:
        cluster_heads = []
        for cluster_id, event_ids in clusters.items():
            if not event_ids:
                continue

            # Find highest significance in cluster
            placeholders = ",".join("?" * len(event_ids))
            result = conn.execute(
                f"SELECT id FROM journey_events WHERE id IN ({placeholders}) "
                "ORDER BY significance_score DESC, created_at ASC LIMIT 1",
                event_ids
            ).fetchone()

            if result:
                cluster_heads.append(result["id"])

    return cluster_heads


def string_similarity(s1: str, s2: str) -> float:
    """Return 0.0-1.0 similarity score."""
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def get_cluster_summary(user_id: int) -> dict:
    """Get clustering statistics for user.

    Returns:
      - total_events: count of all events
      - clustered_events: count of events with cluster_id set
      - cluster_count: count of distinct clusters
      - cluster_heads: count of events marked as cluster head
      - average_cluster_size: float mean of events per cluster
    """
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        clustered = conn.execute(
            "SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = ? AND cluster_id IS NOT NULL",
            (user_id,)
        ).fetchone()

        clusters = conn.execute(
            "SELECT COUNT(DISTINCT cluster_id) as cnt FROM journey_events WHERE user_id = ? AND cluster_id IS NOT NULL",
            (user_id,)
        ).fetchone()

        heads = conn.execute(
            "SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = ? AND is_cluster_head = 1",
            (user_id,)
        ).fetchone()

    total_count = total["cnt"] if total else 0
    clustered_count = clustered["cnt"] if clustered else 0
    cluster_count = clusters["cnt"] if clusters else 0
    head_count = heads["cnt"] if heads else 0

    avg_size = 0.0
    if cluster_count > 0:
        avg_size = clustered_count / cluster_count

    return {
        "total_events": total_count,
        "clustered_events": clustered_count,
        "cluster_count": cluster_count,
        "cluster_heads": head_count,
        "average_cluster_size": avg_size,
    }
