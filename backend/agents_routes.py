"""Phase 8: Agentic AI routes — thin entry-point.

Imports all route sub-modules so Flask registers every route on agents_bp.
app.py imports agents_bp from here.

Sub-modules:
  agents_routes_common.py     — Blueprint, shared helpers
  agents_routes_scout.py      — Job Scout + URL scraper routes
  agents_routes_pipeline.py   — Application Pipeline routes
  agents_routes_system.py     — Agent runs log + system status
  agents_routes_tailor.py     — Resume Tailor + Cover Letter routes
  agents_routes_coach.py      — Interview Coach routes
  agents_routes_advisor.py    — Career Advisor + salary routes
  agents_routes_orchestrator.py — Apply orchestration + feedback routes
"""

import agents_routes_advisor  # noqa: F401
import agents_routes_coach  # noqa: F401
import agents_routes_orchestrator  # noqa: F401
import agents_routes_pipeline  # noqa: F401

# Import sub-modules to trigger @agents_bp.route() registration
import agents_routes_scout  # noqa: F401
import agents_routes_system  # noqa: F401
import agents_routes_tailor  # noqa: F401
from agents_routes_common import agents_bp  # noqa: F401 — re-exported for app.py
