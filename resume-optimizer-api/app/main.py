"""Lambda entry point for resume-optimizer-api.

Wraps the Flask app with Mangum for AWS Lambda + API Gateway.
Local dev: run with gunicorn or flask run directly.
"""
import os
from app import create_app

app = create_app()

# Lambda handler (Mangum wraps Flask for API Gateway/Lambda)
if os.environ.get("CLOUDLIFT_ENV") == "aws":
    from mangum import Mangum  # noqa: PLC0415
    handler = Mangum(app, lifespan="off")
