# S0.6 — Redaction Gateway Specification

> **Date:** 2026-09-05 · **Status:** Specification, ready for implementation
> **Implements:** DD-15 (trust boundary), DD-03 (deterministic pseudonymisation + identity vault), P-3 (amended), REQ-406/407/482
> **Plan ref:** `PLAN_Interview_Rejection_Intelligence_2026-09-04.md` S0.6
> Written without GPU access; executable code is delegated separately.

---

## 1. What this is

**One choke point. No model call in IRI is reachable except through it.** Not a helper, not a convention — a structural constraint. If a second path to a model exists, the privacy posture is whatever that second path does, and every guarantee below is decorative.

The gateway owns four things: **destination classification**, **redaction**, **cost and quota**, and **the model-call log**.

---

## 2. ⚠ The finding that changes this component's priority

DD-15 places the user's own GPU **inside** the trust boundary — self-hosted models may see unredacted evidence — and everything outside it **outside**, where redaction is mandatory and fails closed.

**The FTAL harness, which IRI's `ILLMInference` path reaches, has a silent local→cloud fallback.** Observed directly during a failed delegation on 2026-09-04:

```
Primary (http://localhost:8021/v1): All connection attempts failed;
Cloud (Haiku): All connection attempts failed
```

It only failed at the second hop because cloud was also unreachable. Had cloud been reachable, the call would have gone to a third-party API.

**Traced and corrected 2026-09-05 — it is worse than first written.** My initial note cited `model_router.select_model_with_fallback`'s `fallback_to_cloud=False` default as a gate. That was a **red herring**: that function only returns a recommendation string and its sole caller is a demo `main()`. It routes nothing.

The real path is `agent_task_queue_execution.py` ~line 585. On primary vLLM failure it tries a local fallback endpoint; if that also fails — or if primary and fallback are the same endpoint — it proceeds straight to:

```python
if result_text is None:
    try:
        backend = get_ai_backend()
        _cloud_model = "claude-haiku-4-5-20251001"
        cloud_result = await backend.chat(messages=messages, ...)
        endpoint_used = "cloud:claude-haiku"
```

**There is no flag, no config check, and no opt-in.** The cross-boundary hop is unconditional. This changes the character of the problem from "check the configuration" to "there is no configuration to check."

**One thing is better than first written:** the destination *is* recorded distinctly — `endpoint_used = "cloud:claude-haiku"` plus a warning log. So "did anything leave this machine?" **is** answerable after the fact on this path, by filtering `endpoint_used LIKE 'cloud:%'`. IRI does not need to build that logging; it needs to not depend on the path.

**The trigger condition is not rare.** The RTX 5090 fell off the PCIe bus **three times on 2026-09-04**, twice within ~20 minutes of boot. Local inference being unavailable is a routine operating state on this machine, not an edge case.

So the failure mode is concrete: the local model dies mid-analysis, a fallback fires, and an **unredacted interview transcript** — real names, employers, interviewer identities, rejection reasons, compensation figures — is sent to an external API. Under DD-15 that is not a degraded result. It is a privacy breach caused by an availability event.

### The rule this forces

**An availability failure must never silently downgrade the privacy posture.**

- The gateway **classifies by actual destination**, never by intent or configuration. "We meant to use the local model" is not a fact about where the bytes went — and on the harness path there is no configuration expressing that intent in the first place.
- **Fallback across the trust boundary is forbidden by default.** If the local model is unavailable, the correct behaviour is to **fail the analysis and leave it retryable** — not to complete it elsewhere.
- If cross-boundary fallback is ever enabled deliberately, it **must redact first**, and it must be an explicit per-request opt-in, never a default or a global setting.
- IRI must not delegate destination selection to a component that can reroute underneath it. Either the gateway pins the endpoint, or it treats the harness as an untrusted-destination caller and redacts unconditionally.

This is the single highest-risk item in S0 and should be built before any analyser exists to call it.

---

## 3. Destination classification

| Class | Examples | Redaction |
|---|---|---|
| **Inside boundary** | vLLM on the local RTX 5090 (`localhost:8021`) | Not required (DD-15) |
| **Outside boundary** | Azure OpenAI, Bedrock, Anthropic API, any hosted endpoint | **Mandatory, fail-closed** |
| **Unknown** | Anything not positively identified as inside | **Treated as outside** |

Default-deny: an unrecognised destination is *outside*. A misconfiguration must produce over-redaction, never under-redaction.

Classification is on the **resolved endpoint at call time**, after any routing.

---

## 4. Redaction and the identity vault (DD-03)

