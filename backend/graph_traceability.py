"""P2-B: Graph traceability — resume version vertices + sourced_from edges.

Writes ro_resume_versions vertices and ro_version_sourced_from edges to
ArangoDB after resume generation, enabling "why does this bullet exist?" queries.
Also provides evidence coverage analytics and untapped evidence prompt injection.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Write resume version to graph
# ---------------------------------------------------------------------------


def write_resume_version_to_graph(
    user_id: int,
    version_id: int,
    source: str,
    posting: dict,
    evidence_refs: list,
) -> str | None:
    """Upsert a resume version vertex and sourced_from edges to ArangoDB.

    Args:
        user_id: User who owns the version.
        version_id: SQLite resume_versions.id.
        source: e.g. "agent_tailor", "experience", "linkedin".
        posting: Job posting dict (title, company).
        evidence_refs: List of dicts with _id, type, confidence, section.

    Returns:
        ArangoDB vertex ID string, or None if not connected.
    """
    from arango_client import get_arango_client

    client = get_arango_client()
    if not client.is_connected:
        return None

    title = posting.get("title", "")
    company = posting.get("company", "")
    now = datetime.now(timezone.utc).isoformat()

    version_vid = client.upsert_vertex(
        "ro_resume_versions",
        {
            "user_id": user_id,
            "version_id": version_id,
            "source": source,
            "job_title": title,
            "company": company,
            "created_at": now,
        },
        key_source=f"resume-version-{version_id}",
    )

    for ref in evidence_refs:
        ref_id = ref.get("_id", "")
        if not ref_id:
            continue
        client.upsert_edge(
            "ro_version_sourced_from",
            version_vid,
            ref_id,
            {
                "reference_type": ref.get("type", ""),
                "confidence": ref.get("confidence", 1.0),
                "section": ref.get("section", ""),
            },
        )

    return version_vid


# ---------------------------------------------------------------------------
# Extract evidence references from tailored text
# ---------------------------------------------------------------------------


def extract_evidence_references(tailored_text: str, user_id: int) -> list:
    """Match client names, outcomes, and milestones mentioned in tailored text.

    Returns a list of dicts: {_id, type, confidence, section}.
    Confidence is lower for fuzzy matches.
    """
    from arango_client import get_arango_client

    client = get_arango_client()
    if not client.is_connected or not tailored_text:
        return []

    refs = []
    text_lower = tailored_text.lower()

    # Match client projects by client_name
    clients = client.query(
        "FOR c IN ro_client_projects FILTER c.user_id == @uid"
        " RETURN {_id: c._id, name: c.client_name}",
        {"uid": user_id},
    )
    for c in clients:
        name = (c.get("name") or "").lower()
        if name and name in text_lower:
            refs.append({"_id": c["_id"], "type": "client", "confidence": 0.9, "section": ""})

    # Match business outcomes by title
    outcomes = client.query(
        "FOR o IN ro_business_outcomes RETURN {_id: o._id, name: o.title}",
        {},
    )
    for o in outcomes:
        name = (o.get("name") or "").lower()
        if name and len(name) > 5 and name in text_lower:
            refs.append({"_id": o["_id"], "type": "outcome", "confidence": 0.8, "section": ""})

    # Match journey milestones by title
    milestones = client.query(
        "FOR m IN ro_journey_milestones RETURN {_id: m._id, name: m.title}",
        {},
    )
    for m in milestones:
        name = (m.get("name") or "").lower()
        if name and len(name) > 5 and name in text_lower:
            refs.append({"_id": m["_id"], "type": "milestone", "confidence": 0.7, "section": ""})

    return refs


# ---------------------------------------------------------------------------
# Evidence coverage analytics
# ---------------------------------------------------------------------------


def get_evidence_coverage() -> dict:
    """Return evidence coverage stats for the knowledge graph.

    Returns:
        {total_evidence, evidence_used, evidence_untapped, coverage_pct, untapped_items}
    """
    from arango_client import get_arango_client

    empty = {
        "total_evidence": 0,
        "evidence_used": 0,
        "evidence_untapped": 0,
        "coverage_pct": 0.0,
        "untapped_items": [],
    }

    client = get_arango_client()
    if not client.is_connected:
        return empty

    try:
        total_clients = client.query("RETURN LENGTH(ro_client_projects)")[0]
        total_outcomes = client.query("RETURN LENGTH(ro_business_outcomes)")[0]
        total_milestones = client.query("RETURN LENGTH(ro_journey_milestones)")[0]
        total = total_clients + total_outcomes + total_milestones

        # Evidence with at least one inbound version edge
        used_rows = client.query(
            """
            LET used_clients = (
                FOR c IN ro_client_projects
                    LET edges = (
                        FOR e IN ro_version_sourced_from
                            FILTER e._to == c._id LIMIT 1 RETURN 1
                    )
                    FILTER LENGTH(edges) > 0
                    RETURN 1
            )
            LET used_outcomes = (
                FOR o IN ro_business_outcomes
                    LET edges = (
                        FOR e IN ro_version_sourced_from
                            FILTER e._to == o._id LIMIT 1 RETURN 1
                    )
                    FILTER LENGTH(edges) > 0
                    RETURN 1
            )
            LET used_milestones = (
                FOR m IN ro_journey_milestones
                    LET edges = (
                        FOR e IN ro_version_sourced_from
                            FILTER e._to == m._id LIMIT 1 RETURN 1
                    )
                    FILTER LENGTH(edges) > 0
                    RETURN 1
            )
            RETURN LENGTH(used_clients) + LENGTH(used_outcomes) + LENGTH(used_milestones)
            """,
            {},
        )
        used = used_rows[0] if used_rows else 0

        untapped = get_untapped_evidence(limit=20)
        pct = round(used / total * 100, 1) if total > 0 else 0.0

        return {
            "total_evidence": total,
            "evidence_used": used,
            "evidence_untapped": total - used,
            "coverage_pct": pct,
            "untapped_items": untapped,
        }
    except Exception as e:
        logger.warning("get_evidence_coverage failed: %s", e)
        return empty


def get_untapped_evidence(limit: int = 5) -> list:
    """Return evidence vertices with zero inbound version edges."""
    from arango_client import get_arango_client

    client = get_arango_client()
    if not client.is_connected:
        return []

    try:
        rows = client.query(
            """
            LET untapped_clients = (
                FOR c IN ro_client_projects
                    LET edges = (
                        FOR e IN ro_version_sourced_from
                            FILTER e._to == c._id LIMIT 1 RETURN 1
                    )
                    FILTER LENGTH(edges) == 0
                    RETURN {type: "client", name: c.client_name, _id: c._id}
            )
            LET untapped_outcomes = (
                FOR o IN ro_business_outcomes
                    LET edges = (
                        FOR e IN ro_version_sourced_from
                            FILTER e._to == o._id LIMIT 1 RETURN 1
                    )
                    FILTER LENGTH(edges) == 0
                    RETURN {type: "outcome", name: o.title, _id: o._id}
            )
            LET untapped_milestones = (
                FOR m IN ro_journey_milestones
                    LET edges = (
                        FOR e IN ro_version_sourced_from
                            FILTER e._to == m._id LIMIT 1 RETURN 1
                    )
                    FILTER LENGTH(edges) == 0
                    RETURN {type: "milestone", name: m.title, _id: m._id}
            )
            RETURN SLICE(
                APPEND(APPEND(untapped_clients, untapped_outcomes), untapped_milestones),
                0, @lim
            )
            """,
            {"lim": limit},
        )
        return rows[0] if rows else []
    except Exception as e:
        logger.warning("get_untapped_evidence failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Prompt injection
# ---------------------------------------------------------------------------


def build_untapped_prompt_injection(untapped_items: list) -> str:
    """Build a prompt snippet listing untapped evidence for the tailor to consider."""
    if not untapped_items:
        return ""

    lines = ["Consider highlighting these under-represented achievements:"]
    for item in untapped_items[:5]:
        name = item.get("name", "")
        kind = item.get("type", "")
        if name:
            lines.append(f"  - [{kind}] {name}")
    return "\n".join(lines)
