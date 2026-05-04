"""ECS Fargate worker entry point.

Thin wrapper that delegates to backend/analysis_worker.py.
In the Docker image, backend/ is at /app/backend/ and on PYTHONPATH.

CLOUDLIFT_ENV=aws   → run_sqs_worker() (long-poll SQS FIFO)
CLOUDLIFT_ENV=local → start_worker()   (subscribe to Artemis STOMP)
"""
from __future__ import annotations

import os
import sys

for _candidate in (
    os.path.join(os.path.dirname(__file__), "..", "..", "backend"),  # local dev
    "/app/backend",  # Fargate image
):
    _candidate = os.path.realpath(_candidate)
    if os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from analysis_worker import run_sqs_worker, start_worker  # noqa: E402

if __name__ == "__main__":
    if os.environ.get("CLOUDLIFT_ENV") == "aws":
        print("[workers] SQS mode — polling ro-test-analysis-chunks.fifo")
        run_sqs_worker()
    else:
        print("[workers] Artemis mode — subscribing to STOMP queue")
        start_worker()
