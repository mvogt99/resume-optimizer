"""
ArangoDB write methods, import_structured_analysis, and list_drive_folders
for ProjectAnalyzer.
"""

import contextlib
import json

from models import get_db

# ---------------------------------------------------------------------------
# ArangoDB write
# ---------------------------------------------------------------------------


def write_to_arango(client):
    """Write approved analysis to ArangoDB knowledge graph."""
    try:
        from arango_client import get_arango_client

        arango = get_arango_client()
        if not arango.is_connected:
            print("[project_analyzer] ArangoDB not connected, skipping graph write")
            return
    except Exception as e:
        print(f"[project_analyzer] ArangoDB unavailable: {e}")
        return

    client_name = client["client_name"]

    project_id = arango.upsert_vertex(
        "ro_client_projects",
        {
            "name": client_name,
            "folder_id": client["folder_id"],
            "document_count": client["document_count"],
        },
        key_source=f"project:{client_name}",
    )

    tech_items = _parse_json_field(client.get("technical_analysis_json", []))
    for tech in tech_items:
        name = tech.get("name", "")
        if not name:
            continue
        tech_id = arango.upsert_vertex(
            "ro_technologies",
            {"name": name, "category": tech.get("category", "")},
            key_source=f"tech:{name}",
        )
        arango.upsert_edge(
            "ro_client_used_tech",
            project_id,
            tech_id,
            {"context": tech.get("context", ""), "confidence": tech.get("confidence", 0.5)},
        )

    gov_items = _parse_json_field(client.get("governance_analysis_json", []))
    for gov in gov_items:
        name = gov.get("name", "")
        if not name:
            continue
        gov_id = arango.upsert_vertex(
            "ro_governance_controls",
            {
                "name": name,
                "category": gov.get("category", ""),
                "description": gov.get("description", ""),
            },
            key_source=f"gov:{name}",
        )
        arango.upsert_edge(
            "ro_client_required_governance",
            project_id,
            gov_id,
            {"confidence": gov.get("confidence", 0.5)},
        )

    role_items = _parse_json_field(client.get("role_analysis_json", []))
    for role in role_items:
        title = role.get("title", "")
        if not title:
            continue
        outcome_id = arango.upsert_vertex(
            "ro_outcomes",
            {
                "title": title,
                "type": role.get("type", ""),
                "description": role.get("description", ""),
                "metrics": role.get("metrics", ""),
            },
            key_source=f"outcome:{title}",
        )
        arango.upsert_edge(
            "ro_client_produced_outcome",
            project_id,
            outcome_id,
            {"confidence": role.get("confidence", 0.5)},
        )

    skill_items = _parse_json_field(client.get("skills_json", []))
    skill_vertex_ids = {}
    for skill in skill_items:
        name = skill.get("name", "")
        if not name:
            continue
        skill_id = arango.upsert_vertex(
            "ro_skills",
            {
                "name": name,
                "category": skill.get("category", ""),
                "proficiency_signal": skill.get("proficiency_signal", ""),
            },
            key_source=f"skill:{name}",
        )
        skill_vertex_ids[name.lower()] = skill_id
        arango.upsert_edge(
            "ro_client_demonstrated_skill",
            project_id,
            skill_id,
            {"evidence": skill.get("evidence", ""), "confidence": skill.get("confidence", 0.5)},
        )

    outcome_items = _parse_json_field(client.get("business_outcomes_json", []))

    tech_vertex_ids = {}
    for tech in tech_items:
        name = tech.get("name", "")
        if name:
            tech_vertex_ids[name.lower()] = arango.upsert_vertex(
                "ro_technologies",
                {"name": name, "category": tech.get("category", "")},
                key_source=f"tech:{name}",
            )

    correlation = client.get("correlation_json", {})
    if isinstance(correlation, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            correlation = json.loads(correlation)
    outcome_links = {}
    for link in (correlation if isinstance(correlation, dict) else {}).get(
        "outcome_skill_links", []
    ):
        if isinstance(link, dict):
            outcome_key = (link.get("outcome", "") or "").lower()
            outcome_links[outcome_key] = {
                "skills": link.get("skills", []),
                "technologies": link.get("technologies", []),
            }

    for outcome in outcome_items:
        title = outcome.get("outcome_title", "")
        if not title:
            continue
        outcome_id = arango.upsert_vertex(
            "ro_business_outcomes",
            {
                "title": title,
                "outcome_type": outcome.get("outcome_type", ""),
                "description": outcome.get("description", ""),
                "metric_value": outcome.get("metric_value", ""),
                "metric_unit": outcome.get("metric_unit", ""),
                "baseline": outcome.get("baseline", ""),
                "result": outcome.get("result", ""),
                "time_period": outcome.get("time_period", ""),
                "beneficiary": outcome.get("beneficiary", ""),
                "confidence": outcome.get("confidence", 0.5),
            },
            key_source=f"outcome:{title}",
        )

        arango.upsert_edge(
            "ro_client_achieved_outcome",
            project_id,
            outcome_id,
            {"confidence": outcome.get("confidence", 0.5)},
        )

        links = outcome_links.get(title.lower(), {})
        for skill_name in links.get("skills", []):
            sid = skill_vertex_ids.get(skill_name.lower())
            if sid:
                arango.upsert_edge("ro_outcome_driven_by_skill", outcome_id, sid)
        for tech_name in links.get("technologies", []):
            tid = tech_vertex_ids.get(tech_name.lower())
            if tid:
                arango.upsert_edge("ro_outcome_enabled_by_tech", outcome_id, tid)


def _parse_json_field(value):
    """Parse a JSON field that may be a string or list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            return json.loads(value)
    return []


# ---------------------------------------------------------------------------
# Import structured analysis (DLH platform export)
# ---------------------------------------------------------------------------


def import_structured_analysis(user_id, analysis_json, client_name=None):
    """Import a pre-structured analysis JSON (e.g. DLH platform export)."""
    if not client_name:
        mt = analysis_json.get("multi_tenancy", {})
        clients = mt.get("clients", [])
        client_name = clients[0].title() if clients else "Unknown"

    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM client_projects WHERE user_id = ? AND client_name = ?",
            (user_id, client_name),
        ).fetchone()
        if row:
            client_id = row["id"]
        else:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO client_projects (user_id, client_name, folder_id, folder_name) "
                "VALUES (?, ?, ?, ?)",
                (user_id, client_name, "", analysis_json.get("platform_name", "")),
            )
            conn.commit()
            client_id = cursor.lastrowid

    tech_items = _build_tech_items(analysis_json)
    gov_items = _build_gov_items(analysis_json)
    role_items = _build_role_items(analysis_json)
    outcome_items = _build_outcome_items(analysis_json)
    skill_items = _build_skill_items(analysis_json)

    with get_db() as conn:
        conn.execute(
            "UPDATE client_projects SET "
            "technical_analysis_json = ?, governance_analysis_json = ?, "
            "role_analysis_json = ?, business_outcomes_json = ?, "
            "skills_json = ?, analysis_status = 'completed', "
            "document_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (
                json.dumps(tech_items),
                json.dumps(gov_items),
                json.dumps(role_items),
                json.dumps(outcome_items),
                json.dumps(skill_items),
                len(
                    analysis_json.get("architectural_capabilities", {})
                    .get("data_pipeline_architecture", {})
                    .get("pipeline_stages", [])
                ),
                client_id,
            ),
        )
        conn.commit()

    return client_id


def _build_tech_items(analysis_json):
    arch = analysis_json.get("architectural_capabilities", {})
    tech_stack = analysis_json.get("technical_stack", {})
    tech_items = []

    iac = arch.get("infrastructure_as_code", {})
    if iac:
        tech_items.append(
            {
                "name": iac.get("framework", "AWS CDK"),
                "category": "IaC",
                "context": f"{iac.get('stack_count', 0)} stacks, "
                f"envs: {', '.join(iac.get('deployment_environments', []))}",
                "confidence": 0.95,
            }
        )

    pipeline = arch.get("data_pipeline_architecture", {})
    for stage in pipeline.get("pipeline_stages", []):
        tech_name = stage.get("technology", "")
        if tech_name and "Lambda" in tech_name:
            tech_items.append(
                {
                    "name": "AWS Lambda",
                    "category": "Compute",
                    "context": f"Stage: {stage.get('stage', '')}, {stage.get('purpose', '')}",
                    "confidence": 0.95,
                }
            )

    storage = arch.get("storage_architecture", {})
    if storage.get("iceberg_tables"):
        tech_items.append(
            {
                "name": "Apache Iceberg",
                "category": "Storage",
                "context": "Table format for data lake",
                "confidence": 0.95,
            }
        )
    if storage.get("athena_integration"):
        tech_items.append(
            {
                "name": "Amazon Athena",
                "category": "Analytics",
                "context": "Query engine with Iceberg + federated query support",
                "confidence": 0.95,
            }
        )

    eo = arch.get("event_orchestration", {})
    if eo:
        for svc in ["SNS FIFO", "SQS FIFO", "EventBridge"]:
            tech_items.append(
                {
                    "name": f"Amazon {svc}" if not svc.startswith("Event") else svc,
                    "category": "Integration",
                    "context": eo.get("pattern", ""),
                    "confidence": 0.90,
                }
            )

    export = arch.get("export_capabilities", {})
    if export.get("orchestration"):
        tech_items.append(
            {
                "name": "AWS Step Functions",
                "category": "Orchestration",
                "context": export.get("orchestration", ""),
                "confidence": 0.90,
            }
        )

    if arch.get("glue_etl_jobs"):
        tech_items.append(
            {
                "name": "AWS Glue",
                "category": "ETL",
                "context": "PySpark-based ETL jobs",
                "confidence": 0.95,
            }
        )

    for category, items in tech_stack.items():
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str) and item not in [t["name"] for t in tech_items]:
                    tech_items.append(
                        {
                            "name": item,
                            "category": category.replace("_", " ").title(),
                            "context": "",
                            "confidence": 0.85,
                        }
                    )

    seen_tech = set()
    unique_tech = []
    for t in tech_items:
        key = t["name"].lower()
        if key not in seen_tech:
            seen_tech.add(key)
            unique_tech.append(t)
    return unique_tech


def _build_gov_items(analysis_json):
    arch = analysis_json.get("architectural_capabilities", {})
    gov_items = []
    security = arch.get("cross_cutting_concerns", {}).get("security", {})
    for key, val in security.items():
        gov_items.append(
            {
                "name": key.replace("_", " ").title(),
                "category": "Security",
                "description": val if isinstance(val, str) else str(val),
                "confidence": 0.90,
            }
        )
    dq = arch.get("data_quality_framework", {})
    if dq:
        gov_items.append(
            {
                "name": f"Data Quality ({dq.get('integration', 'Custom')})",
                "category": "Data Quality",
                "description": ", ".join(dq.get("capabilities", [])),
                "confidence": 0.95,
            }
        )
    return gov_items


def _build_role_items(analysis_json):
    role_items = []
    achievements = analysis_json.get("solution_architect_achievements", {})
    for category, items in achievements.items():
        if isinstance(items, list):
            for item in items:
                role_items.append(
                    {
                        "title": item,
                        "type": category.replace("_", " ").title(),
                        "description": "",
                        "metrics": "",
                        "confidence": 0.85,
                    }
                )
    return role_items


def _build_outcome_items(analysis_json):
    outcome_items = []
    metrics = analysis_json.get("quantifiable_metrics", {})
    for _, data in metrics.items():
        if isinstance(data, dict):
            for key, val in data.items():
                outcome_items.append(
                    {
                        "outcome_type": "quantitative_metric",
                        "description": f"{key.replace('_', ' ').title()}: {val}",
                        "metric_value": str(val),
                        "confidence": 0.95,
                    }
                )
    recs = analysis_json.get("recommendations_for_endorsement", {})
    for section, items in recs.items():
        if isinstance(items, list):
            for item in items:
                outcome_items.append(
                    {
                        "outcome_type": section.replace("_", " "),
                        "description": item,
                        "confidence": 0.90,
                    }
                )
    return outcome_items


def _build_skill_items(analysis_json):
    skill_items = []
    for keyword in analysis_json.get("linkedin_endorsement_keywords", []):
        skill_items.append(
            {
                "name": keyword,
                "category": "DLH Platform",
                "proficiency_signal": "platform architect",
                "evidence": f"Demonstrated in {analysis_json.get('platform_name', '')}",
                "confidence": 0.90,
            }
        )
    return skill_items


# ---------------------------------------------------------------------------
# Google Drive folder browsing
# ---------------------------------------------------------------------------


def list_drive_folders(parent_id=None):
    """Browse Google Drive folders for project selection."""
    try:
        from gdrive_service import get_gdrive_service

        gdrive = get_gdrive_service()
        service = gdrive._get_drive_service()
    except Exception as e:
        return {"error": str(e), "folders": []}

    if parent_id:
        query = (
            f"'{parent_id}' in parents and "
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
    else:
        query = (
            "'root' in parents and "
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )

    try:
        results = (
            service.files()
            .list(q=query, fields="files(id, name, modifiedTime)", pageSize=100, orderBy="name")
            .execute()
        )
        return {"folders": results.get("files", [])}
    except Exception as e:
        return {"error": str(e), "folders": []}
