"""QA Audit — shared data types, constants, and path helpers.

Imported by all qa_audit_* modules. Never imports from other qa_audit_* files.
"""

import json  # noqa: F401 — re-exported for consumers
from dataclasses import asdict, dataclass, field  # noqa: F401 — re-exported
from datetime import datetime, timezone  # noqa: F401 — re-exported
from pathlib import Path

# Resolve project paths
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
TESTS_DIR = BACKEND_DIR / "tests"
ROADMAP_DIR = BACKEND_DIR.parent / "roadmap"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class FileGrade:
    path: str
    tier: str  # A/B/C/D/F
    test_count: int
    content_checks: int  # assertions checking response body values
    db_queries: int  # calls to query_db()
    schema_checks: int  # calls to schema validation helpers
    llm_verified: int  # tests using require_harness fixture
    anti_patterns: list = field(default_factory=list)
    content_pct: float = 0.0
    db_pct: float = 0.0
    schema_pct: float = 0.0
    # Quality-weighted content: trivial=0.5, structural=0.75, semantic=1.0
    quality_content_pct: float = 0.0
    total_assertions: int = 0
    file_name: str = ""  # convenience: basename only


@dataclass
class DepartmentReport:
    name: str
    agents: list = field(default_factory=list)
    governed_count: int = 0
    ungoverned_count: int = 0
    accountability_metric: str = ""
    current_status: str = "NO GOVERNANCE"


@dataclass
class AuditResult:
    files: list = field(default_factory=list)
    departments: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    governance_rules: dict = field(default_factory=dict)
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Department map (Section 3.5 Accountability Matrix)
# ---------------------------------------------------------------------------

DEPARTMENT_MAP = {
    "PMO": {
        "agents": [],
        "test_files": [],
        "metric": "Session state persisted, phases gated",
    },
    "Architecture": {
        "agents": [],
        "test_files": [],
        "metric": "Schemas defined for tested routes",
    },
    "Software Engineering": {
        "agents": ["Batch Jobs Manager", "LLM Router", "Document Parser"],
        "test_files": ["test_jobs.py", "test_e2e_functional.py"],
        "metric": "Zero thread leaks, zero crashes",
    },
    "Resume & Talent": {
        "agents": [
            "Career Advisor",
            "Resume Tailor",
            "Experience Chat",
            "Interview Coach",
            "Deep Profile",
            "Skills Interview",
            "ATS Improvement",
            "Builder",
            "Deep Interview",
        ],
        "test_files": [
            "test_agents_wave2_live.py",
            "test_experience.py",
            "test_llm_chat_modules.py",
            "test_builder.py",
            "test_profile.py",
            "test_deep_profile_interview.py",
        ],
        "metric": "All agents Tier-A tested",
    },
    "Job Management": {
        "agents": ["Application Tracker", "Job Scout"],
        "test_files": ["test_agents_wave2_live.py", "test_integration_agents.py"],
        "metric": "Maintained Tier-A",
    },
    "Marketing": {
        "agents": ["Campaign Manager", "Post Generator"],
        "test_files": ["test_campaigns_full.py", "test_integration_campaigns.py"],
        "metric": "test_campaigns.py upgraded or deleted",
    },
    "QA/Testing": {
        "agents": [],
        "test_files": [],
        "metric": "qa_audit.py enforcing quality gates",
    },
    "DevOps/Frontend": {
        "agents": [],
        "test_files": ["test_frontend_governance.py"],
        "metric": "Build passes, E2E tests exist",
    },
}

# Weights: trivial=0.5, structural=0.75, semantic=1.0
QUALITY_WEIGHTS = {"trivial": 0.5, "structural": 0.75, "semantic": 1.0}


def _tier_rank(tier):
    """Return numeric rank for tier comparison (lower = better)."""
    return {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}.get(tier, 5)
