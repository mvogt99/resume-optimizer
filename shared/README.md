# shared

Shared Python package for type-safe event schemas and utilities.

## Purpose

Provides dataclass models for inter-service communication:
- ResumeUploadedEvent — fired when resume lands in S3
- AnalysisRequestedEvent — submitted by API, consumed by workers
- AnalysisCompleteEvent — published by workers, stored for audit trail

## Usage

```python
from shared.events import AnalysisRequestedEvent

event = AnalysisRequestedEvent(
    resume_id="uuid",
    user_id="user123",
    job_description="...",
    task_type="resume_analysis"
)
sqs_body = event.to_sqs_message()  # JSON string
```
