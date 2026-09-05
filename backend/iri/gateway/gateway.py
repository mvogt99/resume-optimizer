"""
The single choke point every model call in this subsystem passes through. It classifies the destination,
applies redaction when required, enforces a per-tenant quota, and writes an audit record — in that order,
before any text leaves the process. No model call in this subsystem may be reachable except through this class,
and a second path to a model makes every guarantee here decorative.
"""

from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

from iri.gateway.types import DestinationClass, ModelCallRecord, RedactionState, is_redaction_required
from iri.gateway.classifier import classify_endpoint
from iri.gateway.redactor import IRedactor, NullRedactor, RedactionResult


class GatewayError(Exception):
    """Base class for all gateway-related errors."""
    pass


class RedactionRequiredError(GatewayError):
    """The call was blocked because redaction did not reach a safe state."""
    pass


class QuotaExceededError(GatewayError):
    """The tenant's budget for this window is spent."""
    pass


class ModelGateway:
    def __init__(self, redactor: IRedactor, audit_sink: Callable[[ModelCallRecord], None], quota: Optional[int] = None):
        self.redactor = redactor
        self.audit_sink = audit_sink
        self.quota = quota
        self.tenant_call_count = {}

    def invoke(self, tenant_id: UUID, endpoint: str, model_id: str, prompt: str,
               call: Callable[[str], str]) -> str:
        from uuid import uuid4

        # Generate a unique call_id for this invocation
        call_id = str(uuid4())

        # Classify the endpoint
        destination_class = classify_endpoint(endpoint)

        # Record the start time for latency calculation
        start_time = datetime.now(timezone.utc)

        def create_audit_record(success: bool, completion_token_count: int, redaction_state: RedactionState) -> ModelCallRecord:
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return ModelCallRecord(
                call_id=call_id,
                tenant_id=tenant_id,
                timestamp=datetime.now(timezone.utc),
                destination_class=destination_class,
                resolved_endpoint=endpoint,
                model_id=model_id,
                prompt_token_count=len(prompt.split()),  # Approximate token count
                completion_token_count=completion_token_count,
                latency_ms=latency_ms,
                success=success,
                redaction_state=redaction_state
            )

        # Enforce quota
        if self.quota is not None:
            current_count = self.tenant_call_count.get(tenant_id, 0)
            if current_count >= self.quota:
                record = create_audit_record(success=False, completion_token_count=0, redaction_state=RedactionState.FAILED)
                self._record_audit(record)
                raise QuotaExceededError("Tenant quota exceeded.")
            self.tenant_call_count[tenant_id] = current_count + 1

        # Apply redaction if required
        redaction_required = is_redaction_required(destination_class)
        if redaction_required:
            result = self.redactor.redact(prompt)
            if not result.is_safe_to_send:
                # Record the audit before raising the error
                record = create_audit_record(success=False, completion_token_count=0, redaction_state=result.state)
                self._record_audit(record)
                raise RedactionRequiredError(f"Redaction required but not safe to send. State: {result.state}, Reason: {result.reason}")
            safe_text = result.text
            redaction_state = result.state
        else:
            safe_text = prompt
            redaction_state = RedactionState.NOT_REQUIRED

        # Invoke the model call
        try:
            completion = call(safe_text)
            completion_token_count = len(completion.split())  # Approximate token count
            success = True
        except Exception as e:
            completion_token_count = 0  # Not applicable for failed calls
            success = False
            raise e
        finally:
            # Write audit record
            record = create_audit_record(success=success, completion_token_count=completion_token_count, redaction_state=redaction_state)
            self._record_audit(record)

        return completion

    def _record_audit(self, record: ModelCallRecord):
        try:
            self.audit_sink(record)
        except Exception as e:
            # If the audit sink raises, re-raise the exception to ensure the original outcome is not silently swallowed.
            # This decision is based on the critical nature of audit records in maintaining a complete audit trail.
            raise e
