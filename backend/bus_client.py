"""
Artemis STOMP client for parallel document analysis.
Flask is sync; stomp.py handles threading internally via its listener pattern.
Publish chunks → collect results via separate thread-safe queues.
Graceful degradation: if Artemis unreachable, is_available() returns False
and callers fall back to sequential processing.
"""

import contextlib
import json
import os
import queue
import threading
import time

import stomp

CHUNKS_QUEUE = "/queue/resume.analysis.chunks"
RESULTS_QUEUE = "/queue/resume.analysis.results"
ARTEMIS_HOST = os.environ.get("ARTEMIS_HOST", "localhost")
ARTEMIS_PORT = int(os.environ.get("ARTEMIS_PORT", "61613"))
ARTEMIS_USER = os.environ.get("ARTEMIS_USER", "artemis")
ARTEMIS_PASS = os.environ.get("ARTEMIS_PASS", "artemis")


class _ResultListener(stomp.ConnectionListener):
    """Listener that collects analysis results into a thread-safe queue."""

    def __init__(self, result_queue):
        self._result_queue = result_queue

    def on_message(self, frame):
        try:
            body = frame.body if hasattr(frame, "body") else frame
            data = json.loads(body)
            self._result_queue.put(data)
        except (json.JSONDecodeError, AttributeError):
            pass


class _ChunkWorkerListener(stomp.ConnectionListener):
    """Listener that processes chunks and publishes results to the results queue."""

    def __init__(self, worker_conn):
        self._worker_conn = worker_conn

    def on_message(self, frame):
        try:
            from analysis_worker import handle_chunk

            body = frame.body if hasattr(frame, "body") else frame
            payload = json.loads(body)
            print(
                f"[bus_worker] Processing doc={payload['doc_id']} " f"chunk={payload['chunk_idx']}"
            )
            result = handle_chunk(payload)
            self._worker_conn.send(
                destination=RESULTS_QUEUE,
                body=json.dumps(result),
                headers={"persistent": "true", "content-type": "application/json"},
            )
        except Exception as e:
            print(f"[bus_worker] Error processing chunk: {e}")


class ResumeAnalysisBus:
    """STOMP client for parallel document chunk analysis via Artemis."""

    def __init__(self):
        self._connection = None  # publisher + result collector
        self._worker_conn = None  # chunk consumer
        self._connected = False
        self._result_queue = queue.Queue()
        self._lock = threading.Lock()
        self._try_connect()

    def _try_connect(self):
        """Attempt connection to Artemis. Non-fatal on failure."""
        try:
            # Connection 1: publish chunks + collect results
            conn = stomp.Connection([(ARTEMIS_HOST, ARTEMIS_PORT)])
            conn.set_listener("results", _ResultListener(self._result_queue))
            conn.connect(ARTEMIS_USER, ARTEMIS_PASS, wait=True)
            conn.subscribe(destination=RESULTS_QUEUE, id="ro-results", ack="auto")
            self._connection = conn

            # Connection 2: consume chunks + process via handle_chunk
            worker = stomp.Connection([(ARTEMIS_HOST, ARTEMIS_PORT)])
            worker.set_listener("worker", _ChunkWorkerListener(worker))
            worker.connect(ARTEMIS_USER, ARTEMIS_PASS, wait=True)
            worker.subscribe(destination=CHUNKS_QUEUE, id="ro-worker", ack="auto")
            self._worker_conn = worker

            self._connected = True
            print(
                f"[bus_client] Connected to Artemis at {ARTEMIS_HOST}:{ARTEMIS_PORT} "
                f"(publisher + worker)"
            )
        except Exception as e:
            print(f"[bus_client] Artemis unavailable, bus disabled: {e}")
            self._connected = False

    def is_available(self):
        """True if STOMP connection is live."""
        return self._connected and self._connection is not None

    def publish_chunk(self, doc_id, chunk_idx, chunk_text, context, extractors):
        """Publish a document chunk for analysis. Thread-safe (stomp.py send is safe)."""
        if not self.is_available():
            return False
        msg = json.dumps(
            {
                "doc_id": doc_id,
                "chunk_idx": chunk_idx,
                "chunk_text": chunk_text,
                "context": context,
                "extractors": extractors,
            }
        )
        try:
            self._connection.send(
                destination=CHUNKS_QUEUE,
                body=msg,
                headers={"persistent": "true", "content-type": "application/json"},
            )
            return True
        except Exception as e:
            print(f"[bus_client] Publish failed: {e}")
            self._connected = False
            return False

    def collect_results(self, expected_count, timeout=300):
        """Block until expected_count results arrive or timeout. Returns list of result dicts."""
        results = []
        deadline = time.time() + timeout
        while len(results) < expected_count and time.time() < deadline:
            try:
                remaining = max(0.1, deadline - time.time())
                item = self._result_queue.get(timeout=min(remaining, 2.0))
                results.append(item)
            except queue.Empty:
                continue
        return results

    def drain_results(self):
        """Drain any leftover results from the queue (call before a new batch)."""
        drained = 0
        while True:
            try:
                self._result_queue.get_nowait()
                drained += 1
            except queue.Empty:
                break
        if drained:
            print(f"[bus_client] Drained {drained} stale results")

    def stop(self):
        """Disconnect cleanly."""
        for conn in (self._connection, self._worker_conn):
            if conn:
                with contextlib.suppress(Exception):
                    conn.disconnect()
        self._connected = False


# Singleton
_bus = None
_bus_lock = threading.Lock()


def get_analysis_bus():
    """Get or create the singleton ResumeAnalysisBus."""
    global _bus
    with _bus_lock:
        if _bus is None:
            _bus = ResumeAnalysisBus()
        return _bus
