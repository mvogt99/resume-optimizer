"""S0.6 test 7 — no IRI analysis path may reach the FTAL harness.

DD-15 places the local GPU inside the trust boundary and every hosted
endpoint outside it. The harness violates that boundary unconditionally:
`agent_task_queue_execution.py` routes to claude-haiku on local failure with
no flag, no config check and no opt-in.

CloudLift's LocalVLLMAdapter does not: it posts directly to localhost:8021
and raises AdapterError on failure. So the pin is structural — IRI gets the
right behaviour by consuming cloudlift.bridge (DD-09) and NOT calling the
harness.

Structural guarantees decay silently. This file is the ratchet: it fails the
moment someone reintroduces a harness call into an IRI analysis path,
including by importing a module that makes one.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

IRI_ROOT = Path(__file__).resolve().parent.parent / "iri"

# Modules in this repo that reach the FTAL harness, directly or transitively.
HARNESS_MODULES = {"smart_llm", "llm_helper", "experience_chat"}

# Substrings that indicate a harness call site.
HARNESS_MARKERS = (
    "api/harness/run",
    "localhost:8000",
    "delegate_task",
    "delegate_and_apply",
)

# Hosted-inference markers. IRI may reference these ONLY through a CloudLift
# adapter, never by calling a provider SDK from its own analysis code.
CLOUD_MARKERS = ("anthropic", "claude-haiku", "bedrock-runtime", "openai.ChatCompletion")


def _iri_python_files() -> list[Path]:
    if not IRI_ROOT.exists():
        pytest.skip("backend/iri not present")
    return sorted(p for p in IRI_ROOT.rglob("*.py") if "__pycache__" not in str(p))


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_iri_never_imports_a_harness_module():
    offenders = [
        (p.relative_to(IRI_ROOT), sorted(_imported_names(p) & HARNESS_MODULES))
        for p in _iri_python_files()
        if _imported_names(p) & HARNESS_MODULES
    ]
    assert not offenders, (
        "IRI must not import harness-backed modules — the harness falls back "
        f"to claude-haiku unconditionally on local failure. Offenders: {offenders}"
    )


def test_iri_contains_no_harness_call_sites():
    offenders = []
    for p in _iri_python_files():
        text = p.read_text()
        hits = [m for m in HARNESS_MARKERS if m in text]
        if hits:
            offenders.append((str(p.relative_to(IRI_ROOT)), hits))
    assert not offenders, f"Harness call sites found in IRI: {offenders}"


def test_iri_does_not_call_hosted_providers_directly():
    """Hosted inference is reachable only through a CloudLift adapter."""
    offenders = []
    for p in _iri_python_files():
        if "adapters" in p.parts:
            continue  # adapters are the sanctioned provider boundary
        text = p.read_text().lower()
        hits = [m for m in CLOUD_MARKERS if m.lower() in text]
        if hits:
            offenders.append((str(p.relative_to(IRI_ROOT)), hits))
    assert not offenders, (
        f"IRI analysis code calls a hosted provider directly: {offenders}"
    )


def test_local_llm_adapter_has_no_fallback_path():
    """The pin only holds because the adapter fails instead of rerouting.

    If CloudLift ever adds a cloud fallback to LocalVLLMAdapter, DD-15's
    trust boundary silently stops holding and this test is the alarm.
    """
    from cloudlift.bridge.local import vllm_adapter

    source = Path(vllm_adapter.__file__).read_text().lower()
    for marker in ("anthropic", "bedrock", "claude-haiku", "azure openai"):
        assert marker not in source, (
            f"LocalVLLMAdapter now references {marker!r} — verify it cannot "
            "reroute off-host before trusting DD-15."
        )


def test_local_llm_adapter_targets_localhost():
    import inspect

    from cloudlift.bridge.local.vllm_adapter import LocalVLLMAdapter

    default = inspect.signature(LocalVLLMAdapter.__init__).parameters["base_url"].default
    assert "localhost" in default or "127.0.0.1" in default, (
        f"LocalVLLMAdapter default base_url is {default!r}, not a loopback address"
    )
