"""
Chunk consumer for parallel document analysis via Artemis message bus.
Subscribes to resume.analysis.chunks, runs requested extractors, publishes results.

Can run standalone (`python analysis_worker.py`) or be used inline via `handle_chunk()`.
"""

import json
import os
import time

import stomp

CHUNKS_QUEUE = "/queue/resume.analysis.chunks"
RESULTS_QUEUE = "/queue/resume.analysis.results"
ARTEMIS_HOST = os.environ.get("ARTEMIS_HOST", "localhost")
ARTEMIS_PORT = int(os.environ.get("ARTEMIS_PORT", "61613"))
ARTEMIS_USER = os.environ.get("ARTEMIS_USER", "artemis")
ARTEMIS_PASS = os.environ.get("ARTEMIS_PASS", "artemis")

# Extractors are imported lazily to avoid import failures when used as a library
_extractors = {}


def _get_extractor(name):
    """Lazy-load extractor functions to avoid circular imports."""
    if name not in _extractors:
        if name == "tech":
            from technical_extractor import extract_technical_picture

            _extractors["tech"] = extract_technical_picture
        elif name == "gov":
            from governance_extractor import extract_governance_picture

            _extractors["gov"] = extract_governance_picture
        elif name == "role":
            from role_extractor import extract_role_picture

            _extractors["role"] = extract_role_picture
        elif name == "skills":
            from skills_extractor import extract_all_skills

            _extractors["skills"] = extract_all_skills
        elif name == "outcomes":
            from business_outcomes_extractor import extract_business_outcomes

            _extractors["outcomes"] = extract_business_outcomes
    return _extractors.get(name)


# Map extractor short names to result keys
_EXTRACTOR_KEYS = {
    "tech": "technical",
    "gov": "governance",
    "role": "role",
    "skills": "skills",
    "outcomes": "outcomes",
}


def handle_chunk(payload):
    """Process a single chunk through requested extractors.

    Args:
        payload: dict with doc_id, chunk_idx, chunk_text, context, extractors

    Returns:
        dict with doc_id, chunk_idx, and extraction results per field
    """
    doc_id = payload["doc_id"]
    chunk_idx = payload["chunk_idx"]
    text = payload["chunk_text"]
    context = payload.get("context", "")
    extractors = payload.get("extractors", ["tech", "gov", "role"])

    result = {
        "doc_id": doc_id,
        "chunk_idx": chunk_idx,
        "technical": [],
        "governance": [],
        "role": [],
        "skills": [],
        "outcomes": [],
    }

    for ext_name in extractors:
        result_key = _EXTRACTOR_KEYS.get(ext_name, ext_name)
        fn = _get_extractor(ext_name)
        if fn is None:
            print(f"[analysis_worker] Unknown extractor: {ext_name}")
            continue
        try:
            result[result_key] = fn(text, context_summary=context)
        except Exception as e:
            print(
                f"[analysis_worker] {ext_name} extractor failed on "
                f"doc={doc_id} chunk={chunk_idx}: {e}"
            )
            result[result_key] = []

    return result


class _WorkerListener(stomp.ConnectionListener):
    """STOMP listener that processes chunks and publishes results."""

    def __init__(self, connection):
        self._connection = connection

    def on_message(self, frame):
        try:
            body = frame.body if hasattr(frame, "body") else frame
            payload = json.loads(body)
            print(
                f"[analysis_worker] Processing doc={payload['doc_id']} "
                f"chunk={payload['chunk_idx']}"
            )
            result = handle_chunk(payload)
            self._connection.send(
                destination=RESULTS_QUEUE,
                body=json.dumps(result),
                headers={"persistent": "true", "content-type": "application/json"},
            )
        except Exception as e:
            print(f"[analysis_worker] Error processing message: {e}")


def start_worker():
    """Connect to Artemis, subscribe to chunks queue, and block processing messages."""
    conn = stomp.Connection([(ARTEMIS_HOST, ARTEMIS_PORT)])
    listener = _WorkerListener(conn)
    conn.set_listener("worker", listener)
    conn.connect(ARTEMIS_USER, ARTEMIS_PASS, wait=True)
    conn.subscribe(destination=CHUNKS_QUEUE, id="analysis-worker-1", ack="auto")
    print(f"[analysis_worker] Subscribed to {CHUNKS_QUEUE}, waiting for messages...")

    try:
        while conn.is_connected():
            time.sleep(1)
    except KeyboardInterrupt:
        print("[analysis_worker] Shutting down...")
    finally:
        conn.disconnect()


def run_sqs_worker(poll_wait: int = 20) -> None:
    """SQS worker loop — replaces Artemis listener in CLOUDLIFT_ENV=aws.

    Long-polls the chunks FIFO queue, processes each message via handle_chunk(),
    publishes results to the results queue, then deletes the source message.
    Runs until interrupted.
    """
    from cloudlift_queue_adapter import receive_chunks, delete_message, publish_result  # noqa: PLC0415

    print("[analysis_worker] SQS mode — polling ro-test-analysis-chunks.fifo")
    while True:
        try:
            messages = receive_chunks(max_messages=10, wait_seconds=poll_wait)
            for msg in messages:
                payload = msg["body"]
                doc_id = payload.get("doc_id", "unknown")
                chunk_idx = payload.get("chunk_idx", 0)
                print(f"[analysis_worker] SQS doc={doc_id} chunk={chunk_idx}")
                try:
                    result = handle_chunk(payload)
                    publish_result(doc_id, chunk_idx, result)
                    delete_message(msg["receipt_handle"])
                except Exception as exc:
                    print(f"[analysis_worker] SQS processing failed: {exc}")
        except KeyboardInterrupt:
            print("[analysis_worker] SQS worker shutting down...")
            break
        except Exception as exc:
            print(f"[analysis_worker] SQS poll error: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    if os.environ.get("CLOUDLIFT_ENV") == "aws":
        run_sqs_worker()
    else:
        start_worker()
