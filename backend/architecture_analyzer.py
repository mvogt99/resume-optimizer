"""Architecture diagram analysis — extract insights from document descriptions."""

import logging

from llm_helper import call_llm_quality, extract_json
from models import get_db

logger = logging.getLogger(__name__)


def _get_architecture_docs(user_id, project_id=None):
    """Find project documents related to architecture/design."""
    with get_db() as conn:
        if project_id:
            rows = conn.execute(
                "SELECT pd.id, pd.file_name, pd.parsed_text, pd.classification_json, "
                "cp.client_name FROM project_documents pd "
                "JOIN client_projects cp ON pd.client_id = cp.id "
                "WHERE cp.user_id = ? AND pd.client_id = ?",
                (user_id, project_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT pd.id, pd.file_name, pd.parsed_text, pd.classification_json, "
                "cp.client_name FROM project_documents pd "
                "JOIN client_projects cp ON pd.client_id = cp.id "
                "WHERE cp.user_id = ?",
                (user_id,),
            ).fetchall()

    arch_docs = []
    arch_keywords = (
        "architecture",
        "design",
        "diagram",
        "integration",
        "infrastructure",
        "topology",
    )

    for row in rows:
        fname = (row["file_name"] or "").lower()
        classification = row["classification_json"] or ""
        text = row["parsed_text"] or ""

        is_arch = any(kw in fname for kw in arch_keywords)
        if not is_arch:
            is_arch = any(kw in classification.lower() for kw in arch_keywords)
        if not is_arch:
            # Check first 500 chars of text for architecture mentions
            is_arch = any(kw in text[:500].lower() for kw in arch_keywords)

        if is_arch and text:
            arch_docs.append(dict(row))

    return arch_docs


def analyze_architecture(user_id, project_id=None):
    """Analyze architecture-related text from project documents."""
    docs = _get_architecture_docs(user_id, project_id)

    if not docs:
        return {
            "project": "",
            "components": [],
            "integrations": [],
            "patterns": [],
            "technology_stack": [],
            "recommendations": [],
            "error": "No architecture-related documents found",
        }

    # Combine text from all architecture docs (truncated)
    combined_text = ""
    project_name = docs[0]["client_name"] if docs else ""
    for doc in docs[:5]:
        combined_text += f"\n--- {doc['file_name']} ---\n"
        combined_text += (doc["parsed_text"] or "")[:3000]

    prompt = (
        "Analyze the following architecture-related document text and extract:\n"
        "1. components: list of system components mentioned\n"
        "2. integrations: list of {from, to, protocol} connections between systems\n"
        "3. patterns: architectural patterns detected "
        "(microservices, monolith, event-driven, etc.)\n"
        "4. technology_stack: technologies and frameworks mentioned\n"
        "5. recommendations: brief improvement suggestions\n\n"
        f"Document text:\n{combined_text[:8000]}\n\n"
        "Return JSON with the 5 fields above."
    )

    raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=2048)
    result = {
        "project": project_name,
        "components": [],
        "integrations": [],
        "patterns": [],
        "technology_stack": [],
        "recommendations": [],
    }

    if raw:
        parsed = extract_json(raw)
        if isinstance(parsed, dict):
            result["components"] = parsed.get("components", [])
            result["integrations"] = parsed.get("integrations", [])
            result["patterns"] = parsed.get("patterns", [])
            result["technology_stack"] = parsed.get("technology_stack", [])
            result["recommendations"] = parsed.get("recommendations", [])

    return result


def get_architecture_summary(user_id):
    """Aggregate architecture analysis across all projects."""
    with get_db() as conn:
        projects = conn.execute(
            "SELECT id, client_name FROM client_projects WHERE user_id = ? AND approved = 1",
            (user_id,),
        ).fetchall()

    all_techs = []
    all_patterns = []
    integration_map = {}
    analyzed = 0

    for proj in projects:
        result = analyze_architecture(user_id, project_id=proj["id"])
        if result.get("components") or result.get("technology_stack"):
            analyzed += 1
            all_techs.extend(result.get("technology_stack", []))
            all_patterns.extend(result.get("patterns", []))
            for integ in result.get("integrations", []):
                if isinstance(integ, dict):
                    key = f"{integ.get('from', '')} -> {integ.get('to', '')}"
                    integration_map[key] = integ.get("protocol", "unknown")

    # Count frequency for common items
    tech_counts = {}
    for t in all_techs:
        t_str = str(t).lower()
        tech_counts[t_str] = tech_counts.get(t_str, 0) + 1
    common_techs = sorted(tech_counts.keys(), key=lambda k: tech_counts[k], reverse=True)[:20]

    pattern_counts = {}
    for p in all_patterns:
        p_str = str(p).lower()
        pattern_counts[p_str] = pattern_counts.get(p_str, 0) + 1
    common_patterns = sorted(pattern_counts.keys(), key=lambda k: pattern_counts[k], reverse=True)[
        :10
    ]

    return {
        "projects_analyzed": analyzed,
        "common_technologies": common_techs,
        "common_patterns": common_patterns,
        "integration_map": integration_map,
    }
