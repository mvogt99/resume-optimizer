"""CloudLift queue adapter for resume-optimizer — thin shim.

Routes message queue operations based on CLOUDLIFT_ENV:
  local: Artemis STOMP — handled by bus_client.py (application layer); this
         adapter is not called in local mode (bus_client checks is_aws() first)
  aws:   Amazon SQS FIFO — delegates via lazy boto3 import (cloudlift pattern)

Note: cloudlift SQSAdapter uses tenant-prefixed queue names incompatible with
RO's domain-specific queue naming (ro-{env}-analysis-*.fifo). SQS operations
use lazy boto3 import following cloudlift.bridge pattern.

Queue URLs (us-east-1, account 604023213058):
  ro-test-analysis-chunks.fifo   — chunk publish/consume
  ro-test-analysis-results.fifo  — result publish/consume
  ro-test-analysis-dlq.fifo      — dead letter for chunks
"""
from __future__ import annotations

import json
import logging
import os
import time

logger = logging.getLogger(__name__)

CLOUDLIFT_ENV = os.environ.get("CLOUDLIFT_ENV", "local")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
RO_ENV = os.environ.get("RO_ENV", "test")

CHUNKS_QUEUE_NAME = f"ro-{RO_ENV}-analysis-chunks.fifo"
RESULTS_QUEUE_NAME = f"ro-{RO_ENV}-analysis-results.fifo"


def is_aws() -> bool:
    return CLOUDLIFT_ENV == "aws"


def _sqs():
    """Return a boto3 SQS client — lazy import per cloudlift pattern."""
    import boto3  # noqa: PLC0415
    return boto3.client("sqs", region_name=AWS_REGION)


def _queue_url(client, name: str) -> str:
    return client.get_queue_url(QueueName=name)["QueueUrl"]


def publish_chunk(
    doc_id: str,
    chunk_idx: int,
    chunk_text: str,
    context: str,
    extractors: list[str],
) -> bool:
    """Publish a document chunk for analysis via SQS FIFO.

    Mirrors bus_client.ResumeAnalysisBus.publish_chunk() interface.
    Returns True on success, False on failure (caller falls back to inline).
    """
    try:
        client = _sqs()
        url = _queue_url(client, CHUNKS_QUEUE_NAME)
        body = json.dumps({
            "doc_id": doc_id,
            "chunk_idx": chunk_idx,
            "chunk_text": chunk_text,
            "context": context,
            "extractors": extractors,
        })
        client.send_message(
            QueueUrl=url,
            MessageBody=body,
            MessageGroupId=str(doc_id),
            MessageDeduplicationId=f"{doc_id}-{chunk_idx}-{time.time_ns()}",
        )
        return True
    except Exception as exc:
        logger.error("[sqs] publish_chunk failed: %s", exc)
        return False


def receive_chunks(max_messages: int = 10, wait_seconds: int = 20) -> list[dict]:
    """Long-poll SQS for chunk messages.

    Returns list of dicts: {receipt_handle, body (parsed dict)}.
    Only call in CLOUDLIFT_ENV=aws — returns [] in local mode.
    """
    if not is_aws():
        return []
    try:
        client = _sqs()
        url = _queue_url(client, CHUNKS_QUEUE_NAME)
        resp = client.receive_message(
            QueueUrl=url,
            MaxNumberOfMessages=min(max_messages, 10),
            WaitTimeSeconds=wait_seconds,
        )
        out = []
        for msg in resp.get("Messages", []):
            try:
                out.append({"receipt_handle": msg["ReceiptHandle"], "body": json.loads(msg["Body"])})
            except json.JSONDecodeError:
                pass
        return out
    except Exception as exc:
        logger.error("[sqs] receive_chunks failed: %s", exc)
        return []


def delete_message(receipt_handle: str) -> None:
    """Acknowledge and delete a processed chunk message."""
    try:
        client = _sqs()
        url = _queue_url(client, CHUNKS_QUEUE_NAME)
        client.delete_message(QueueUrl=url, ReceiptHandle=receipt_handle)
    except Exception as exc:
        logger.error("[sqs] delete_message failed: %s", exc)


def publish_result(doc_id: str, chunk_idx: int, result: dict) -> bool:
    """Publish an extraction result to the results queue."""
    try:
        client = _sqs()
        url = _queue_url(client, RESULTS_QUEUE_NAME)
        body = json.dumps({"doc_id": doc_id, "chunk_idx": chunk_idx, "result": result})
        client.send_message(
            QueueUrl=url,
            MessageBody=body,
            MessageGroupId=str(doc_id),
            MessageDeduplicationId=f"{doc_id}-result-{chunk_idx}-{time.time_ns()}",
        )
        return True
    except Exception as exc:
        logger.error("[sqs] publish_result failed: %s", exc)
        return False
