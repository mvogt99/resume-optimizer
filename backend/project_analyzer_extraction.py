"""
Skill/outcome extraction methods for ProjectAnalyzer.
Handles _extract_all_skills, _extract_business_outcomes,
_extract_skills_and_outcomes_combined, _classify_documents,
_load_classifications, and _build_context_for_doc.
"""

import contextlib
import json

from llm_helper import call_llm, extract_json, merge_extracted_items, smart_sample_chunks
from models import get_db


def classify_documents(client_id, job_id, manager, call_llm_fn=None):
    """Pass 1: LLM classifies each document by type, extracts key entities."""
    with get_db() as conn:
        docs = conn.execute(
            "SELECT id, parsed_text, file_name, classification_json FROM project_documents "
            "WHERE client_id = ? AND status IN ('parsed', 'analyzed')",
            (client_id,),
        ).fetchall()

    classifications = {}
    total = len(docs)

    for i, doc in enumerate(docs):
        if manager.is_cancelled(job_id):
            return classifications

        existing_cls = doc["classification_json"]
        if existing_cls and existing_cls != "{}":
            try:
                classifications[doc["id"]] = json.loads(existing_cls)
                manager.update_progress(
                    job_id,
                    {
                        "phase": "classifying",
                        "total": total,
                        "processed": i + 1,
                        "current_file": doc["file_name"],
                    },
                )
                continue
            except json.JSONDecodeError:
                pass

        text = doc["parsed_text"] or ""
        if len(text) < 50:
            continue

        manager.update_progress(
            job_id,
            {
                "phase": "classifying",
                "total": total,
                "processed": i + 1,
                "current_file": doc["file_name"],
            },
        )

        preview = text[:3000]
        prompt = (
            f"Classify this project document named '{doc['file_name']}'.\n\n"
            "Return a JSON object with:\n"
            '- "doc_type": one of "proposal", "sow", "architecture", '
            '"status_report", "meeting_notes", "requirements", '
            '"design", "test_plan", "presentation", "spreadsheet", "other"\n'
            '- "project_name": project name if identifiable\n'
            '- "time_period": date range if mentioned (e.g. "Q1 2024")\n'
            '- "key_entities": list of up to 10 important entities '
            "(technologies, people, systems, processes)\n"
            '- "summary": 1-2 sentence summary of what this document is about\n\n'
            f"Document preview:\n{preview}"
        )

        raw = call_llm(prompt, task_type="reasoning", max_tokens=1024)
        classification = extract_json(raw) if raw else None
        if not isinstance(classification, dict):
            classification = {
                "doc_type": "other",
                "project_name": "",
                "time_period": "",
                "key_entities": [],
                "summary": "",
            }

        classifications[doc["id"]] = classification

        with get_db() as conn:
            conn.execute(
                "UPDATE project_documents SET classification_json = ? WHERE id = ?",
                (json.dumps(classification), doc["id"]),
            )
            conn.commit()

    return classifications


def load_classifications(client_id):
    """Load existing classification_json from all analyzed docs for a client."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, classification_json FROM project_documents "
            "WHERE client_id = ? AND status = 'analyzed' AND classification_json IS NOT NULL",
            (client_id,),
        ).fetchall()
    classifications = {}
    for row in rows:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            classifications[row["id"]] = json.loads(row["classification_json"])
    return classifications


def build_context_for_doc(doc_id, classifications):
    """Build a ~500-char context summary from sibling documents' classifications."""
    parts = []
    for other_id, cls in classifications.items():
        if other_id == doc_id:
            continue
        doc_type = cls.get("doc_type", "")
        summary = cls.get("summary", "")
        entities = cls.get("key_entities", [])
        if summary:
            parts.append(f"[{doc_type}] {summary}")
        elif entities:
            parts.append(f"[{doc_type}] Entities: {', '.join(entities[:5])}")

    context = "; ".join(parts)
    if len(context) > 500:
        context = context[:497] + "..."
    return context


def extract_all_skills(client_id, job_id, manager, classifications):
    """Pass 3: Run dedicated skills extractor on every parsed document."""
    from skills_extractor import extract_all_skills as _extract_all_skills

    with get_db() as conn:
        docs = conn.execute(
            "SELECT id, parsed_text, file_name FROM project_documents "
            "WHERE client_id = ? AND status = 'analyzed'",
            (client_id,),
        ).fetchall()

    all_skills = []
    total = len(docs)
    for i, doc in enumerate(docs):
        if manager.is_cancelled(job_id):
            return

        text = doc["parsed_text"] or ""
        if len(text) < 50:
            continue

        if len(text) > 60000:
            sampled, _ = smart_sample_chunks(text)
            text = "\n\n--- CHUNK BOUNDARY ---\n\n".join(sampled)

        manager.update_progress(
            job_id,
            {
                "phase": "extracting_skills",
                "total": total,
                "processed": i + 1,
                "current_file": doc["file_name"],
            },
        )

        context = build_context_for_doc(doc["id"], classifications)
        skills = _extract_all_skills(text, context_summary=context)
        all_skills.extend(skills)

    merged = merge_extracted_items(all_skills, "name")
    with get_db() as conn:
        conn.execute(
            "UPDATE client_projects SET skills_json = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(merged), client_id),
        )
        conn.commit()


