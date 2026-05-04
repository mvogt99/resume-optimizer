"""
Data source gathering and WIP project scanning for DeepProfileEngine.
"""

import contextlib
import glob
import json
import os


def get_linkedin_data(current_user_id):
    """Get LinkedIn profile data from the cached globals in app.py."""
    try:
        import linkedin_cache

        raw = linkedin_cache.get_raw(current_user_id)
        if raw:
            return {
                "skills": raw.get("skills", []),
                "experience": raw.get("experience", []),
                "recommendations": raw.get("recommendations", []),
                "summary": raw.get("summary", ""),
                "headline": raw.get("headline", ""),
                "education": raw.get("education_history", []),
            }
    except (ImportError, AttributeError):
        pass
    return {}


def get_project_data(user_id):
    """Get all completed project analyses."""
    from models import get_db

    with get_db() as conn:
        rows = conn.execute(
            "SELECT client_name, skills_json, correlation_json, "
            "business_outcomes_json, technical_analysis_json, role_analysis_json "
            "FROM client_projects WHERE analysis_status IN ('completed', 'complete') "
            "AND (skills_json IS NOT NULL AND skills_json != '[]')"
        ).fetchall()

    projects = []
    for row in rows:
        proj = {"client_name": row["client_name"]}
        for field in [
            "skills_json",
            "correlation_json",
            "business_outcomes_json",
            "technical_analysis_json",
            "role_analysis_json",
        ]:
            try:
                proj[field.replace("_json", "")] = json.loads(row[field] or "{}")
            except (json.JSONDecodeError, TypeError):
                proj[field.replace("_json", "")] = {}
        projects.append(proj)
    return projects


def get_journey_data():
    """Get journey timeline events, skills, and narratives."""
    from models import get_db

    with get_db() as conn:
        events = conn.execute(
            "SELECT event_date, title, category, technologies, metrics "
            "FROM journey_events ORDER BY event_date DESC LIMIT 500"
        ).fetchall()
        narratives = conn.execute(
            "SELECT narrative_type, title, content FROM journey_narratives "
            "WHERE (approved = 1 OR narrative_type IN ('resume_entry', 'learning_arc')) "
            "AND superseded_at IS NULL"
        ).fetchall()

    parsed_events = []
    for e in events:
        evt = dict(e)
        for jfield in ("technologies", "metrics"):
            try:
                evt[jfield] = json.loads(evt.get(jfield) or "[]")
            except (json.JSONDecodeError, TypeError):
                evt[jfield] = []
        parsed_events.append(evt)

    return {
        "events": parsed_events,
        "narratives": [dict(n) for n in narratives],
    }


def get_experience_data(user_id):
    """Get finalized experience extractions."""
    from models import get_db

    with get_db() as conn:
        rows = conn.execute(
            "SELECT employer, client, title, duration, responsibilities, "
            "technologies, accomplishments, bullet_points "
            "FROM extracted_experiences WHERE user_id = ?",
            (user_id,),
        ).fetchall()

    experiences = []
    for row in rows:
        exp = dict(row)
        for jfield in ("responsibilities", "technologies", "accomplishments", "bullet_points"):
            try:
                exp[jfield] = json.loads(exp.get(jfield) or "[]")
            except (json.JSONDecodeError, TypeError):
                exp[jfield] = []
        experiences.append(exp)
    return experiences


