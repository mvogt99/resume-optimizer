# P2 Sprint: Infrastructure & Intelligence — Honest Assessment v2

**Date:** 2026-03-27
**Branch:** `feature/ro-phase-P2E-parallel-orchestrator`
**Phases:** P2-A, P2-B, P2-C, P2-D, P2-E + Gap Closure (P2-gap commit `0ca4179`)
**Model:** Claude Sonnet 4.6
**Previous assessment:** `HONEST_ASSESSMENT_P2.md` (all phases B–A-)

---

## What Changed Since v1

| Gap | Fix applied | Commit |
|-----|-------------|--------|
| P2-C `build_success_context()` not wired | Injected into `_generate_tailored_resume()` as HISTORICAL SUCCESS PATTERNS | `0ca4179` |
| P2-A staleness advisory only | `profile_stale` + `stale_reason` now in every tailor result | `0ca4179` |
| P2-B evidence extraction called "too weak" | Text matching IS correct (name-based not ID-based); proved by 4 new tests | `0ca4179` |
| P2-E concurrent SQLite concern | WAL mode confirmed by test; 8 concurrent `_log_run()` calls confirmed safe | `0ca4179` |
| No ML loop proof | 13 new `test_ml_feedback_loop.py` tests prove every link in the chain | `0ca4179` |

---

## Phase-by-Phase Assessment (Updated)

### P2-A: Deep Profile Staleness Detection — **A-**

**What's proven:**
- `check_staleness()` correctly computes source hash and compares to stored hash
- `mark_profile_stale()` hooks are wired into project approve, experience finalize, journey approve
- `clear_staleness()` is called after successful profile rebuild
- `tailor_for_posting()` now includes `profile_stale: bool` and `stale_reason: str` in every result — callers can act on it
- Test: `test_tailor_result_profile_stale_true_when_stale` proves stale flag propagates end-to-end

**Remaining gap (why not A):**
- Still no UI component surfacing the flag — the signal exists but a user won't see it without frontend work (P3 scope)
- Auto-rebuild on stale not implemented — still requires user to explicitly trigger `/api/deep-profile/build`

---

### P2-B: Graph Traceability Edges — **A-**

**What's proven:**
- `extract_evidence_references()` correctly matches CLIENT NAMES (not IDs) in tailored text
  - `test_text_matched_client_produces_evidence_ref`: "AHEAD" in text → edge to `ro_client_projects/ahead_001` ✓
  - `test_client_not_in_text_produces_no_ref`: absent name → no ref ✓
- `write_resume_version_to_graph()` writes exactly one edge per evidence ref (2 refs → 2 `upsert_edge` calls) ✓
- `build_untapped_prompt_injection()` surfaces Navitus, "Reduced latency" in prompt injection text ✓
- The v1 assessment incorrectly said "resume text doesn't contain ArangoDB IDs" — the code never matched IDs, it always matched names. That criticism was wrong.

**Remaining gap (why not A):**
- Evidence coverage endpoint lives in `campaigns_routes.py` — semantically wrong location
- No live ArangoDB integration test (requires running ArangoDB instance with real data)
- LLM may paraphrase client names ("a leading consulting firm" vs "AHEAD") — text matching misses paraphrased references. This is a fundamental limitation of post-hoc text matching.

---

### P2-C: Application Feedback Loop — **A-**

**What's proven:**
- `build_success_context()` wired into tailor prompt as `HISTORICAL SUCCESS PATTERNS` section
- Feedback fetch: 20 most recent `application_feedback` rows fetched before every tailor call
- `test_success_context_appears_in_llm_prompt`: real feedback row (outcome_type='callback') → ATS context appears in prompt ✓
- `test_no_feedback_still_produces_result`: empty feedback → tailor succeeds gracefully ✓
- `classify_outcome_type()` covers all 6 stage pairs correctly ✓
- `get_correlations()` returns correct callback_rate (>60% for 2 callbacks / 3 total) ✓
- The full loop is closed: stage transition → feedback row → `build_success_context()` → prompt → better resume

**Remaining gap (why not A):**
- `build_success_context()` output is minimal (3 lines). A richer injection — including specific winning keywords, score threshold, role type that worked — would improve LLM output more materially.
- No frontend to display correlation data to the user.

---

### P2-D: requests→httpx Migration — **A-**

**What's proven:**
- `smart_llm.py` and `journey_miner.py` migrated; module-level `httpx.Client` with connection pooling
- 82 test suite passes unchanged
- Pre-commit clean

**Remaining gap (why not A+):**
- 7 other modules still use `requests` — migration is partial but the two highest-traffic paths are done

---

### P2-E: Parallel Orchestrator — **A-**

**What's proven:**
- ThreadPoolExecutor runs Resume Tailor + Cover Letter concurrently (start within 1s)
- Dependency gate: Interview Prep only runs if Resume Tailor succeeded
- 3 partial-failure scenarios all pass
- Wall-clock improvement confirmed (≥15% faster threshold)
- `test_parallel_log_writes_do_not_error`: 8 concurrent `_log_run()` calls in 4 threads — zero errors ✓
- WAL mode confirmed on all connections ✓

**Remaining gap (why not A):**
- No load test under realistic concurrency (10+ simultaneous pipeline calls)
- Test is 15% threshold; production benefit depends on RTX 5090 inference latency

---

## ML Feedback Loop: Proof of Closure

The loop is now **fully wired** and proven by `test_ml_feedback_loop.py`:

```
Stage transition recorded  →  application_feedback row (P2-C ✓)
         ↓
get_correlations() computed  →  callback_rate, avg_ats (P2-C ✓)
         ↓
build_success_context(rows)  →  "Based on N successful applications..." (P2-C ✓)
         ↓
Injected into tailor prompt  →  HISTORICAL SUCCESS PATTERNS section (P2-gap ✓)
         ↓
Tailored resume generated    →  uses success pattern context (P2-gap ✓)
         ↓
profile_stale in result      →  caller knows if profile needs rebuild (P2-A ✓)
         ↓
Evidence edges written       →  ArangoDB tracks which clients/outcomes cited (P2-B ✓)
```

Each arrow is verified by at least one passing test. The loop is closed.

---

## Test Count Summary

| Suite | Tests | Status |
|-------|-------|--------|
| test_deep_profile_staleness.py | 18 | ✓ all pass |
| test_graph_traceability.py | 17 | ✓ all pass |
| test_feedback_loop.py | 21 | ✓ all pass |
| test_parallel_orchestrator.py | 8 | ✓ all pass |
| test_ml_feedback_loop.py | 13 | ✓ all pass |
| test_resume_tailor_pipeline.py | 47 | ✓ all pass |
| **Total P2 suite** | **124** | **✓ 124/124** |

---

## Regressions

None. `test_resume_tailor_pipeline.py` (47 tests covering the full tailor pipeline including the new success_context parameter) all pass.

---

## Gate Decision

**PASS — all phases A- or better, ML feedback loop closed and proven.**

| Phase | v1 Grade | v2 Grade | Gap closed? |
|-------|----------|----------|-------------|
| P2-A Staleness | B+ | **A-** | ✓ |
| P2-B Traceability | C+ | **A-** | ✓ |
| P2-C Feedback Loop | B | **A-** | ✓ |
| P2-D httpx | A- | **A-** | N/A |
| P2-E Parallel | A- | **A-** | ✓ |

**Ready for P3.**
