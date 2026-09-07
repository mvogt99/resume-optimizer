"""Blanket LLM blocking, with two documented escape hatches.

llm_helper exposes THREE entry points -- call_llm, call_llm_quality and
call_llm_quality_cached -- plus extract_json. Test files used to hand-patch only
the first, so code paths using the other two reached the real model. Blocking is
therefore central and on by default.
"""

import httpx
import pytest



@pytest.fixture(autouse=True)
def _block_llm_calls(request, monkeypatch) -> None:
    """No test reaches a live model unless it asks to.

    Two escape hatches, and they are NOT interchangeable:

    `llm_required` -- the test drives a genuinely live model. CI deselects it.

    `llm_unit` -- the test exercises llm_helper's OWN routing with the HTTP
    transport already mocked, so it must call the real call_llm_quality and
    reach smart_llm._call_inference beneath it. Blanket-stubbing makes such a
    test assert against THIS FIXTURE'S stub instead of the code under test: the
    stub returns None, _call_inference is never reached, and the failure reads
    "Expected '_call_inference' to have been called" -- which looks like a
    mocking bug in the test rather than a blocked call. Those tests need no live
    model, so they must keep running in CI, which is why llm_required is the
    wrong marker for them.

    Patched on the SOURCE module: callers import these names INSIDE their
    function bodies, so a source-module patch is what they see at call time.
    """
    if "llm_required" in request.keywords or "llm_unit" in request.keywords:
        return

    try:
        import llm_helper
    except ImportError:
        return

    def _blocked(*args, **kwargs):
        return None

    monkeypatch.setattr(llm_helper, "call_llm", _blocked)
    monkeypatch.setattr(llm_helper, "call_llm_quality", _blocked)
    monkeypatch.setattr(llm_helper, "call_llm_quality_cached", _blocked)
    monkeypatch.setattr(llm_helper, "extract_json", _blocked)

@pytest.fixture(autouse=True)
def _block_gateway_transport(request, monkeypatch) -> None:
    """Make it impossible to reach the live gateway or model server over HTTP.

    _block_llm_calls is not enough: several modules bind the llm_helper names at
    IMPORT time, and smart_llm reaches the network by its own path entirely --
    a module-level `_http_client` used by call_harness, model selection and
    _call_inference.

    The symptom is a HANG, not a failure. smart_llm's HARNESS_TIMEOUT is 300s
    and SWAP_TIMEOUT is 660s, both far longer than the suite's 120s per-test
    timeout, and the blocking poll happens inside a C call where the timeout
    signal cannot interrupt promptly. A full local sweep stalled at 9% with the
    main thread parked in do_sys_poll on an established connection to port 8000.

    Raising rather than returning a fake response is deliberate: a silent fake
    would let a test assert against invented data, which is the exact failure
    this suite has suffered repeatedly. Mark llm_required or integration to opt
    back in.
    """
    if "llm_required" in request.keywords or "integration" in request.keywords:
        return

    try:
        import smart_llm
    except ImportError:
        return

    class _BlockedHttpClient:
        """Explicit stand-in, not a MagicMock: it states exactly what it does.

        Raises httpx.ConnectError, which is what this situation actually IS from
        the caller's point of view: the gateway is not reachable from a test.
        Using the accurate exception means every retry loop already handles it
        correctly -- including smart_llm's swap poll, which now fails fast on a
        connection error instead of sleeping through SWAP_TIMEOUT (660s).

        A BaseException was tried first so that `except Exception: pass` could
        not swallow it. That broke 21 tests which legitimately tolerate a failed
        LLM call, and it was the wrong tool: the goal is an honest failure, not
        an uncatchable one.
        """

        def _blocked(self, verb):
            raise httpx.ConnectError(
                f"_block_gateway_transport: this test tried to {verb} the live "
                "gateway. Mark it llm_required or integration if that is intended."
            )

        def post(self, *args, **kwargs):
            self._blocked("POST to")

        def get(self, *args, **kwargs):
            self._blocked("GET from")

    monkeypatch.setattr(smart_llm, "_http_client", _BlockedHttpClient())
