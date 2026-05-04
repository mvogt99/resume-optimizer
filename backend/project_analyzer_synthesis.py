"""
Document analysis (sequential/bus), cross-document correlation, and synthesis
for ProjectAnalyzer.
"""

import json
import os

from llm_helper import call_llm, extract_json, merge_extracted_items, smart_sample_chunks
from models import get_db

# ---------------------------------------------------------------------------
# Document analysis (sequential + bus)
# ---------------------------------------------------------------------------


def analyze_documents(client_id, job_id, manager, classifications=None):
    """Run LLM extraction on each parsed document with optional cross-doc context."""
    from governance_extractor import extract_governance_picture
    from project_analyzer_extraction import build_context_for_doc
    from role_extractor import extract_role_picture
    from technical_extractor import extract_technical_picture

    with get_db() as conn:
        docs = conn.execute(
            "SELECT id, parsed_text, file_name FROM project_documents "
            "WHERE client_id = ? AND status = 'parsed'",
            (client_id,),
        ).fetchall()

    bus = _get_bus()
    if bus and bus.is_available():
        analyze_documents_bus(docs, client_id, job_id, manager, classifications, bus)
        return

    total = len(docs)
    for i, doc in enumerate(docs):
        if manager.is_cancelled(job_id):
            return

        text = doc["parsed_text"]
        if not text or len(text) < 50:
            with get_db() as conn2:
                conn2.execute(
                    "UPDATE project_documents SET analysis_json = ?, "
                    "status = 'analyzed' WHERE id = ?",
                    (
                        json.dumps(
                            {
                                "technical": [],
                                "governance": [],
                                "role": [],
                                "skipped": "text_too_short",
                            }
                        ),
                        doc["id"],
                    ),
                )
                conn2.commit()
            continue

        sampling_meta = None
        if len(text) > 60000:
            sampled, total_chunks = smart_sample_chunks(text)
            text = "\n\n--- CHUNK BOUNDARY ---\n\n".join(sampled)
            sampling_meta = {
                "sampled": True,
                "chunks_used": len(sampled),
                "chunks_total": total_chunks,
            }
            print(
                f"[project_analyzer] Smart-sampled {doc['file_name']}: "
                f"{len(sampled)}/{total_chunks} chunks ({len(text):,} chars from original)"
            )

        manager.update_progress(
            job_id,
            {
                "phase": "analyzing",
                "total": total,
                "processed": i + 1,
                "current_file": doc["file_name"],
            },
        )

        context = ""
        if classifications:
            context = build_context_for_doc(doc["id"], classifications)

        analysis = {
            "technical": extract_technical_picture(text, context_summary=context),
            "governance": extract_governance_picture(text, context_summary=context),
            "role": extract_role_picture(text, context_summary=context),
        }
        if sampling_meta:
            analysis["sampling"] = sampling_meta

        with get_db() as conn:
            conn.execute(
                "UPDATE project_documents SET analysis_json = ?, status = 'analyzed' WHERE id = ?",
                (json.dumps(analysis), doc["id"]),
            )
            conn.commit()


def analyze_documents_bus(docs, client_id, job_id, manager, classifications, bus):
    """Parallel document analysis via Artemis message bus."""
    from analysis_worker import handle_chunk
    from project_analyzer_extraction import build_context_for_doc

    bus.drain_results()

    pending = []
    total = len(docs)
    for i, doc in enumerate(docs):
        if manager.is_cancelled(job_id):
            return

        text = doc["parsed_text"]
        if not text or len(text) < 50:
            with get_db() as conn2:
                conn2.execute(
                    "UPDATE project_documents SET analysis_json = ?, "
                    "status = 'analyzed' WHERE id = ?",
                    (
                        json.dumps(
                            {
                                "technical": [],
                                "governance": [],
                                "role": [],
                                "skipped": "text_too_short",
                            }
                        ),
                        doc["id"],
                    ),
                )
                conn2.commit()
            continue

        sampling_meta = None
        if len(text) > 60000:
            sampled, total_chunks = smart_sample_chunks(text)
            text = "\n\n--- CHUNK BOUNDARY ---\n\n".join(sampled)
            sampling_meta = {
                "sampled": True,
                "chunks_used": len(sampled),
                "chunks_total": total_chunks,
            }

        context = ""
        if classifications:
            context = build_context_for_doc(doc["id"], classifications)

        manager.update_progress(
            job_id,
            {
                "phase": "publishing_chunks",
                "total": total,
                "processed": i + 1,
                "current_file": doc["file_name"],
            },
        )

        published = bus.publish_chunk(
            doc_id=doc["id"],
            chunk_idx=0,
            chunk_text=text,
            context=context,
            extractors=["tech", "gov", "role"],
        )
        if published:
            pending.append((doc["id"], sampling_meta))
        else:
            analysis = handle_chunk(
                {
                    "doc_id": doc["id"],
                    "chunk_idx": 0,
                    "chunk_text": text,
                    "context": context,
                    "extractors": ["tech", "gov", "role"],
                }
            )
            if sampling_meta:
                analysis["sampling"] = sampling_meta
            with get_db() as conn2:
                conn2.execute(
                    "UPDATE project_documents SET analysis_json = ?, "
                    "status = 'analyzed' WHERE id = ?",
                    (json.dumps(analysis), doc["id"]),
                )
                conn2.commit()

    if not pending:
        return

    manager.update_progress(
        job_id,
        {"phase": "collecting_results", "total": len(pending), "processed": 0},
    )
    results = bus.collect_results(expected_count=len(pending), timeout=600)
    results_by_doc = {r["doc_id"]: r for r in results if isinstance(r, dict)}

    for doc_id, sampling_meta in pending:
        r = results_by_doc.get(doc_id)
        if r:
            analysis = {
                "technical": r.get("technical", []),
                "governance": r.get("governance", []),
                "role": r.get("role", []),
            }
        else:
            analysis = {"technical": [], "governance": [], "role": [], "skipped": "bus_timeout"}
        if sampling_meta:
            analysis["sampling"] = sampling_meta

        with get_db() as conn2:
            conn2.execute(
                "UPDATE project_documents SET analysis_json = ?, status = 'analyzed' WHERE id = ?",
                (json.dumps(analysis), doc_id),
            )
            conn2.commit()


