"""Krisp MCP transport: JSON-RPC 2.0 over HTTPS with a bearer token.

The client takes a transport callable rather than importing an HTTP library, so
the protocol is testable without a network. That matters here beyond
convenience: completing a real OAuth flow needs a human at a browser, so a live
account cannot be part of the test suite.

Most of these tests are about the SSE path. An MCP server may answer with either
plain JSON or Server-Sent Events, and a client that handles only one works
against whichever the server happened to send that day.
"""
from __future__ import annotations

import json

import pytest

from iri.ingestion.krisp.mcp_client import KrispMcpClient, McpAuthError, McpError

TOOLS_RESULT = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"tools": [{"name": "search_meetings"}, {"name": "get_multiple_documents"}]},
    }
)
TOOL_NAMES = ["search_meetings", "get_multiple_documents"]


def transport(status: int, body: str, captured: dict | None = None):
    def _transport(url, headers, request_body):
        if captured is not None:
            captured.update(url=url, headers=headers, body=request_body)
        return status, body

    return _transport


# --- the request ------------------------------------------------------------


def test_sends_a_jsonrpc_2_envelope_with_the_bearer_token():
    seen: dict = {}
    KrispMcpClient(transport(200, TOOLS_RESULT, seen), "SECRET").call("tools/list")
    assert json.loads(seen["body"])["jsonrpc"] == "2.0"
    assert "Bearer SECRET" in str(seen["headers"].values())


def test_accept_header_offers_both_response_formats():
    """The server chooses; the client must accept either."""
    seen: dict = {}
    KrispMcpClient(transport(200, TOOLS_RESULT, seen), "t").call("tools/list")
    accept = str(seen["headers"])
    assert "application/json" in accept and "text/event-stream" in accept


def test_request_ids_increment_per_client():
    seen: dict = {}
    client = KrispMcpClient(transport(200, TOOLS_RESULT, seen), "t")
    client.call("a")
    first = json.loads(seen["body"])["id"]
    client.call("b")
    assert json.loads(seen["body"])["id"] == first + 1


# --- response parsing: both formats -----------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        TOOLS_RESULT,                                              # plain JSON
        f"data: {TOOLS_RESULT}\n\n",                               # bare SSE
        f"event: message\ndata: {TOOLS_RESULT}\n\n",               # typical SSE
        f": ping\nevent: message\ndata: {TOOLS_RESULT}\n",         # with a comment
        f"id: 7\nevent: message\ndata: {TOOLS_RESULT}\n\n",        # with an id line
    ],
)
def test_parses_every_response_shape(body):
    """Detecting SSE by the body's FIRST characters fails on all but one of these."""
    assert KrispMcpClient(transport(200, body), "t").list_tools() == TOOL_NAMES


def test_multi_frame_stream_uses_the_final_frame():
    empty = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}})
    body = f"data: {empty}\n\nevent: message\ndata: {TOOLS_RESULT}\n\n"
    assert KrispMcpClient(transport(200, body), "t").list_tools() == TOOL_NAMES


def test_a_server_with_no_tools_is_valid_not_an_error():
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}})
    assert KrispMcpClient(transport(200, body), "t").list_tools() == []


# --- errors -----------------------------------------------------------------


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failures_are_distinguishable(status):
    """The caller refreshes and retries ONCE on this; it must not be a generic error."""
    with pytest.raises(McpAuthError):
        KrispMcpClient(transport(status, "denied"), "t").call("m")


def test_other_http_errors_raise_mcp_error():
    with pytest.raises(McpError):
        KrispMcpClient(transport(500, "x"), "t").call("m")


def test_unparseable_body_raises_rather_than_returning_nothing():
    with pytest.raises(McpError):
        KrispMcpClient(transport(200, "not json, not sse"), "t").call("m")


@pytest.mark.parametrize("status,body", [(500, "BODY-ECHOING-THE-REQUEST"), (200, "BODY-ECHOING-THE-REQUEST")])
def test_exceptions_never_carry_the_body_or_the_token(status, body):
    """A response body may echo request content, which may be evidence text."""
    with pytest.raises(McpError) as exc:
        KrispMcpClient(transport(status, body), "SECRET-TOKEN").call("m")
    assert "BODY-ECHOING-THE-REQUEST" not in str(exc.value)
    assert "SECRET-TOKEN" not in str(exc.value)


def test_jsonrpc_error_is_returned_not_raised():
    """A method-level error is data for the caller, not an exception."""
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "no such method"}}
    )
    assert KrispMcpClient(transport(200, body), "t").call("m").error is not None
