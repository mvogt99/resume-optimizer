# Resume Optimizer Integration — Approved Plan

**Status:** APPROVED by user 2026-03-27 | **P1+P2 COMPLETE** merged to main 2026-03-27 (commit ed812ab)
**Roadmap:** `INTEGRATION_ROADMAP_2026-03-27.md` (14 phases, ~216 new tests, ~12-15 sessions)

## Pre-implementation Status

### Infrastructure Health (verified 2026-03-27)
- RTX 5090: 33°C, 14W idle, persistence ON, compute DEFAULT
- vLLM: Qwen3-Coder-30B-A3B loaded on port 8021
- Gateway: healthy on port 8000, all models registered
- pytest-xdist: installed in resume-optimizer .venv

### Test Baseline (INCOMPLETE)
- Non-E2E suite (~1900 tests) was running with 2 workers but interrupted by token budget
- Partial observation: 1 failure, 1 skip seen at ~48% through single-worker run
- **Must complete baseline before starting Phase P0-A**
- E2E/GPU tests not yet run

## Resume Instructions

When user sends "resume":

1. **Complete test baseline** (Step 2 from session prompt):
   ```bash
   cd /home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer
   source .venv/bin/activate && cd backend
   python -m pytest tests/ -q --tb=short -p no:warnings -n 2 \
     --ignore=tests/test_e2e_functional.py \
     --ignore=tests/test_regression_e2e.py \
     --ignore=tests/test_agents_e2e.py \
     --ignore=tests/test_agents_wave2_live.py
   ```
   Record: X passed, Y failed, Z errors, S skipped.

2. **Start Phase P0-A** (Data Quality Remediation):
   - Prompt user: "Phase P0-A is mechanical data cleanup — recommend Sonnet. Approve model switch?"
   - Create branch: `feature/ro-phase-P0A-data-quality`
   - Read `PHASE_P0A.md` for detailed task specs
   - Follow workflow contract (TDD, FTAL delegation, PersonaForge, honest assessment, user gate)

3. **Phase order (approved):**

| Phase | Name | Model | Status |
|-------|------|-------|--------|
| P0-A | Data Quality Remediation | Sonnet | ✅ COMPLETE |
| P0-B | FTAL Harness Integration | Sonnet + Opus | ✅ COMPLETE |
| P1-A | SQLite Hardening | Sonnet | ✅ COMPLETE |
| P1-B | PersonaForge Integration | Sonnet + Opus | ✅ COMPLETE |
| P1-C | E2E Agent Validation | Opus | ✅ COMPLETE |
| P1-D | LinkedIn Narrative Regen | Sonnet | ✅ COMPLETE |
| P2-A | Deep Profile Staleness | Sonnet | ✅ COMPLETE (A-) |
| P2-B | Graph Traceability Edges | Sonnet | ✅ COMPLETE (A-) |
| P2-C | Application Feedback Loop | Sonnet | ✅ COMPLETE (A-) |
| P2-D | requests→httpx Migration | Sonnet | ✅ COMPLETE (A-) |
| P2-E | Parallel Orchestrator | Sonnet | ✅ COMPLETE (A-) |
| P2-F | PostgreSQL Migration | Sonnet | ⏸ DEFERRED (2-3 sessions) |
| **P3-A** | **Security Remediation** | **Opus → Sonnet** | **✅ COMPLETE (A-)** |
| FINAL | Merge + Full E2E | Opus | ✅ COMPLETE (A-) |

**P1+P2 merged to main:** commit `ed812ab` (2026-03-27) — 75 files, 6388 insertions, 124 new tests, all gates PASS.
**P3 merged to main:** commit `16d717f` (2026-03-28) — P3-A+P3-B security, 23 tests.
**FINAL assessment:** commit `06cb9ea` (2026-03-28) — 105/109 E2E pass, A- overall.
**Remaining work:** see `REMAINING_WORK_2026-03-28.md` (P4-A, P2-F, P4-B).

## Key Dependencies
- P1-C depends on P0-B + P1-B
- P1-D depends on P0-A + P1-B
- P2-F depends on P1-A
- FINAL depends on all phases
