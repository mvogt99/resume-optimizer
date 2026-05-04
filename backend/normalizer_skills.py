"""Canonical skill inventory — synonym/alias mappings and skill-building helpers.

Provides:
  CANONICAL_SKILL_MAP   — known skill synonyms keyed by lowercase canonical key
  find_canonical_skill  — look up canonical name for any alias
  get_skill_aliases     — get all aliases for a canonical skill
  build_inventory_from_arango  — query ro_skills with client provenance, cluster canonically
  enhance_inventory_with_llm   — use LLM to add resume-derived skills
"""

import json
import logging

logger = logging.getLogger(__name__)

# Canonical skill groups: key → {canonical, aliases}
CANONICAL_SKILL_MAP = {
    "kafka": {"canonical": "Apache Kafka", "aliases": [
        "Kafka", "Apache Kafka", "AWS Kafka", "MSK", "MSK/Kinesis", "Kinesis/MSK",
        "Apache Kafka / MSK", "MSK (Managed Streaming for Kafka)", "Kafka Streams",
    ]},
    "kinesis": {"canonical": "Amazon Kinesis", "aliases": [
        "Kinesis", "AWS Kinesis", "Amazon Kinesis", "Kinesis Streams",
        "Kinesis Data Streams", "AWS Kinesis Data Streams", "AWS Kinesis Data Firehose",
        "AWS Kinesis Data Analytics", "Kinesis Analytics",
    ]},
    "flink": {"canonical": "Apache Flink", "aliases": [
        "Flink", "Apache Flink", "Flink SQL", "PyFlink",
    ]},
    "spark": {"canonical": "Apache Spark", "aliases": [
        "Spark", "Apache Spark", "PySpark", "Spark Streaming", "Spark SQL",
        "Databricks Spark", "Spark Structured Streaming", "EMR Spark",
    ]},
    "debezium": {"canonical": "Debezium CDC", "aliases": [
        "Debezium", "CDC", "Change Data Capture", "AWS DMS",
        "Database Migration Service", "DMS", "Debezium CDC",
    ]},
    "eventhub": {"canonical": "Azure Event Hubs", "aliases": [
        "EventHub", "Event Hub", "Azure Event Hubs", "EventHubs",
        "EventHub Integration", "EventHub Triggering",
    ]},
    "eventbridge": {"canonical": "AWS EventBridge", "aliases": [
        "EventBridge", "AWS EventBridge", "EventBridge Pipes", "EventBridge Pipe",
        "EventBridge Polling", "Default Event Bus", "EventBridge Default Event Bus",
    ]},
    "databricks": {"canonical": "Databricks", "aliases": [
        "Databricks", "Databricks Lakehouse Architecture", "Azure Databricks",
        "Databricks Jobs", "Databricks Platform", "Databricks Workspace",
        "Databricks Asset Bundles", "Databricks secret scopes", "Unity Catalog",
    ]},
    "delta_lake": {"canonical": "Delta Lake", "aliases": [
        "Delta Lake", "Databricks/Delta Lake", "Delta Live Tables", "Delta Sharing",
        "Delta Load Strategies", "Delta Batch Load",
    ]},
    "iceberg": {"canonical": "Apache Iceberg", "aliases": [
        "Iceberg", "Apache Iceberg", "Apache Iceberg Tables", "Iceberg Tables",
        "Iceberg Table Format", "Iceberg partitioning", "Iceberg Table Management",
        "S3/Iceberg", "Athena Iceberg", "Athena Iceberg Tables",
    ]},
    "snowflake": {"canonical": "Snowflake", "aliases": [
        "Snowflake", "Snowflake Data Cloud", "Snowflake Data Platform",
        "Snowflake Multi-Tenant Architecture",
    ]},
    "dbt": {"canonical": "dbt", "aliases": [
        "dbt", "dbt Core", "dbt Cloud", "DBT",
    ]},
    "data_mesh": {"canonical": "Data Mesh", "aliases": [
        "data mesh", "Data Mesh", "domain ownership", "data product", "data products",
        "federated governance", "self-serve data platform", "Data Mesh architecture",
    ]},
    "lakehouse": {"canonical": "Data Lakehouse", "aliases": [
        "lakehouse", "Lakehouse", "Data Lakehouse", "DLH", "data lakehouse",
        "Lake House Architecture", "Data Lake House", "Lakehouse Architecture",
        "Data Lakehouse Architecture", "Medallion Architecture",
    ]},
    "hipaa": {"canonical": "HIPAA Compliance", "aliases": [
        "HIPAA", "HIPAA Compliance", "PHI", "Protected Health Information",
        "HIPAA/HITECH", "health data privacy", "HIPAA Security Rule",
    ]},
    "hl7": {"canonical": "HL7 / FHIR", "aliases": [
        "HL7", "FHIR", "HL7 FHIR", "HL7 v2", "HL7 v3", "SMART on FHIR",
    ]},
    "aws": {"canonical": "Amazon Web Services", "aliases": [
        "AWS", "Amazon Web Services", "Amazon AWS",
    ]},
    "azure": {"canonical": "Microsoft Azure", "aliases": [
        "Azure", "Microsoft Azure", "Azure Cloud",
    ]},
    "gcp": {"canonical": "Google Cloud Platform", "aliases": [
        "GCP", "Google Cloud", "Google Cloud Platform",
    ]},
    "python": {"canonical": "Python", "aliases": [
        "Python", "Python 3", "Python3", "Python scripting",
    ]},
    "scala": {"canonical": "Scala", "aliases": [
        "Scala", "Scala 2", "Scala 3",
    ]},
    "airflow": {"canonical": "Apache Airflow", "aliases": [
        "Airflow", "Apache Airflow", "MWAA", "Managed Airflow",
    ]},
    "terraform": {"canonical": "Terraform", "aliases": [
        "Terraform", "Terraform IaC", "Terraform modules",
    ]},
    "kubernetes": {"canonical": "Kubernetes", "aliases": [
        "Kubernetes", "K8s", "EKS", "AKS", "GKE", "Helm",
    ]},
}


