"""Live SQS integration tests — requires CLOUDLIFT_ENV=aws.

Usage:
  CLOUDLIFT_ENV=aws AWS_REGION=us-east-1 pytest tests/test_sqs_integration.py -v
"""
import os
import time
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CLOUDLIFT_ENV") != "aws",
    reason="SQS tests require CLOUDLIFT_ENV=aws",
)


def test_publish_and_receive_chunk():
    """Round-trip: publish a chunk, receive it, delete it."""
    import sys
    sys.path.insert(0, ".")
    from cloudlift_queue_adapter import publish_chunk, receive_chunks, delete_message

    unique_id = f"test-{time.time_ns()}"
    sent = publish_chunk(
        doc_id=unique_id,
        chunk_idx=0,
        chunk_text="Python developer with 5 years experience",
        context="resume",
        extractors=["tech"],
    )
    assert sent, "publish_chunk returned False"

    messages = receive_chunks(max_messages=1, wait_seconds=10)
    assert messages, "No messages received from SQS chunks queue"

    body = messages[0]["body"]
    assert body["doc_id"] == unique_id
    assert body["chunk_idx"] == 0
    assert "Python" in body["chunk_text"]

    delete_message(messages[0]["receipt_handle"])


def test_publish_result():
    """Publish a result to the results queue."""
    import sys
    sys.path.insert(0, ".")
    from cloudlift_queue_adapter import publish_result

    unique_id = f"test-{time.time_ns()}"
    ok = publish_result(
        doc_id=unique_id,
        chunk_idx=0,
        result={"technical": ["Python", "Django"], "skills": ["leadership"]},
    )
    assert ok, "publish_result returned False"


def test_bus_client_routes_to_sqs_in_aws_mode():
    """Verify bus_client.publish_chunk routes to SQS when CLOUDLIFT_ENV=aws."""
    import sys
    sys.path.insert(0, ".")
    from bus_client import ResumeAnalysisBus

    bus = ResumeAnalysisBus()
    unique_id = f"bus-test-{time.time_ns()}"
    result = bus.publish_chunk(
        doc_id=unique_id,
        chunk_idx=0,
        chunk_text="Test chunk via bus_client SQS bridge",
        context="test",
        extractors=["tech"],
    )
    assert result is True, f"bus_client.publish_chunk returned {result!r} (expected True via SQS bridge)"
