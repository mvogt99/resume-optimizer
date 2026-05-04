"""Job description parser — decomposes JD text into atomic, typed requirement objects.

Produces normalized_requirements conforming to the production schema:
  requirement_id     — deterministic SHA-1 key
  requirement_type   — must_have | preferred | leadership | domain | education | certification | other
  category           — semantic category (e.g. "Streaming Technologies")
  text               — original requirement text
  canonical_skills   — skills extracted from this requirement
  importance         — 0.0–1.0 weight (must_have=1.0, preferred=0.7, domain=0.5, other=0.3)
"""

import hashlib
import json
import logging
import re

logger = logging.getLogger(__name__)

# Module-level LLM import — allows test patching via patch("jd_parser.call_llm_quality")
try:
    from llm_helper import call_llm_quality
except ImportError:  # pragma: no cover
    call_llm_quality = None  # type: ignore[assignment]

# Importance weights by requirement type
IMPORTANCE_WEIGHTS = {
    "must_have": 1.0,
    "leadership": 0.85,
    "preferred": 0.7,
    "domain": 0.5,
    "certification": 0.5,
    "education": 0.4,
    "other": 0.3,
}

# Heuristic signal phrases for each requirement type (fast pre-classification)
_TYPE_SIGNALS = {
    "must_have": [
        "required", "must have", "must-have", "you must", "minimum",
        "require", "essential", "mandatory", "need", "needs to have",
        "5+ years", "7+ years", "10+ years", "3+ years", "experience with",
        "hands-on", "proven experience", "strong experience",
    ],
    "preferred": [
        "preferred", "nice to have", "nice-to-have", "a plus", "bonus",
        "ideally", "desirable", "advantageous", "familiar with", "exposure to",
        "experience with is a plus", "knowledge of",
    ],
    "leadership": [
        "lead", "leading", "manage", "mentor", "director", "head of",
        "principal", "strategy", "stakeholder", "collaborate", "cross-functional",
        "partner with", "influence", "executive", "roadmap", "govern",
    ],
    "domain": [
        "healthcare", "hipaa", "phi", "hl7", "fhir", "pharma", "finance",
        "fintech", "retail", "insurance", "compliance", "regulated",
        "data mesh", "lakehouse", "medallion", "domain", "industry",
    ],
    "certification": [
        "certified", "certification", "aws certified", "azure certified",
        "gcp certified", "cpa", "cissp", "pmp", "databricks certified",
    ],
    "education": [
        "bachelor", "master", "phd", "degree", "bs ", "ms ", "b.s.", "m.s.",
        "computer science", "engineering degree", "equivalent experience",
    ],
}


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def _extract_json(text, fallback) -> list:
    if text is None:
        return fallback
    # Already parsed — return directly
    if isinstance(text, list):
        return text
    if isinstance(text, dict):
        return text.get("requirements", fallback)
    cleaned = str(text).strip()
    for fence in ("```json", "```"):
        if fence in cleaned:
            start = cleaned.find(fence) + len(fence)
            end = cleaned.find("```", start)
            if end > start:
                cleaned = cleaned[start:end].strip()
                break
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return parsed.get("requirements", fallback)
    except (json.JSONDecodeError, ValueError):
        logger.warning("JD parser: non-JSON LLM response, using heuristic fallback")
    return fallback


def _heuristic_type(text: str) -> str:
    """Classify a requirement line using keyword signals (no LLM)."""
    lower = text.lower()
    for req_type, signals in _TYPE_SIGNALS.items():
        if any(sig in lower for sig in signals):
            return req_type
    return "other"


def _split_jd_sentences(job_text: str) -> list[str]:
    """Split JD text into candidate requirement lines."""
    lines = []
    for line in job_text.split("\n"):
        line = line.strip().lstrip("-•·*▪▸").strip()
        if len(line) > 20:
            lines.append(line)
    # Also split on semicolons for run-on sentences
    expanded = []
    for line in lines:
        parts = re.split(r";(?!\s*\d)", line)
        expanded.extend(p.strip() for p in parts if len(p.strip()) > 20)
    return expanded


def _heuristic_parse(job_text: str) -> list[dict]:
    """Fallback: parse JD using heuristics when LLM is unavailable."""
    lines = _split_jd_sentences(job_text)
    requirements = []
    for line in lines:
        req_type = _heuristic_type(line)
        req_id = _sha1(line)
        requirements.append({
            "requirement_id": req_id,
            "requirement_type": req_type,
            "category": _infer_category(line),
            "text": line,
            "canonical_skills": _extract_skills_heuristic(line),
            "importance": IMPORTANCE_WEIGHTS[req_type],
        })
    return requirements


