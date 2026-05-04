"""Shared test fixtures for resume-optimizer backend tests."""

import contextlib
import os
import sys
import tempfile

import pytest

# Ensure backend/ is on sys.path so imports work
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Also ensure tests/ is on sys.path so test_helpers can be imported
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)


def _patch_db_path(tmp_path):
    """Patch DB_PATH in models and ALL modules that imported it at module level."""
    import models

    models.DB_PATH = tmp_path
    # Patch every loaded module that has a module-level DB_PATH from models
    for mod in list(sys.modules.values()):
        if mod is None or mod is models:
            continue
        if hasattr(mod, "DB_PATH") and isinstance(mod.DB_PATH, str):
            with contextlib.suppress(AttributeError, TypeError):
                mod.DB_PATH = tmp_path


def _truncate_all_pg_tables() -> None:
    """Truncate all public tables and restart sequences for a clean test state."""
    import psycopg2

    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    tables = [r[0] for r in cur.fetchall()]
    if tables:
        cur.execute("TRUNCATE {} RESTART IDENTITY CASCADE".format(", ".join(tables)))
    conn.commit()
    cur.close()
    conn.close()


@pytest.fixture()
def app():
    """Create a Flask app with a fresh database for each test.

    SQLite path: creates a temp file, patches DB_PATH, deletes at teardown.
    PostgreSQL path: truncates all tables + restarts sequences at the start of
    each test so every test begins with a clean database.
    """
    from db_engine import is_postgres

    using_pg = is_postgres()

    if using_pg:
        db_fd = None
        db_path = ":memory:"  # unused sentinel
        _truncate_all_pg_tables()
    else:
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        _patch_db_path(db_path)

    # Set JOURNEY_WORKDIR to a temp dir for tests (avoid scanning huge real workdir)
    test_workdir = tempfile.mkdtemp()
    os.environ["JOURNEY_WORKDIR"] = test_workdir

    from models import init_db

    init_db()

    # Initialize lazy tables that aren't created by init_db()
    from resume_corrections import init_corrections_table
    init_corrections_table()

    from builder_interview import init_builder_interview_tables
    from deep_profile import _init_deep_profile_tables
    from experience_chat import init_experience_tables
    from resume_builder import init_builder_tables
    from skills_interview import init_skills_interview_tables

    init_experience_tables()
    init_builder_interview_tables()
    init_skills_interview_tables()
    init_builder_tables()
    _init_deep_profile_tables()

    # Reset ALL singletons so they re-create tables against the new DB path.
    # Without this, singletons from previous tests hold stale DB connections.
    import ats_improvement_chat
    import builder_interview as _bi
    import campaign_interview as _ci
    import deep_interview
    import deep_profile as _dp
    import experience_chat as _ec
    import resume_builder as _rb
    import skills_interview as _si

    ats_improvement_chat._instance = None
    _bi._interviewer = None
    _ci._interviewer = None
    deep_interview._interviewer = None
    _dp._engine = None
    _ec._extractor = None
    _rb._builder = None
    _si._interviewer = None

    import resume_interview as _rint

    _rint._interviewer = None

    ats_improvement_chat.get_ats_improvement_chat()  # triggers _init_tables()
    deep_interview._init_interview_tables()

    # Reset batch_jobs singleton so daemon threads use the test DB
    import batch_jobs as _bj

    _bj.BatchJobManager._instance = None

    # Reset journey_miner and project_analyzer singletons
    import journey_miner as _jm
    import project_analyzer as _pa

    _jm._miner = None
    _pa._analyzer = None

    # Reset agent singletons so each test gets fresh instances
    import agents as _agents

    _agents._job_scout = None
    _agents._app_tracker = None
    _agents._resume_tailor = None
    _agents._cover_letter = None
    _agents._interview_coach = None
    _agents._career_advisor = None
    _agents._orchestrator = None

    # batch_jobs table is created at import time of batch_jobs module,
    # but may have used old DB_PATH. Re-create in test DB.
    from models import get_db_connection

    conn = get_db_connection() if using_pg else get_db_connection(db_path=db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS batch_jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            user_id INTEGER NOT NULL,
            params_json TEXT DEFAULT '{}',
            progress_json TEXT DEFAULT '{}',
            result_json TEXT DEFAULT '{}',
            error_message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )"""
    )
    conn.commit()
    conn.close()

    from app import create_app

    application = create_app(testing=True)
    application.config["TESTING"] = True

    yield application

    # Shutdown batch job threads BEFORE deleting the temp DB
    if _bj.BatchJobManager._instance is not None:
        _bj.BatchJobManager._instance.shutdown(timeout=5)

    if not using_pg:
        os.close(db_fd)
        os.unlink(db_path)


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    """Register a test user and return auth headers with JWT token."""
    client.post(
        "/api/register",
        json={"email": "test@test.com", "password": "Test1234!"},
    )
    resp = client.post(
        "/api/login",
        json={"email": "test@test.com", "password": "Test1234!"},
    )
    data = resp.get_json()
    return {
        "Authorization": f"Bearer {data['token']}",
        "Content-Type": "application/json",
    }


@pytest.fixture()
def second_user_headers(client):
    """Register a second test user for isolation tests."""
    client.post(
        "/api/register",
        json={"email": "user2@test.com", "password": "Test1234!"},
    )
    resp = client.post(
        "/api/login",
        json={"email": "user2@test.com", "password": "Test1234!"},
    )
    data = resp.get_json()
    return {
        "Authorization": f"Bearer {data['token']}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Composite fixtures using test_helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _block_personaforge(request, monkeypatch):
    """Block all PersonaForge HTTP calls in tests — never hit localhost:8090.

    Tests that need the real PF functions (e.g. personaforge_client unit tests)
    can mark themselves with @pytest.mark.real_pf to skip this fixture.
    """
    if "real_pf" in request.keywords:
        return
    monkeypatch.setattr("personaforge_client.pf_recall", lambda *a, **kw: None)
    monkeypatch.setattr("personaforge_client.pf_remember", lambda *a, **kw: None)
    monkeypatch.setattr("personaforge_client.pf_feedback", lambda *a, **kw: None)
    # Also patch on the base_agent module where it was imported
    try:
        import agents.base_agent as _ba

        monkeypatch.setattr(_ba, "pf_recall", lambda *a, **kw: None)
        monkeypatch.setattr(_ba, "pf_remember", lambda *a, **kw: None)
    except (ImportError, AttributeError):
        pass


@pytest.fixture(autouse=True, scope="session")
def report_skipped_infrastructure(request):
    """Report infrastructure tests that were skipped due to services being down."""
    yield
    terminal = request.config.pluginmanager.get_plugin("terminalreporter")
    if terminal is None:
        return
    skipped_items = terminal.stats.get("skipped", [])
    infra_keywords = ("harness", "arango", "qdrant", "artemis", "gdrive", "LLM")
    infra_skips = [
        s
        for s in skipped_items
        if any(kw.lower() in str(s.longrepr).lower() for kw in infra_keywords)
    ]
    if infra_skips:
        terminal.write_line("")
        terminal.write_line(
            f"\u26a0\ufe0f  WARNING: {len(infra_skips)} infrastructure tests SKIPPED "
            f"(services down)",
            yellow=True,
        )
        for s in infra_skips[:10]:
            terminal.write_line(f"   - {s.nodeid}", yellow=True)
        if len(infra_skips) > 10:
            terminal.write_line(f"   ... and {len(infra_skips) - 10} more", yellow=True)


from test_helpers import JD_TEXT  # noqa: E402
from test_helpers import query_db  # noqa: E402, F401
from test_helpers import optimize as _optimize  # noqa: E402
from test_helpers import require_harness as _require_harness  # noqa: E402
from test_helpers import upload_jd, upload_resume  # noqa: E402


@pytest.fixture()
def require_harness():
    """Skip (or fail if REQUIRE_LLM_TESTS=true) when FTAL harness is unavailable."""
    _require_harness()


@pytest.fixture()
def resume_and_jd(client, auth_headers):
    """Upload matched resume + JD, return (resume_id, jd_id)."""
    rid = upload_resume(client, auth_headers)
    jid = upload_jd(client, auth_headers)
    return rid, jid


@pytest.fixture()
def linkedin_imported(client, auth_headers):
    """Import LinkedIn profile, return profile dict."""
    resp = client.post("/api/import/linkedin", headers=auth_headers, json={})
    assert resp.status_code == 200, f"LinkedIn import failed: {resp.get_json()}"
    resp2 = client.get("/api/profile/linkedin", headers=auth_headers)
    return resp2.get_json()


@pytest.fixture()
def optimized_resume(client, auth_headers, resume_and_jd):
    """Upload resume + JD, optimize, return (resume_id, optimization_result)."""
    rid, _ = resume_and_jd
    result = _optimize(client, auth_headers, rid)
    return rid, result


@pytest.fixture()
def posting_id(client, auth_headers):
    """Create a manual job posting, return posting_id."""
    resp = client.post(
        "/api/agents/scout/postings",
        headers={"user-id": "1", "Content-Type": "application/json"},
        json={
            "title": "Senior Solutions Architect",
            "company": "Acme Corp",
            "description": JD_TEXT,
            "link": "https://example.com/job/123",
            "location": "Remote",
        },
    )
    assert resp.status_code == 201, f"Create posting failed: {resp.get_json()}"
    data = resp.get_json()
    return data.get("id") or data.get("posting_id")


# ---------------------------------------------------------------------------
# Phase B hybrid_scorer fixtures
# ---------------------------------------------------------------------------

from datetime import date, timedelta


@pytest.fixture
def sample_requirement():
    """Standard requirement for must_have skill."""
    return {
        "requirement_id": "req_kafka_001",
        "requirement_type": "must_have",
        "text": "5+ years Apache Kafka experience in streaming architectures",
        "canonical_skills": ["Apache Kafka"],
        "importance": 1.0,
    }


@pytest.fixture
def sample_requirement_domain():
    """Domain-type requirement for healthcare context."""
    return {
        "requirement_id": "req_hipaa_001",
        "requirement_type": "domain",
        "text": "HIPAA compliance expertise with healthcare claims systems",
        "canonical_skills": ["HIPAA", "Claims"],
        "importance": 0.8,
    }


@pytest.fixture
def sample_requirement_leadership():
    """Leadership-type requirement."""
    return {
        "requirement_id": "req_lead_001",
        "requirement_type": "leadership",
        "text": "Led teams of 8+ engineers; established development standards",
        "canonical_skills": ["Team Leadership"],
        "importance": 0.7,
    }


@pytest.fixture
def sample_candidate_senior():
    """Candidate with high seniority signals and extensive Kafka experience."""
    return {
        "candidate_id": "cand_001",
        "target_role_families": ["data_architect", "consultant"],
        "skill_inventory": [
            {
                "canonical_skill": "Apache Kafka",
                "aliases": ["Kafka", "MSK"],
                "evidence_refs": ["proj_001", "proj_002", "proj_003"],
                "proficiency_estimate": "expert",
            },
            {
                "canonical_skill": "Python",
                "aliases": ["Python 3", "Py"],
                "evidence_refs": ["proj_001"],
                "proficiency_estimate": "expert",
            },
        ],
        "experience_units": [
            {
                "experience_id": "exp_001",
                "title": "Data Platform Architect",
                "company": "Navitus",
                "skills": ["Apache Kafka", "Python"],
                "leadership_signals": ["led teams", "strategy"],
                "date_range": {"start": "2022-01-01", "end": None},
            },
            {
                "experience_id": "exp_002",
                "title": "Principal Engineer",
                "company": "OPI",
                "skills": ["Kafka", "Spark"],
                "leadership_signals": ["mentored"],
                "date_range": {"start": "2019-01-01", "end": "2022-01-01"},
            },
        ],
    }


@pytest.fixture
def sample_candidate_junior():
    """Candidate with minimal experience and junior role signals."""
    return {
        "candidate_id": "cand_002",
        "target_role_families": ["engineer", "analyst"],
        "skill_inventory": [
            {
                "canonical_skill": "SQL",
                "aliases": ["T-SQL"],
                "evidence_refs": ["proj_001"],
                "proficiency_estimate": "intermediate",
            }
        ],
        "experience_units": [
            {
                "experience_id": "exp_003",
                "title": "Software Engineer",
                "company": "StartupXYZ",
                "skills": ["SQL"],
                "leadership_signals": [],
                "date_range": {"start": "2024-01-01", "end": None},
            }
        ],
    }


@pytest.fixture
def sample_candidate_healthcare():
    """Candidate with healthcare domain experience."""
    return {
        "candidate_id": "cand_003",
        "target_role_families": ["healthcare_data"],
        "skill_inventory": [
            {
                "canonical_skill": "HIPAA",
                "aliases": ["PHI", "HIPAA Compliance"],
                "evidence_refs": ["proj_001", "proj_002"],
                "proficiency_estimate": "expert",
            },
            {
                "canonical_skill": "Claims Processing",
                "aliases": ["Claims", "Pharmacy Claims"],
                "evidence_refs": ["proj_001"],
                "proficiency_estimate": "expert",
            },
        ],
        "experience_units": [
            {
                "experience_id": "exp_004",
                "title": "Healthcare Data Architect",
                "company": "Navitus Health Solutions",
                "skills": ["HIPAA", "Claims Processing"],
                "leadership_signals": ["led compliance"],
                "date_range": {"start": "2020-01-01", "end": None},
            }
        ],
    }


@pytest.fixture
def empty_candidate():
    """Candidate with no experience or skills."""
    return {
        "candidate_id": "cand_empty",
        "target_role_families": [],
        "skill_inventory": [],
        "experience_units": [],
    }


@pytest.fixture
def candidate_old_skill():
    """Candidate with skill from 5+ years ago."""
    return {
        "candidate_id": "cand_old",
        "target_role_families": [],
        "skill_inventory": [],
        "experience_units": [
            {
                "experience_id": "exp",
                "skills": ["Apache Kafka"],
                "date_range": {
                    "start": "2018-01-01",
                    "end": (date.today() - timedelta(days=1825)).isoformat(),
                },
            }
        ],
    }
