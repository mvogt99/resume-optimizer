from __future__ import annotations
import json
from dataclasses import dataclass
from iri.ingestion.krisp.oauth import KRISP_MCP_URL

# This inversion of control by using a transport callable allows the protocol to be tested
# without a live account, since completing a real OAuth flow needs a human at a browser.
# NEVER log or embed the access token, and never put a response body into an exception message.

class McpError(Exception):
    """Base class for MCP errors."""
    pass

class McpAuthError(McpError):
    """Authentication error. The token is missing, expired, or rejected. The caller
    should refresh and retry ONCE, not loop."""
    pass

@dataclass(frozen=True)
class McpResponse:
    id: int
    result: dict | None
    error: dict | None

class KrispMcpClient:
    def __init__(self, transport, access_token: str, url: str = KRISP_MCP_URL):
        self.transport = transport
        self.access_token = access_token
        self.url = url
        self._request_id = 0

    def call(self, method: str, params: dict | None = None) -> McpResponse:
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {}
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        status, body = self.transport(self.url, headers, json.dumps(request))
        
        if status in (401, 403):
            raise McpAuthError()
        if not (200 <= status < 300):
            raise McpError(f"HTTP {status}")

        # Check for Server-Sent Events (SSE)
        lines = body.splitlines()
        data_lines = [line.split("data: ")[1] for line in lines if line.startswith("data: ")]
        if data_lines:
            body = data_lines[-1]  # Use the last data line

        try:
            response = json.loads(body)
        except json.JSONDecodeError:
            raise McpError("Invalid JSON response")

        if "error" in response:
            if response["error"].get("code") == -32000:  # Assuming -32000 is the auth error code
                raise McpAuthError()
            return McpResponse(id=response["id"], result=None, error=response["error"])
        return McpResponse(id=response["id"], result=response["result"], error=None)

    def list_tools(self) -> list[str]:
        response = self.call("tools/list")
        tools = response.result.get("tools", [])
        return [tool["name"] for tool in tools]

    def call_tool(self, name: str, arguments: dict) -> dict:
        response = self.call("tools/call", {"name": name, "arguments": arguments})
        if response.error:
            raise McpError(response.error)
        return response.result
