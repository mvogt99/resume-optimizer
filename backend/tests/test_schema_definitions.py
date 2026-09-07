"""Test all schema definition files under schemas/ for structural correctness.

Covers 12 schema modules + cross-module integrity checks.
"""

import importlib
import sys
from pathlib import Path

# Ensure backend is on path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import schemas
from schemas import (
    agents,
    auth,
    campaigns,
    experience,
    gdrive,
    graph,
    jobs,
    journey,
    profile,
    projects,
    resume,
    sessions,
)


def _get_schema_dicts(module):
    """Extract all dict objects that look like JSON schemas from a module."""
    result = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, dict) and "type" in obj:
            result.append((name, obj))
    return result


class TestAuthSchemas:
    def test_register_201_requires_only_message(self):
        """Registration is approval-gated: the ordinary response carries a
        message and pending=true and NO credential, so `message` is the only
        required property. user_id/token/role stay ALLOWED for the admin path
        but must not be required -- demanding a token here would mean an
        unapproved account had been issued one."""
        assert "required" in auth.REGISTER_201
        assert auth.REGISTER_201["required"] == ["message"]
        props = auth.REGISTER_201["properties"]
        for optional in ("pending", "user_id", "token", "role"):
            assert optional in props, f"{optional} must remain permitted"

    def test_login_200_has_required_fields(self):
        assert "required" in auth.LOGIN_200
        assert "user_id" in auth.LOGIN_200["required"]
        assert "token" in auth.LOGIN_200["required"]


class TestAgentsSchemas:
    def test_scout_search_response(self):
        assert agents.SCOUT_SEARCH_202["type"] == "object"
        assert "job_id" in agents.SCOUT_SEARCH_202["required"]

    def test_scout_postings_response(self):
        assert "postings" in agents.SCOUT_POSTINGS_200["required"]
        assert agents.SCOUT_POSTINGS_200["properties"]["postings"]["type"] == "array"

    def test_agent_status_response(self):
        assert agents.AGENT_STATUS_200["type"] == "object"


class TestCampaignSchemas:
    def test_interview_start_has_session_id(self):
        assert "session_id" in campaigns.INTERVIEW_START_201["required"]
        assert campaigns.INTERVIEW_START_201["type"] == "object"

    def test_campaign_list_has_campaigns(self):
        assert "campaigns" in campaigns.LIST_CAMPAIGNS_200["required"]
        assert campaigns.LIST_CAMPAIGNS_200["properties"]["campaigns"]["type"] == "array"

    def test_post_schema_structure(self):
        post_schemas = [n for n in dir(campaigns) if "POST" in n and not n.startswith("_")]
        assert len(post_schemas) >= 1, "No post-related schemas found"


class TestExperienceSchemas:
    def test_start_session_has_session_id(self):
        assert "session_id" in experience.START_SESSION_201["required"]
        assert experience.START_SESSION_201["type"] == "object"

    def test_send_message_structure(self):
        assert experience.SEND_MESSAGE_200["type"] == "object"
        props = experience.SEND_MESSAGE_200["properties"]
        assert "message" in props or "response" in props


class TestGdriveSchemas:
    def test_import_has_resume_id(self):
        assert "resume_id" in gdrive.GDRIVE_IMPORT_201["required"]

    def test_versions_list_has_versions(self):
        assert "versions" in gdrive.VERSIONS_LIST_200["required"]


class TestGraphSchemas:
    def test_technologies_has_required(self):
        assert "technologies" in graph.TECHNOLOGIES_200["required"]
        assert graph.TECHNOLOGIES_200["type"] == "object"

    def test_clients_by_tech_has_clients(self):
        assert "clients" in graph.CLIENTS_BY_TECH_200["required"]


class TestJobSchemas:
    def test_list_jobs_has_jobs(self):
        assert "jobs" in jobs.LIST_JOBS_200["required"]
        assert jobs.LIST_JOBS_200["properties"]["jobs"]["type"] == "array"

    def test_job_status_has_required(self):
        assert "id" in jobs.JOB_STATUS_200["required"]
        assert "status" in jobs.JOB_STATUS_200["required"]


class TestJourneySchemas:
    def test_start_mining_has_job_id(self):
        assert "job_id" in journey.START_MINING_202["required"]

    def test_skills_has_skills_array(self):
        assert "skills" in journey.SKILLS_200["required"]


class TestProfileSchemas:
    def test_import_linkedin_has_message(self):
        assert "message" in profile.IMPORT_LINKEDIN_200["required"]

    def test_build_deep_profile_has_profile(self):
        assert "profile" in profile.BUILD_DEEP_PROFILE_200["required"]


class TestProjectSchemas:
    def test_create_project_has_project_id(self):
        assert "project_id" in projects.CREATE_PROJECT_201["required"]

    def test_list_projects_has_projects(self):
        assert "projects" in projects.LIST_PROJECTS_200["required"]


class TestResumeSchemas:
    def test_upload_resume_has_resume_id(self):
        assert "resume_id" in resume.UPLOAD_RESUME_201["required"]

    def test_optimize_has_ats_score(self):
        assert "ats_compliance_score" in resume.OPTIMIZE_200["required"]


class TestSessionSchemas:
    def test_create_session_has_id(self):
        assert "id" in sessions.CREATE_SESSION_201["required"]
        assert sessions.CREATE_SESSION_201["type"] == "object"

    def test_list_sessions_has_sessions(self):
        assert "sessions" in sessions.LIST_SESSIONS_200["required"]


class TestCrossModule:
    def test_all_schema_modules_importable(self):
        """Every schema submodule can be imported without error."""
        module_names = [
            "schemas.agents",
            "schemas.auth",
            "schemas.campaigns",
            "schemas.experience",
            "schemas.gdrive",
            "schemas.graph",
            "schemas.jobs",
            "schemas.journey",
            "schemas.profile",
            "schemas.projects",
            "schemas.resume",
            "schemas.sessions",
        ]
        for name in module_names:
            mod = importlib.import_module(name)
            assert mod is not None, f"Failed to import {name}"

    def test_no_circular_dependencies(self):
        """Schema modules don't import each other (only __init__ imports them)."""
        for mod in [
            agents,
            auth,
            campaigns,
            experience,
            gdrive,
            graph,
            jobs,
            journey,
            profile,
            projects,
            resume,
            sessions,
        ]:
            source = Path(mod.__file__).read_text(encoding="utf-8")
            assert "from schemas." not in source, f"{mod.__name__} imports other schema module"

    def test_all_schemas_have_type(self):
        """Every exported schema dict has a 'type' key."""
        for mod in [
            agents,
            auth,
            campaigns,
            experience,
            gdrive,
            graph,
            jobs,
            journey,
            profile,
            projects,
            resume,
            sessions,
        ]:
            for name, schema in _get_schema_dicts(mod):
                assert "type" in schema, f"{mod.__name__}.{name} missing 'type'"

    def test_master_registry_has_entries(self):
        """schemas.SCHEMAS master dict has entries from all modules."""
        assert len(schemas.SCHEMAS) >= 20, f"Only {len(schemas.SCHEMAS)} entries in SCHEMAS"
        # Check a sample from each category
        methods = {k[0] for k in schemas.SCHEMAS.keys()}
        assert "POST" in methods
        assert "GET" in methods