- **Deterministic pseudonymisation**, not deletion. The same real entity maps to the same pseudonym across every document and session, or cross-stage correlation (§10 CrossStageContext) becomes impossible.
- The mapping lives in the **identity vault**, stored via `ISecretStore` and never sent anywhere.
- **Fail closed on low confidence.** If entity detection is not confident a span is safe, redact it. A degraded analysis is recoverable; a leaked name is not.
- **Outbound vault scan** before any cross-boundary call: if a raw value from the vault appears in the payload, block the call. This catches redaction misses that entity detection alone would not.
- Redaction is **bounded and recorded, not eliminated** — design §9.2 says so plainly, and this spec does not claim otherwise.

**Parity note (DD-15 consequence):** the parity suite must **force-enable redaction in `local`**, so all three environments compare on equivalent input. Otherwise `local` analyses richer text than `azure` and structural equivalence is meaningless.

---

## 5. Cost, quota, logging

Every call, regardless of destination, records: timestamp, tenant, destination class, resolved endpoint, model id, token counts, latency, outcome, and **redaction state**.

**Redaction state is an enum, never a boolean.** This is a correction (2026-09-05): the field was originally specified as "whether redaction was applied," which catches *redaction did not run* but silently passes *redaction ran and partially succeeded* — the more dangerous of the two.

| State | Meaning |
|---|---|
| `NOT_REQUIRED` | Destination classified inside the trust boundary (DD-15) |
| `COMPLETE` | Every detector ran, every detected span replaced, outbound vault scan clean |
| `PARTIAL` | A detector errored, timed out, or returned low confidence on a span |
| `FAILED` | Redaction could not be attempted |

**`PARTIAL` on an outside-boundary call blocks the call.** It is not a warning and not a degraded success. A partially-redacted transcript is exactly the artifact that looks safe in a log and is not — the boolean would have recorded it as `redacted=true`.

*Credit where due:* this class of defect was surfaced by hybrid-ai-windows-45 in their PSU telemetry on 2026-09-04 — a blank-guard that only fired when **all six** fields were missing, so a partial sensor read passed labelled `OK` and rendered as a fabricated 0 V rail collapse, pointed straight at the hypothesis under test. Same shape, different domain: **a status field that only catches total failure will silently pass the partial one, and the partial one is worse because it is credible.**

- **Quota is enforced before the call, not after.** DD-16's ~100-user ceiling and the harness's variable latency make an after-the-fact counter useless as a control.
- Cost attribution is **per tenant** — required for any future multi-user operation, and cheap to add now versus retrofitting.
- **The log records the destination class of every call.** This is the audit artifact that answers "did anything unredacted ever leave this machine?" — a question that cannot be reconstructed later if it is not recorded at the time.
- The log must never contain prompt or completion text. Counts and identifiers only.

---

## 6. Test obligations

Each gets an explicit **negative** test proving fail-closed behaviour (REQ-593):

1. Unknown destination → classified outside → redacted.
2. Local endpoint unavailable → analysis **fails and is retryable**; no cross-boundary call is made.
3. Low-confidence entity detection → span redacted, not passed.
3b. **Partial redaction on an outside-boundary call → call blocked**, state recorded as `PARTIAL`. A detector that errors or times out must not yield a `COMPLETE` record.
4. Vault value present in outbound payload → call **blocked**.
5. Quota exhausted → call refused **before** dispatch.
6. Redaction forced on in `local` → output structurally comparable to `azure`.
7. No model call path exists that bypasses the gateway — asserted by import-graph inspection, not by convention.

Test 2 is the one that would have caught today's fallback, and test 7 is the one that keeps the whole component honest.

---

## 7. Open item

Whether IRI pins its own endpoint or routes through the FTAL harness is **not yet decided**, and §2 makes it consequential. Pinning gives IRI control of destination but forfeits the harness's model management and F/T/A/L scoring. Routing through the harness keeps those but means IRI cannot guarantee where a call lands — in which case the only safe posture is to redact unconditionally, treating even local inference as outside the boundary, which discards the benefit DD-15 was written to capture.

**RESOLVED 2026-09-05 — pin the endpoint.** Confirmed with the harness maintainer (hybrid-ai-windows-45): nothing on their side breaks if IRI bypasses the harness for analysis calls, and they concur with the decision. Routing evidence through a component whose documented failure mode is an unconditional hop to Anthropic is not a risk worth carrying for convenience, particularly when local inference has been unavailable repeatedly.

**Decision (DD-25):** IRI pins its own `ILLMInference` endpoint for all analysis calls. **Implemented 2026-09-05 at zero code cost** — `LocalVLLMAdapter` already posts directly to `localhost:8021` and raises `AdapterError` with no fallback path, so DD-09 delivers this by construction. Enforcement is the deliverable: `backend/tests/test_iri_llm_endpoint_pinning.py` (5 checks, verified to fail on an injected violation). The FTAL harness continues to be used for **code generation**, where the trust boundary does not apply and the F/T/A/L scoring is worth having.

A per-call "must not leave this host" opt-in has been proposed to the harness maintainer and is on their debt ledger. IRI must not depend on it existing.
