"""Flask app factory for resume-optimizer-api.

Delegates to backend/app.py create_app() — no code duplication.
backend/ is on PYTHONPATH in both local dev and the Lambda Docker image.
"""
from __future__ import annotations

import os
import sys

# Add backend/ to path so `from app import create_app` resolves to backend/app.py
for _candidate in (
    os.path.join(os.path.dirname(__file__), "..", "..", "backend"),   # local dev
    os.path.join(os.environ.get("LAMBDA_TASK_ROOT", "/var/task"), "backend"),  # Lambda
):
    _candidate = os.path.realpath(_candidate)
    if os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from app import create_app  # noqa: E402 — resolves to backend/app.py

__all__ = ["create_app"]
