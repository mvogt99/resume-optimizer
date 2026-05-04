"""Shared event schemas for resume-optimizer services.

Used by both resume-optimizer-api (publishers) and
resume-optimizer-workers (consumers) to ensure consistent
SQS message formats.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import time


@dataclass
class ResumeUploadedEvent:
    resume_id: str
    user_id: str
    s3_key: str
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_sqs_message(self) -> str:
        return json.dumps({"event": "resume_uploaded", **asdict(self)})


@dataclass
class AnalysisRequestedEvent:
    resume_id: str
    user_id: str
    job_description: str
    task_type: str = "resume_analysis"
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_sqs_message(self) -> str:
        return json.dumps({"event": "analysis_requested", **asdict(self)})


@dataclass
class AnalysisCompleteEvent:
    resume_id: str
    user_id: str
    result_s3_key: str
    score: float
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_sqs_message(self) -> str:
        return json.dumps({"event": "analysis_complete", **asdict(self)})
