"""CloudLift database adapter — thin shim resolving DATABASE_URL by CLOUDLIFT_ENV.

CLOUDLIFT_ENV=local → returns "" (app keeps SQLite via models.py default)
CLOUDLIFT_ENV=aws   → fetches RDS credentials from AWS Secrets Manager,
                       returns a postgresql:// URL for RDS ro-test-pg

Follows cloudlift.bridge pattern: no cloud SDK imports at module level;
boto3 is imported lazily inside _fetch_rds_url() only when CLOUDLIFT_ENV=aws.

Environment variables:
    RDS_SECRET_ARN  — Secrets Manager secret name or ARN (default: "ro/test/db")
    RDS_HOST        — override host read from secret
    RDS_PORT        — override port (default: 5432)
    RDS_DB          — override dbname (default: "ro_test")
    AWS_REGION      — region for Secrets Manager client (default: "us-east-1")
"""
from __future__ import annotations

import json
import logging
import os

_logger = logging.getLogger(__name__)

_cached_url: str | None = None


def resolve_database_url() -> str:
    """Return the DATABASE_URL for the current environment.

    Returns "" for local (caller keeps SQLite).
    Returns a valid postgresql:// URL for aws.
    Result is cached after the first call.
    """
    global _cached_url
    if _cached_url is not None:
        return _cached_url

    # If DATABASE_URL is already set (e.g., via host-level .env or docker-compose),
    # return it directly without calling Secrets Manager. This allows deployments
    # that don't use Secrets Manager (local Postgres, docker-compose, etc.) to work.
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        _logger.info("[db_adapter] using DATABASE_URL from environment")
        _cached_url = explicit
        return _cached_url

    env = os.environ.get("CLOUDLIFT_ENV", "local")
    if env != "aws":
        _cached_url = ""
        return _cached_url

    _cached_url = _fetch_rds_url()
    return _cached_url


def _fetch_rds_url() -> str:
    """Fetch RDS credentials from Secrets Manager and build a postgresql:// URL.

    Uses lazy boto3 import following cloudlift.bridge pattern — no SDK at module level.
    """
    import boto3  # noqa: PLC0415 — lazy import, only used in aws env

    secret_id = os.environ.get("RDS_SECRET_ARN", "ro/test/db")
    region = os.environ.get("AWS_REGION", "us-east-1")

    _logger.info("[db_adapter] fetching RDS credentials from Secrets Manager: %s", secret_id)
    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_id)
        secret = json.loads(response["SecretString"])
    except Exception as exc:
        raise RuntimeError(
            f"[db_adapter] failed to fetch secret '{secret_id}' from Secrets Manager "
            f"(region={region}): {exc}"
        ) from exc

    host = os.environ.get("RDS_HOST") or secret.get("host", "")
    port = int(os.environ.get("RDS_PORT") or secret.get("port", 5432))
    dbname = os.environ.get("RDS_DB") or secret.get("dbname", "ro_test")
    user = secret["username"]
    password = secret["password"]

    if not host:
        raise RuntimeError("[db_adapter] RDS host not found in secret or RDS_HOST env var")

    url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    _logger.info("[db_adapter] resolved RDS URL: postgresql://%s@%s:%d/%s", user, host, port, dbname)
    return url
