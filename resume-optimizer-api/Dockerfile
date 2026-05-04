# resume-optimizer-api — Lambda container image
#
# Build context: repo root
#   docker build -f resume-optimizer-api/Dockerfile -t resume-optimizer/api .
#
# Copies backend/ (business logic) + resume-optimizer-api/app/ (Lambda wrapper).
# backend/ is added to PYTHONPATH so the wrapper resolves backend/app.py correctly.

FROM public.ecr.aws/lambda/python:3.11

WORKDIR ${LAMBDA_TASK_ROOT}

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --prefer-binary numpy scipy \
 && pip install --no-cache-dir --prefer-binary -r requirements.txt \
 && pip install --no-cache-dir "mangum>=0.17.0"

RUN python -m spacy download en_core_web_sm

COPY backend/ ./backend/
COPY resume-optimizer-api/lambda_app/ ./lambda_app/

# backend/ on PYTHONPATH first so `from app import create_app` resolves to backend/app.py
# (not lambda_app — the package name no longer conflicts)
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}/backend:${LAMBDA_TASK_ROOT}"

CMD ["lambda_app.main.handler"]
