# resume-optimizer-workers — ECS Fargate container
#
# Build context: repo root (docker build -f resume-optimizer-workers/Dockerfile .)
# Long-running worker; consumes SQS chunks queue, processes via Bedrock, publishes results.
#
# CLOUDLIFT_ENV=aws  → runs run_sqs_worker() (long-poll SQS)
# CLOUDLIFT_ENV=local → runs start_worker()  (Artemis STOMP)

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
 && rm -rf /var/lib/apt/lists/*

# Deps from backend (single source of truth)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && python -m spacy download en_core_web_sm

# Backend business logic
COPY backend/ ./backend/

# Worker entry point
COPY resume-optimizer-workers/workers/ ./workers/

ENV PYTHONPATH="/app/backend:/app"

HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import sys; sys.path.insert(0,'/app/backend'); from analysis_worker import handle_chunk; print('ok')"

CMD ["python", "workers/analysis_worker.py"]
