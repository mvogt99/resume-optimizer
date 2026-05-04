"""Chat context assembler — gathers resume, ATS score, keyword, and LinkedIn data for chatbot system prompt."""

import json
import logging

import linkedin_cache
from models import get_db


def get_chat_context(user_id: int) -> dict:
    context = {
        "resume_text": None,
        "resume_filename": None,
        "ats_score": None,
        "matching_keywords": [],
        "missing_keywords": [],
        "job_description": None,
        "linkedin_headline": None,
        "linkedin_summary": None,
        "linkedin_skills": [],
    }

    try:
        with get_db() as conn:
            try:
                resume = conn.execute(
                    "SELECT * FROM resume_versions WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
                    (user_id,),
                ).fetchone()
                if resume:
                    context["resume_text"] = resume["parsed_text"]
                    context["resume_filename"] = resume["file_name"]
            except Exception as e:
                logging.error(f"Error fetching resume data: {e}")

            try:
                job_session = conn.execute(
                    "SELECT * FROM job_sessions WHERE user_id=? AND ats_score > 0 ORDER BY created_at DESC LIMIT 1",
                    (user_id,),
                ).fetchone()
                if job_session:
                    context["ats_score"] = job_session["ats_score"]
                    context["job_description"] = job_session["job_description_text"]
                    if job_session["optimization_result_json"]:
                        result = json.loads(job_session["optimization_result_json"])
                        context["matching_keywords"] = result.get("matching_keywords", [])
                        context["missing_keywords"] = result.get("missing_keywords", [])
            except Exception as e:
                logging.error(f"Error fetching job session data: {e}")

        try:
            linkedin_data = linkedin_cache.get_profile(user_id)
            if linkedin_data:
                context["linkedin_headline"] = linkedin_data.get("headline")
                context["linkedin_summary"] = linkedin_data.get("summary")
        except Exception as e:
            logging.error(f"Error fetching LinkedIn profile data: {e}")

        try:
            raw_linkedin_data = linkedin_cache.get_raw(user_id)
            if raw_linkedin_data and "skills_and_endorsements" in raw_linkedin_data:
                skills = sorted(
                    raw_linkedin_data["skills_and_endorsements"],
                    key=lambda x: x.get("endorsement_count", 0),
                    reverse=True,
                )
                context["linkedin_skills"] = [skill["name"] for skill in skills[:10]]
        except Exception as e:
            logging.error(f"Error fetching raw LinkedIn data: {e}")

    except Exception as e:
        logging.error(f"Unexpected error in get_chat_context: {e}")

    return context