def _infer_category(text: str) -> str:
    """Infer a semantic category from requirement text using keyword rules."""
    lower = text.lower()
    category_rules = [
        (["kafka", "kinesis", "flink", "debezium", "spark streaming", "event hub",
          "event-driven", "streaming", "pubsub", "message queue", "msk"], "Streaming & Event Processing"),
        (["databricks", "snowflake", "redshift", "bigquery", "synapse", "delta lake",
          "iceberg", "hudi", "lakehouse", "data warehouse"], "Data Warehousing & Analytics"),
        (["airflow", "dbt", "glue", "fivetran", "stitch", "nifi", "pipeline",
          "etl", "elt", "ingestion", "orchestration"], "Data Pipeline & Orchestration"),
        (["kubernetes", "docker", "terraform", "helm", "eks", "aks", "gke",
          "ci/cd", "devops", "infrastructure"], "Cloud Infrastructure & DevOps"),
        (["hipaa", "hl7", "fhir", "phi", "healthcare", "clinical", "claims",
          "formulary", "pharmacy"], "Healthcare & Compliance"),
        (["python", "scala", "java", "go", "sql", "pyspark", "java", "rust",
          "typescript"], "Programming Languages"),
        (["data mesh", "domain ownership", "data product", "federated", "self-serve"], "Data Mesh"),
        (["architect", "architecture", "design", "pattern", "strategy", "roadmap",
          "governance"], "Architecture & Strategy"),
        (["ml", "machine learning", "ai", "llm", "model", "feature store",
          "mlflow", "sagemaker"], "Machine Learning & AI"),
        (["aws", "azure", "gcp", "cloud", "s3", "ec2", "lambda"], "Cloud Platforms"),
    ]
    for keywords, category in category_rules:
        if any(kw in lower for kw in keywords):
            return category
    return "General"


def _extract_skills_heuristic(text: str) -> list[str]:
    """Extract likely skill/tool names from a requirement line."""
    known_skills = [
        "Kafka", "Kinesis", "Flink", "Debezium", "Spark", "Airflow", "dbt",
        "Databricks", "Snowflake", "Redshift", "BigQuery", "Synapse",
        "Kubernetes", "Docker", "Terraform", "Python", "Scala", "Java", "SQL",
        "AWS", "Azure", "GCP", "Delta Lake", "Iceberg", "Hudi", "HIPAA",
        "HL7", "FHIR", "NiFi", "Fivetran", "Glue", "MSK", "EventHub",
        "PostgreSQL", "MySQL", "Cassandra", "MongoDB", "Elasticsearch",
        "Helm", "Pulsar", "RabbitMQ", "Redis", "Go", "Rust", "Typescript",
        "MLflow", "SageMaker", "dbt Core", "Prefect", "Dagster",
    ]
    found = []
    lower = text.lower()
    for skill in known_skills:
        if skill.lower() in lower:
            found.append(skill)
    return found


def parse_requirements(job_text: str, use_llm: bool = True) -> list[dict]:
    """Parse a job description into atomic typed requirement objects.

    Args:
        job_text: Raw job description text.
        use_llm:  If True, attempt LLM-based parsing first with heuristic fallback.

    Returns:
        List of requirement dicts conforming to the production schema.
        Never raises — returns heuristic parse on any error.
    """
    if not job_text or len(job_text.strip()) < 50:
        return []

    if use_llm:
        try:
            prompt = f"""You are parsing a job description into atomic, typed requirements.

JOB DESCRIPTION:
{job_text[:3000]}

Decompose each distinct requirement into a structured object. For requirements that list \
multiple skills (e.g. "Experience with Kafka, Flink, and Debezium"), create ONE requirement \
object for the group.

Respond with ONLY a JSON array. Each element must have:
{{
  "requirement_type": "must_have|preferred|leadership|domain|education|certification|other",
  "category": "<semantic category, e.g. Streaming Technologies, Healthcare Compliance, Data Architecture>",
  "text": "<the requirement text, verbatim or lightly cleaned>",
  "canonical_skills": ["<skill1>", "<skill2>"],
  "importance": <0.0-1.0 — must_have=1.0, preferred=0.7, leadership=0.85, domain=0.5, education=0.4>
}}

Rules:
- must_have: explicitly required, deal-breaker if absent
- preferred: nice-to-have, bonus
- leadership: stakeholder influence, team leadership, strategy, governance
- domain: industry/business context (healthcare, finance, data mesh)
- education/certification: degrees, certs
- Do NOT include company boilerplate (benefits, EEO statements, salary)
- Limit to 25 most important requirements
- Return ONLY the JSON array, no other text"""

            raw = call_llm_quality(prompt, task_type="analysis", max_tokens=2048)
            parsed = _extract_json(raw, [])
            if parsed:
                # Enrich with deterministic IDs and validate schema
                result = []
                for req in parsed:
                    req_text = req.get("text", "")
                    if not req_text:
                        continue
                    req_type = req.get("requirement_type", "other")
                    if req_type not in IMPORTANCE_WEIGHTS:
                        req_type = "other"
                    result.append({
                        "requirement_id": _sha1(req_text),
                        "requirement_type": req_type,
                        "category": req.get("category", _infer_category(req_text)),
                        "text": req_text,
                        "canonical_skills": req.get("canonical_skills", []),
                        "importance": IMPORTANCE_WEIGHTS.get(
                            req_type, req.get("importance", 0.3)
                        ),
                    })
                if result:
                    logger.info("JD parser: LLM produced %d requirements", len(result))
                    return result
        except Exception as exc:
            logger.warning("JD parser LLM failed, using heuristic fallback: %s", exc)

    result = _heuristic_parse(job_text)
    logger.info("JD parser: heuristic produced %d requirements", len(result))
    return result


def group_requirements_by_category(requirements: list[dict]) -> dict[str, list[dict]]:
    """Group requirements by category for display."""
    groups: dict[str, list] = {}
    for req in requirements:
        cat = req.get("category", "General")
        groups.setdefault(cat, []).append(req)
    # Sort each group by importance desc
    for cat in groups:
        groups[cat].sort(key=lambda r: r.get("importance", 0), reverse=True)
    return groups
