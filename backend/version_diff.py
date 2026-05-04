"""Resume version diffing — compare two resume versions side-by-side."""

import difflib
import logging
import re

from models import get_db

logger = logging.getLogger(__name__)


def _is_section_header(line):
    """Detect section headers: ALL CAPS lines or lines ending with ':'."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.endswith(":") and len(stripped) > 3:
        return True
    # ALL CAPS with at least 3 alpha chars
    alpha = re.sub(r"[^A-Za-z]", "", stripped)
    return len(alpha) >= 3 and stripped == stripped.upper()


def _get_version(version_id, user_id):
    """Load a resume version by ID, verifying ownership."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, user_id, file_name, source, parsed_text, created_at "
            "FROM resume_versions WHERE id = ?",
            (version_id,),
        ).fetchone()
    if not row:
        return None
    if str(row["user_id"]) != str(user_id):
        return None
    return dict(row)


def diff_versions(user_id, version_id_a, version_id_b):
    """Compare two resume versions. Returns diff lines and summary stats."""
    ver_a = _get_version(version_id_a, user_id)
    ver_b = _get_version(version_id_b, user_id)

    if not ver_a:
        return {"error": f"Version {version_id_a} not found or not yours"}
    if not ver_b:
        return {"error": f"Version {version_id_b} not found or not yours"}

    text_a = (ver_a["parsed_text"] or "").splitlines(keepends=True)
    text_b = (ver_b["parsed_text"] or "").splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            text_a,
            text_b,
            fromfile=ver_a["file_name"] or f"v{version_id_a}",
            tofile=ver_b["file_name"] or f"v{version_id_b}",
            lineterm="",
        )
    )

    added = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))
    changed = min(added, removed)

    # Detect which section headers differ
    sections_a = {
        ln.strip() for ln in (ver_a["parsed_text"] or "").splitlines() if _is_section_header(ln)
    }
    sections_b = {
        ln.strip() for ln in (ver_b["parsed_text"] or "").splitlines() if _is_section_header(ln)
    }
    sections_changed = sorted(sections_a.symmetric_difference(sections_b))

    # Also find sections containing changed lines
    current_section = None
    changed_sections = set()
    for line in diff_lines:
        clean = line.lstrip("+-").strip()
        if _is_section_header(clean):
            current_section = clean
        elif (line.startswith("+") or line.startswith("-")) and current_section:
            changed_sections.add(current_section)

    all_changed = sorted(set(sections_changed) | changed_sections)

    return {
        "version_a": {
            "id": ver_a["id"],
            "file_name": ver_a["file_name"],
            "created_at": ver_a["created_at"],
        },
        "version_b": {
            "id": ver_b["id"],
            "file_name": ver_b["file_name"],
            "created_at": ver_b["created_at"],
        },
        "diff_lines": [ln.rstrip("\n") for ln in diff_lines],
        "stats": {"added": added, "removed": removed, "changed": changed},
        "sections_changed": all_changed,
    }


def list_versions_for_diff(user_id):
    """List all resume versions for a user (for diff picker UI)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, file_name, source, created_at FROM resume_versions "
            "WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]