def _get_bus():
    """Get analysis bus instance, or None if unavailable."""
    if not os.environ.get("RESUME_BUS_ENABLED"):
        return None
    try:
        from bus_client import get_analysis_bus

        return get_analysis_bus()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Cross-document correlation and synthesis
# ---------------------------------------------------------------------------


def correlate_cross_document(client_id, get_client_fn):
    """Pass 4: LLM identifies technology clusters and reinforced accomplishments."""
    import contextlib

    client = get_client_fn(client_id)
    if not client:
        return

    tech_json = client.get("technical_analysis_json", "{}")
    role_json = client.get("role_analysis_json", "{}")
    skills_json = client.get("skills_json", "[]")
    outcomes_json = client.get("business_outcomes_json", "[]")

    if isinstance(tech_json, str):
        with contextlib.suppress(json.JSONDecodeError):
            tech_json = json.loads(tech_json)
    if isinstance(role_json, str):
        with contextlib.suppress(json.JSONDecodeError):
            role_json = json.loads(role_json)
    if isinstance(skills_json, str):
        with contextlib.suppress(json.JSONDecodeError):
            skills_json = json.loads(skills_json)
    if isinstance(outcomes_json, str):
        with contextlib.suppress(json.JSONDecodeError):
            outcomes_json = json.loads(outcomes_json)

    tech_names = [t.get("name", "") for t in (tech_json if isinstance(tech_json, list) else [])]
    role_titles = [r.get("title", "") for r in (role_json if isinstance(role_json, list) else [])]
    skill_names = [
        s.get("name", "") for s in (skills_json if isinstance(skills_json, list) else [])
    ]
    outcome_titles = [
        o.get("outcome_title", "")
        for o in (outcomes_json if isinstance(outcomes_json, list) else [])
    ]

    prompt = (
        "Analyze these extracted elements from a client project's documents "
        "and identify cross-document patterns.\n\n"
        f"Technologies found: {', '.join(tech_names[:40])}\n"
        f"Role/impact items: {', '.join(role_titles[:20])}\n"
        f"Skills extracted: {', '.join(skill_names[:50])}\n"
        f"Business outcomes: {', '.join(outcome_titles[:20])}\n\n"
        "Return a JSON object with:\n"
        '- "technology_clusters": list of {"cluster_name": str, '
        '"technologies": [str], "description": str}\n'
        '- "reinforced_accomplishments": list of {"accomplishment": str, '
        '"supporting_evidence_count": int, "confidence": float}\n'
        '- "skill_proficiency_levels": list of {"skill": str, '
        '"level": "beginner|intermediate|advanced|expert", "evidence_count": int}\n'
        '- "key_themes": list of str — 3-5 overarching themes\n'
        '- "outcome_skill_links": list of '
        '{"outcome": str, "skills": [str], "technologies": [str]}\n'
    )

    raw = call_llm(prompt, task_type="reasoning", max_tokens=4096)
    correlation = extract_json(raw) if raw else None
    if not isinstance(correlation, dict):
        correlation = {
            "technology_clusters": [],
            "reinforced_accomplishments": [],
            "skill_proficiency_levels": [],
            "key_themes": [],
            "outcome_skill_links": [],
        }

    with get_db() as conn:
        conn.execute(
            "UPDATE client_projects SET correlation_json = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(correlation), client_id),
        )
        conn.commit()


def synthesize_client(client_id):
    """Aggregate all document analyses into client-level summaries."""
    with get_db() as conn:
        docs = conn.execute(
            "SELECT analysis_json, outcomes_json FROM project_documents "
            "WHERE client_id = ? AND status = 'analyzed'",
            (client_id,),
        ).fetchall()

    all_tech, all_gov, all_role, all_outcomes = [], [], [], []

    for doc in docs:
        try:
            analysis = json.loads(doc["analysis_json"])
        except (json.JSONDecodeError, TypeError):
            analysis = {}
        all_tech.extend(analysis.get("technical", []))
        all_gov.extend(analysis.get("governance", []))
        all_role.extend(analysis.get("role", []))

        try:
            doc_outcomes = json.loads(doc["outcomes_json"] or "[]")
            if isinstance(doc_outcomes, list):
                all_outcomes.extend(doc_outcomes)
        except (json.JSONDecodeError, TypeError):
            pass

    tech_merged = merge_extracted_items(all_tech, "name")
    gov_merged = merge_extracted_items(all_gov, "name")
    role_merged = merge_extracted_items(all_role, "title")
    outcomes_merged = merge_extracted_items(all_outcomes, "outcome_title")

    with get_db() as conn:
        conn.execute(
            "UPDATE client_projects SET technical_analysis_json = ?, "
            "governance_analysis_json = ?, role_analysis_json = ?, "
            "business_outcomes_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (
                json.dumps(tech_merged),
                json.dumps(gov_merged),
                json.dumps(role_merged),
                json.dumps(outcomes_merged),
                client_id,
            ),
        )
        conn.commit()