def extract_business_outcomes(client_id, job_id, manager, classifications):
    """Phase 3d: Extract structured business outcomes from every analyzed document."""
    from business_outcomes_extractor import extract_business_outcomes as _extract_outcomes

    with get_db() as conn:
        docs = conn.execute(
            "SELECT id, parsed_text, file_name, outcomes_json FROM project_documents "
            "WHERE client_id = ? AND status = 'analyzed'",
            (client_id,),
        ).fetchall()

    all_outcomes = []
    total = len(docs)
    for i, doc in enumerate(docs):
        if manager.is_cancelled(job_id):
            return

        existing = doc["outcomes_json"]
        if existing and existing != "[]":
            try:
                doc_outcomes = json.loads(existing)
                if isinstance(doc_outcomes, list) and doc_outcomes:
                    all_outcomes.extend(doc_outcomes)
                    manager.update_progress(
                        job_id,
                        {
                            "phase": "extracting_outcomes",
                            "total": total,
                            "processed": i + 1,
                            "current_file": doc["file_name"],
                        },
                    )
                    continue
            except json.JSONDecodeError:
                pass

        text = doc["parsed_text"] or ""
        if len(text) < 50:
            continue

        if len(text) > 60000:
            sampled, _ = smart_sample_chunks(text)
            text = "\n\n--- CHUNK BOUNDARY ---\n\n".join(sampled)

        manager.update_progress(
            job_id,
            {
                "phase": "extracting_outcomes",
                "total": total,
                "processed": i + 1,
                "current_file": doc["file_name"],
            },
        )

        context = build_context_for_doc(doc["id"], classifications)
        outcomes = _extract_outcomes(text, context_summary=context)

        with get_db() as conn:
            conn.execute(
                "UPDATE project_documents SET outcomes_json = ? WHERE id = ?",
                (json.dumps(outcomes), doc["id"]),
            )
            conn.commit()

        all_outcomes.extend(outcomes)

    seen = _dedup_outcomes(all_outcomes)
    merged = list(seen.values())

    with get_db() as conn:
        conn.execute(
            "UPDATE client_projects SET business_outcomes_json = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(merged), client_id),
        )
        conn.commit()


def extract_skills_and_outcomes_combined(client_id, job_id, manager, classifications):
    """Combined pass: extract skills AND outcomes in a single LLM call per chunk."""
    from skills_outcomes_extractor import extract_skills_and_outcomes

    with get_db() as conn:
        docs = conn.execute(
            "SELECT id, parsed_text, file_name FROM project_documents "
            "WHERE client_id = ? AND status = 'analyzed'",
            (client_id,),
        ).fetchall()

    all_skills = []
    all_outcomes = []
    total = len(docs)
    for i, doc in enumerate(docs):
        if manager.is_cancelled(job_id):
            return

        text = doc["parsed_text"] or ""
        if len(text) < 50:
            continue

        if len(text) > 60000:
            sampled, _ = smart_sample_chunks(text)
            text = "\n\n--- CHUNK BOUNDARY ---\n\n".join(sampled)

        manager.update_progress(
            job_id,
            {
                "phase": "extracting_skills_outcomes",
                "total": total,
                "processed": i + 1,
                "current_file": doc["file_name"],
            },
        )

        context = build_context_for_doc(doc["id"], classifications)
        skills, outcomes = extract_skills_and_outcomes(text, context_summary=context)
        all_skills.extend(skills)

        if outcomes:
            with get_db() as conn:
                conn.execute(
                    "UPDATE project_documents SET outcomes_json = ? WHERE id = ?",
                    (json.dumps(outcomes), doc["id"]),
                )
                conn.commit()
        all_outcomes.extend(outcomes)

    merged_skills = merge_extracted_items(all_skills, "name")
    with get_db() as conn:
        conn.execute(
            "UPDATE client_projects SET skills_json = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(merged_skills), client_id),
        )
        conn.commit()

    seen = _dedup_outcomes(all_outcomes)
    merged_outcomes = list(seen.values())
    with get_db() as conn:
        conn.execute(
            "UPDATE client_projects SET business_outcomes_json = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(merged_outcomes), client_id),
        )
        conn.commit()


def _dedup_outcomes(all_outcomes):
    """Deduplicate outcomes with confidence boosting for multi-document mentions."""
    seen = {}
    for outcome in all_outcomes:
        if not isinstance(outcome, dict):
            continue
        key = (outcome.get("outcome_title") or "").lower().strip()
        if not key:
            continue
        if key in seen:
            existing_conf = seen[key].get("confidence", 0.5)
            seen[key]["confidence"] = min(existing_conf + 0.10, 1.0)
            if len(json.dumps(outcome)) > len(json.dumps(seen[key])):
                boosted = seen[key]["confidence"]
                seen[key] = outcome
                seen[key]["confidence"] = boosted
        else:
            seen[key] = outcome
    return seen
