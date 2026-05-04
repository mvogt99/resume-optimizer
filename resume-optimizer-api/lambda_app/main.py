"""Lambda / gunicorn entry point for resume-optimizer-api.

AWS Lambda:  handler = Mangum(flask_app)
Local dev:   gunicorn lambda_app.main:flask_app
"""
from __future__ import annotations

import os

from lambda_app import create_app

flask_app = create_app()

if os.environ.get("CLOUDLIFT_ENV") == "aws":
    from mangum import Mangum  # noqa: PLC0415
    handler = Mangum(flask_app, lifespan="off")
