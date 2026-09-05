from __future__ import annotations
import json
from datetime import datetime, timezone
from iri.contracts.evidence_source import ConnectionState, EvidenceKind, RawEvidence, SourceHealth
from iri.ingestion.krisp.mcp_client import KrispMcpClient, McpAuthError, McpError
from iri.ingestion.krisp.token_store import KrispTokenStore, needs_refresh


class KrispEvidenceSource:
    def __init__(self, token_store: KrispTokenStore, transport):
        self.token_store = token_store
        self.transport = transport

    @property
    def name(self) -> str:
        return "krisp"

    def health(self, user_id: str) -> SourceHealth:
        tokens = self.token_store.load()
        if not tokens:
            return SourceHealth(connected=False, reason="not connected", checked_at=datetime.now(timezone.utc))
        if needs_refresh(tokens, datetime.now(timezone.utc)):
            return SourceHealth(connected=False, reason="token expired", checked_at=datetime.now(timezone.utc))
        try:
            client = KrispMcpClient(self.transport, tokens.access_token)
            client.list_tools()
            return SourceHealth(connected=True, reason="connected", checked_at=datetime.now(timezone.utc))
        except McpError as e:
            return SourceHealth(connected=False, reason=str(e), checked_at=datetime.now(timezone.utc))

    def fetch_since(self, user_id: str, cursor: str | None, limit: int) -> (list[RawEvidence], str | None):
        tokens = self.token_store.load()
        if not tokens:
            raise McpAuthError("No tokens stored")
        if needs_refresh(tokens, datetime.now(timezone.utc)):
            raise McpAuthError("Token needs refresh")

        client = KrispMcpClient(self.transport, tokens.access_token)
        search_params = {
            "after": cursor,
            "limit": limit,
            "fields": ["name", "date", "duration_seconds", "attendees", "speakers"]
        }
        meetings = client.call_tool("search_meetings", search_params)["structuredContent"]["meetings"]

        raw_evidence_list = []
        for meeting in meetings:
            meeting_id = meeting["meeting_id"]
            transcript_ids = [meeting_id]  # Assuming each meeting has one transcript
            documents = client.call_tool("get_multiple_documents", {"ids": transcript_ids, "include": ["transcript"], "format": "json"})["structuredContent"]["results"]
            transcript_text = self._extract_transcript(documents)

            if transcript_text is not None:
                occurred_at = datetime.fromisoformat(meeting["date"])
                raw_evidence = RawEvidence(
                    source_id=meeting_id,
                    kind=EvidenceKind.TRANSCRIPT,
                    occurred_at=occurred_at,
                    fetched_at=datetime.now(timezone.utc),
                    title=meeting.get("name",""),
                    body=transcript_text,
                    participants=meeting.get("attendees", []),
                    metadata={
                        "duration_seconds": str(meeting.get("duration_seconds")),
                        "meeting_id": meeting_id
                    }
                )
                raw_evidence_list.append(raw_evidence)

        next_cursor = max((meeting["date"] for meeting in meetings), default=None)
        return raw_evidence_list, next_cursor

    def authorize_url(self, *args, **kwargs):
        raise NotImplementedError("Authorization handshake belongs in backend/iri/routes/krisp_routes.py")

    def complete_authorization(self, *args, **kwargs):
        raise NotImplementedError("Authorization handshake belongs in backend/iri/routes/krisp_routes.py")

    def refresh(self, *args, **kwargs):
        raise NotImplementedError("Authorization handshake belongs in backend/iri/routes/krisp_routes.py")

    def revoke(self, *args, **kwargs):
        raise NotImplementedError("Authorization handshake belongs in backend/iri/routes/krisp_routes.py")

    def _extract_transcript(self, documents: list) -> str | None:
        for document in documents:
            if "transcript" in document["document"]:
                return document["document"]["transcript"]
        return None
