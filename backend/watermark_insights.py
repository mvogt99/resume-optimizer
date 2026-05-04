"""Watermark Insights: Compare consecutive mining runs to detect incremental vs full-scan."""

import json
from datetime import datetime
from models import get_db


def get_watermark_insights(user_id: int) -> dict:
    """Analyze watermark usage in last two mining runs.

    Returns dict with:
      - has_previous_run: bool
      - has_current_run: bool
      - previous_run: dict (started_at, completed_at, watermarks_json, opts_json)
      - current_run: dict
      - analysis: dict (incremental, incremental_sources, full_scan_sources, timestamp_diff_minutes)
    """
    with get_db() as conn:
        runs = conn.execute(
            "SELECT id, started_at, completed_at, opts_json, watermarks_json "
            "FROM journey_mining_runs WHERE user_id = ? AND status = 'completed' "
            "ORDER BY completed_at DESC LIMIT 2",
            (user_id,)
        ).fetchall()

    result = {
        "has_previous_run": len(runs) >= 2,
        "has_current_run": len(runs) >= 1,
        "previous_run": None,
        "current_run": None,
        "analysis": None,
    }

    if not runs:
        return result

    # Current run is most recent (first in DESC order)
    current = dict(runs[0])
    current["opts_json"] = json.loads(current["opts_json"] or "{}")
    current["watermarks_json"] = json.loads(current["watermarks_json"] or "{}")
    result["current_run"] = current

    # Previous run is older (second in DESC order)
    if len(runs) >= 2:
        previous = dict(runs[1])
        previous["opts_json"] = json.loads(previous["opts_json"] or "{}")
        previous["watermarks_json"] = json.loads(previous["watermarks_json"] or "{}")
        result["previous_run"] = previous

        # Perform analysis
        result["analysis"] = _analyze_runs(previous, current)

    return result


def _analyze_runs(previous_run: dict, current_run: dict) -> dict:
    """Compare two runs to detect incremental mining.

    Returns:
      - incremental: bool (did current run use previous watermarks?)
      - incremental_sources: list of sources that used incremental
      - full_scan_sources: list of sources that did full scan
      - timestamp_diff_minutes: int (time between runs)
    """
    prev_watermarks = previous_run["watermarks_json"]
    curr_opts = current_run["opts_json"]

    # Check if current run was incremental (used previous watermarks)
    is_incremental = is_incremental_mining(prev_watermarks, curr_opts)

    # Determine which sources were incremental vs full-scanned
    sources_config = {
        "files": "files" in prev_watermarks,
        "git": "git" in prev_watermarks,
        "arango": "arango" in prev_watermarks,
    }

    incremental_sources = [src for src, has_watermark in sources_config.items() if has_watermark and is_incremental]
    full_scan_sources = [src for src, has_watermark in sources_config.items() if not has_watermark or not is_incremental]

    # Calculate time difference
    prev_time = datetime.fromisoformat(previous_run["completed_at"])
    curr_time = datetime.fromisoformat(current_run["started_at"])
    time_diff = int((curr_time - prev_time).total_seconds() / 60)

    return {
        "incremental": is_incremental,
        "incremental_sources": incremental_sources,
        "full_scan_sources": full_scan_sources,
        "timestamp_diff_minutes": time_diff,
    }


def is_incremental_mining(prev_watermarks: dict, curr_opts: dict) -> bool:
    """Determine if current opts represent incremental mining.

    Incremental = current run used previous watermarks (since_date = watermark["files"])
    Full scan = no previous watermarks or opts didn't use them
    """
    if not prev_watermarks or not prev_watermarks.get("files"):
        # No previous watermarks = can't be incremental
        return False

    # Check if opts["since_date"] matches previous watermark
    since_date = curr_opts.get("since_date")
    if not since_date:
        # No since_date in opts = full scan
        return False

    # Compare with previous watermark
    prev_watermark = prev_watermarks.get("files")
    return since_date == prev_watermark


def get_watermark_sources(watermarks: dict) -> list:
    """Return list of sources that have watermarks."""
    sources = []
    if watermarks.get("files"):
        sources.append("files")
    if watermarks.get("git"):
        sources.append("git")
    if watermarks.get("arango"):
        sources.append("arango")
    return sources
