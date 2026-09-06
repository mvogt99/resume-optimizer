"""Blanket LLM blocking, with two documented escape hatches.

llm_helper exposes THREE entry points -- call_llm, call_llm_quality and
call_llm_quality_cached -- plus extract_json. Test files used to hand-patch only
the first, so code paths using the other two reached the real model. Blocking is
therefore central and on by default.
"""

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
