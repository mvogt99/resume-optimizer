# Phase P2-E: Parallel Orchestrator via Artemis

**Branch:** `feature/ro-phase-P2E-parallel-orchestrator`
**Model:** Sonnet (implementation) + Opus (concurrency design at E.1)
**Addresses:** Finding F5 (R5)
**Status:** PENDING
**Estimated tests:** 12-15

---

## Objective

Parallelize independent agent steps in the orchestrator. Currently Resume Tailor,
Cover Letter, and Interview Prep run sequentially. Resume Tailor and Cover Letter
are independent and can run in parallel via Artemis message bus (Phase 12b).

## Tasks

### P2-E.1: Design parallel execution flow (Opus)
- **Analysis:** Map agent dependencies:
  - Resume Tailor: needs posting + profile (independent)
  - Cover Letter: needs posting + profile (independent)
  - Interview Prep: needs tailored resume (depends on Resume Tailor)
- **Design:**
  - Fan-out: Submit Resume Tailor + Cover Letter to Artemis queue
  - Fan-in: Wait for both to complete (with per-agent timeout)
  - Sequential: Run Interview Prep with tailored resume from step 1
- **Error handling:** Define behavior for partial failures
- **Document:** Artemis queue names, message schema, timeout strategy

### P2-E.2: Implement parallel agent dispatch (Sonnet)
- **Test first:** Test asserting Resume Tailor and Cover Letter start within 1s
- **Implementation:** Modify `orchestrator.full_application_pipeline()`:
  - Submit both agents to Artemis via `bus_client.py`
  - Wait for both completion messages (configurable timeout, default 120s)
  - Collect results from both
  - Run Interview Prep with tailored resume from step 1
- **Files:** `agents/orchestrator.py`, `bus_client.py`

### P2-E.3: Error handling for partial failures (Sonnet)
- **Test first:** Test asserting pipeline continues if one parallel step fails
- **Implementation:**
  - If Resume Tailor fails but Cover Letter succeeds:
    - Pipeline status = "partial"
    - Interview Prep skipped (needs resume)
    - Return completed steps only
  - If Cover Letter fails but Resume Tailor succeeds:
    - Pipeline status = "partial"
    - Interview Prep runs (has resume)
    - Return completed steps only
  - If both fail: status = "failed", return errors
- **Files:** `agents/orchestrator.py`

### P2-E.4: Timing comparison test (Sonnet)
- **Test:** Measure pipeline duration with sequential vs parallel execution
- **Validation:** Parallel is at least 30% faster for full pipeline

## Acceptance Criteria

- [ ] Resume Tailor and Cover Letter run in parallel
- [ ] Interview Prep runs sequentially after Resume Tailor
- [ ] Partial failure handling works correctly
- [ ] Parallel execution >= 30% faster than sequential
- [ ] All existing tests pass
- [ ] FTAL scores maintained (parallel doesn't degrade quality)

## User Gate P2-E

**Present:** Execution timing (sequential vs parallel), error handling demo, queue design.

**Model switch:** Opus for P2-E.1 (concurrency design).