def get_resume_data(user_id):
    """Get latest resume versions."""
    from models import get_db

    with get_db() as conn:
        rows = conn.execute(
            "SELECT source, file_name, parsed_text FROM resume_versions "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT 3",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_skills_interview_data():
    """Get finalized skills interview results."""
    from models import get_db

    with get_db() as conn:
        rows = conn.execute(
            "SELECT context_json FROM skills_interview_sessions WHERE is_finalized = 1"
        ).fetchall()

    results = []
    for row in rows:
        try:
            ctx = json.loads(row["context_json"] or "{}")
            results.append(ctx)
        except (json.JSONDecodeError, TypeError):
            pass
    return results


def get_wip_projects(applications_root):
    """Scan local WIP project directories for technology/architecture signals."""
    apps_root = os.path.normpath(applications_root)
    skip_dirs = {"deployed_app", "test", "cooling-automation"}
    projects = []
    for entry in sorted(os.listdir(apps_root)):
        if entry in skip_dirs or entry.startswith("."):
            continue
        proj_dir = os.path.join(apps_root, entry)
        if not os.path.isdir(proj_dir):
            continue
        proj = scan_project_dir(proj_dir, entry)
        if proj and proj["file_count"] >= 3:
            projects.append(proj)
    return projects


def scan_project_dir(proj_dir, name):
    """Extract structured data from a single project directory."""
    py_files = glob.glob(os.path.join(proj_dir, "**", "*.py"), recursive=True)
    if not py_files:
        return None

    proj = {
        "name": name,
        "path": proj_dir,
        "description": "",
        "technologies": [],
        "architecture_patterns": [],
        "skills_demonstrated": [],
        "status": "wip",
        "file_count": len(py_files),
    }

    for doc_name in ("CLAUDE.md", "README.md", "readme.md"):
        doc_path = os.path.join(proj_dir, doc_name)
        if os.path.isfile(doc_path):
            try:
                with open(doc_path, "r", errors="replace") as f:
                    text = f.read(4000)
                for line in text.split("\n"):
                    line = line.strip()
                    if (
                        line
                        and not line.startswith("#")
                        and not line.startswith(">")
                        and not line.startswith("```")
                        and len(line) > 30
                    ):
                        proj["description"] = line[:200]
                        break
            except OSError:
                pass
            break

    for req_name in ("requirements.txt", "backend/requirements.txt"):
        req_path = os.path.join(proj_dir, req_name)
        if os.path.isfile(req_path):
            with contextlib.suppress(OSError), open(req_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pkg = (
                            line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()
                        )
                        if pkg:
                            proj["technologies"].append(pkg)
            break

    pkg_paths = glob.glob(os.path.join(proj_dir, "**/package.json"), recursive=True)
    for pkg_path in pkg_paths[:2]:
        try:
            with open(pkg_path, "r") as f:
                pkg = json.load(f)
            for dep_key in ("dependencies", "devDependencies"):
                for dep_name in pkg.get(dep_key) or {}:
                    proj["technologies"].append(dep_name)
        except (OSError, json.JSONDecodeError):
            pass

    pattern_signals = {
        "fastapi": "FastAPI microservice",
        "flask": "Flask REST API",
        "react": "React SPA",
        "arango": "ArangoDB graph database",
        "qdrant": "Qdrant vector database",
        "spacy": "NLP pipeline (spaCy)",
        "nltk": "NLP processing (NLTK)",
        "sklearn": "Machine learning (scikit-learn)",
        "scikit-learn": "Machine learning (scikit-learn)",
        "docker": "Docker containerization",
        "asyncio": "Async/concurrent processing",
        "threading": "Multi-threaded architecture",
        "sqlite3": "SQLite database",
        "sqlalchemy": "SQLAlchemy ORM",
        "oauth": "OAuth authentication",
        "stomp": "Message bus (STOMP/Artemis)",
        "celery": "Task queue (Celery)",
        "redis": "Redis caching",
        "pytest": "Test-driven development",
    }
    found_patterns = set()
    for py_file in py_files[:50]:
        try:
            with open(py_file, "r", errors="replace") as f:
                content = f.read(3000)
            content_lower = content.lower()
            for signal, pattern in pattern_signals.items():
                if signal in content_lower and pattern not in found_patterns:
                    found_patterns.add(pattern)
        except OSError:
            pass
    proj["architecture_patterns"] = sorted(found_patterns)

    skill_map = {
        "FastAPI microservice": "API design",
        "Flask REST API": "REST API development",
        "React SPA": "Frontend development",
        "ArangoDB graph database": "Graph database design",
        "Qdrant vector database": "Vector search / RAG",
        "NLP pipeline (spaCy)": "Natural language processing",
        "Machine learning (scikit-learn)": "Machine learning",
        "Docker containerization": "DevOps / containerization",
        "OAuth authentication": "Security / authentication",
        "Message bus (STOMP/Artemis)": "Message-driven architecture",
        "Async/concurrent processing": "Concurrent programming",
        "Test-driven development": "Test-driven development",
        "SQLite database": "Database design",
    }
    for pattern in proj["architecture_patterns"]:
        skill = skill_map.get(pattern)
        if skill:
            proj["skills_demonstrated"].append(skill)

    proj["technologies"] = sorted(set(proj["technologies"]))
    return proj
