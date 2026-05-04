#!/usr/bin/env python3
"""
Post-mine analysis for Phase 2: Incremental Mining.
Captures metrics after mining job completes.
"""
import sqlite3
import json
from datetime import datetime

def get_post_mine_counts():
    """Capture post-mine metrics from SQLite."""
    conn = sqlite3.connect('backend/database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Total counts
    cursor.execute("SELECT COUNT(*) as count FROM journey_sources WHERE user_id = 10")
    post_sources = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM journey_events WHERE user_id = 10")
    post_events = cursor.fetchone()['count']

    # Breakdown by source_type
    cursor.execute("""
      SELECT source_type, COUNT(*) as count FROM journey_sources
      WHERE user_id = 10
      GROUP BY source_type
      ORDER BY count DESC
    """)
    source_breakdown = {row['source_type']: row['count'] for row in cursor.fetchall()}

    # Breakdown by event category
    cursor.execute("""
      SELECT category, COUNT(*) as count FROM journey_events
      WHERE user_id = 10
      GROUP BY category
      ORDER BY count DESC
    """)
    event_breakdown = {row['category']: row['count'] for row in cursor.fetchall()}

    # Latest event date
    cursor.execute("SELECT MAX(event_date) as latest_date FROM journey_events WHERE user_id = 10")
    latest_date = cursor.fetchone()['latest_date']

    # Spot-check: sample 5 recent git_commit sources for accuracy
    cursor.execute("""
      SELECT id, source_type, source_path, created_at
      FROM journey_sources
      WHERE user_id = 10 AND source_type = 'git_commit'
      ORDER BY created_at DESC
      LIMIT 5
    """)
    spot_check_sources = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": 10,
        "sources": {
            "total": post_sources,
            "breakdown": source_breakdown
        },
        "events": {
            "total": post_events,
            "breakdown": event_breakdown
        },
        "latest_event_date": latest_date,
        "spot_check_git_commits": spot_check_sources
    }

if __name__ == "__main__":
    metrics = get_post_mine_counts()
    print(json.dumps(metrics, indent=2, default=str))