def find_canonical_skill(skill_name: str) -> str:
    """Look up the canonical name for a skill name or alias.

    Returns the canonical name if found, otherwise returns the input unchanged.
    """
    lower = skill_name.lower()
    for key, mapping in CANONICAL_SKILL_MAP.items():
        aliases_lower = [a.lower() for a in mapping["aliases"]]
        if lower in aliases_lower or lower == key:
            return mapping["canonical"]
    return skill_name


def get_skill_aliases(canonical_skill: str) -> list:
    """Get all known aliases for a canonical skill name."""
    lower = canonical_skill.lower()
    for key, mapping in CANONICAL_SKILL_MAP.items():
        if mapping["canonical"].lower() == lower or key == lower:
            return list(mapping["aliases"])
    return [canonical_skill]


def build_inventory_from_arango(arango_client) -> list:
    """Build canonical skill inventory from ArangoDB ro_skills + client provenance."""
    if not arango_client or not arango_client.is_connected:
        return []

    aql = """
    FOR skill IN ro_skills
      FILTER skill.category IN ["technology", "domain_expertise", "DLH Platform"]
      LET clients = (
        FOR client IN 1..1 INBOUND skill ro_client_demonstrated_skill
          RETURN client.name
      )
      FILTER LENGTH(clients) > 0
      RETURN {
        name: skill.name,
        category: skill.category,
        proficiency: skill.proficiency_signal,
        clients: clients,
        skill_id: skill._id
      }
    """
    try:
        raw_skills = arango_client.query(aql)
    except Exception as e:
        logger.warning("normalizer_skills: failed to query ro_skills: %s", e)
        return []

    inventory: dict = {}  # canonical_key → item

    for skill in raw_skills:
        name = skill.get("name", "")
        lower = name.lower()
        skill_id = skill.get("skill_id", "")
        clients = skill.get("clients", [])

        canonical_key = None
        canonical_name = None
        for key, mapping in CANONICAL_SKILL_MAP.items():
            aliases_lower = [a.lower() for a in mapping["aliases"]]
            if lower in aliases_lower or lower == key:
                canonical_key = key
                canonical_name = mapping["canonical"]
                break

        if canonical_key is None:
            canonical_key = lower.replace(" ", "_")[:40]
            canonical_name = name

        if canonical_key not in inventory:
            inventory[canonical_key] = {
                "canonical_skill": canonical_name,
                "aliases": [],
                "categories": [skill.get("category", "technology")],
                "proficiency_estimate": "proficient",
                "years_estimate": None,
                "evidence_refs": [],
                "_client_set": set(),
            }

        item = inventory[canonical_key]
        if name not in item["aliases"]:
            item["aliases"].append(name)
        item["_client_set"].update(clients)
        if skill_id and skill_id not in item["evidence_refs"]:
            item["evidence_refs"].append(skill_id)

    # Backfill known aliases not yet in DB
    for key, mapping in CANONICAL_SKILL_MAP.items():
        if key in inventory:
            existing = {a.lower() for a in inventory[key]["aliases"]}
            for alias in mapping["aliases"]:
                if alias.lower() not in existing:
                    inventory[key]["aliases"].append(alias)

    return [
        {k: v for k, v in item.items() if k != "_client_set"}
        for item in inventory.values()
    ]


def enhance_inventory_with_llm(
    existing_inventory: list,
    resume_text: str,
    target_role: str = "",
) -> list:
    """Use LLM to add resume-derived skills not yet in the canonical inventory."""
    try:
        from llm_helper import call_llm_quality as _call_llm

        existing_canonicals = [item["canonical_skill"] for item in existing_inventory[:20]]

        prompt = f"""You are normalizing a candidate's skill inventory for ATS matching.

CANDIDATE RESUME (abbreviated):
{resume_text[:1500]}

EXISTING CANONICAL SKILLS (from career knowledge graph):
{json.dumps(existing_canonicals)}

TARGET ROLE: {target_role or "Data Platform Architect"}

Identify important skills in the resume NOT already in the existing list. \
For each, provide a canonical name and aliases.

Respond with ONLY valid JSON:
{{
  "additional_skills": [
    {{
      "canonical_skill": "<canonical name>",
      "aliases": ["<alias1>", "<alias2>"],
      "categories": ["<technology|methodology|domain_expertise>"],
      "proficiency_estimate": "expert|proficient|familiar",
      "evidence_refs": []
    }}
  ]
}}

Rules: Limit 15 additions, no duplicates from existing list."""

        raw = _call_llm(prompt, task_type="analysis", max_tokens=1200)
        if not raw:
            return existing_inventory
        cleaned = raw.strip()
        for fence in ("```json", "```"):
            if fence in cleaned:
                start = cleaned.find(fence) + len(fence)
                end = cleaned.find("```", start)
                if end > start:
                    cleaned = cleaned[start:end].strip()
                    break
        import json as _json
        parsed = _json.loads(cleaned)
        additions = parsed.get("additional_skills", [])
        if additions:
            logger.info("normalizer_skills: LLM added %d skills to inventory", len(additions))
            return existing_inventory + additions
    except Exception as e:
        logger.warning("normalizer_skills: LLM enhancement failed: %s", e)

    return existing_inventory
