import json
import os
import re


def get_default_linkedin_path():
    """Returns path to the default LinkedIn JSON relative to project root."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(
        project_root,
        "working-docs",
        "linkedin",
        "linkedin_profile_merged_api_preferred.json",
    )


def extract_accomplishments(description_text):
    """Extract accomplishment bullet points from a job description."""
    if not description_text:
        return []

    lines = description_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    bullet_chars = {"•", "◦", "▪", "-", "*", "–", "—"}

    accomplishments = []
    in_accomplishments = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if re.match(r"(?i)key\s+accomplishments", stripped):
            in_accomplishments = True
            continue

        is_bullet = stripped[0] in bullet_chars
        if is_bullet:
            cleaned = stripped.lstrip("".join(bullet_chars) + " ").strip()
            if cleaned:
                accomplishments.append(cleaned)
        elif in_accomplishments and accomplishments:
            # Non-bullet line after accomplishments section — stop
            break

    return accomplishments


def parse_linkedin_json(json_path_or_dict):
    """Parse LinkedIn JSON into normalized resume dict.

    Args:
        json_path_or_dict: file path (str) or already-loaded dict.

    Returns:
        Normalized resume dictionary.
    """
    if isinstance(json_path_or_dict, str):
        with open(json_path_or_dict, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json_path_or_dict

    resume = {
        "name": data.get("full_name", ""),
        "headline": data.get("headline", ""),
        "summary": data.get("summary", ""),
        "contact": {"email": data.get("email", "")},
        "experience": [],
        "education": [],
        "skills": [],
        "recommendations": [],
    }

    # Current job + previous jobs
    current_job = data.get("current_job", {})
    previous_jobs = data.get("previous_jobs", [])

    all_jobs = []
    if current_job and current_job.get("title"):
        all_jobs.append({**current_job, "finished_on": "Present"})
    all_jobs.extend(previous_jobs)

    for job in all_jobs:
        desc = job.get("description", "")
        resume["experience"].append(
            {
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "start_date": job.get("started_on", ""),
                "end_date": job.get("finished_on", ""),
                "description": desc,
                "accomplishments": extract_accomplishments(desc),
            }
        )

    for edu in data.get("education_history", []):
        resume["education"].append(
            {
                "school": edu.get("school_name", ""),
                "degree": edu.get("degree_name", ""),
                "field": edu.get("field_of_study", ""),
                "start_date": edu.get("started_on", ""),
                "end_date": edu.get("finished_on", ""),
            }
        )

    for skill in data.get("skills_and_endorsements", []):
        resume["skills"].append(
            {
                "name": skill.get("skill", skill.get("name", "")),
                "endorsements": skill.get("endorsements_count", skill.get("endorsement_count", 0)),
            }
        )

    for rec in data.get("recommendations_received", []):
        first = rec.get("author_first_name", "")
        last = rec.get("author_last_name", "")
        resume["recommendations"].append(
            {
                "author": f"{first} {last}".strip(),
                "author_title": rec.get("author_job_title", ""),
                "text": rec.get("text", ""),
            }
        )

    return resume
