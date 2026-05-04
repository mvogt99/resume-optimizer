# Resume Session Prompt

Copy everything below the line and paste into a new Claude Code session.

---

## RESUME: Resume Optimizer Integration Roadmap

**Context:** A deep architecture analysis of the resume-optimizer app was completed on 2026-03-27. A 14-phase integration roadmap was created and **APPROVED by user** to connect the app to the hybrid-ai-windows governance infrastructure (FTAL harness, PersonaForge, ArangoDB graph).

**Start on Sonnet** — roadmap is approved, next step is mechanical work (test baseline + Phase P0-A).

### What was completed in previous sessions:

1. Deep architecture analysis stored at:
   - `applications/resume-optimizer/roadmap/ARCHITECTURE_ANALYSIS_2026-03-27.md`
   - `applications/resume-optimizer/roadmap/ARCHITECTURE_ANALYSIS_2026-03-27.json`

2. Full 14-phase integration roadmap (APPROVED):
   - `applications/resume-optimizer/roadmap/INTEGRATION_ROADMAP_2026-03-27.md` (index)
   - `applications/resume-optimizer/roadmap/INTEGRATION_ROADMAP_2026-03-27.json` (full JSON)
   - `applications/resume-optimizer/roadmap/APPROVED_PLAN_2026-03-27.md` (approved plan + resume state)
   - `applications/resume-optimizer/roadmap/APPROVED_PLAN_2026-03-27.json` (machine-readable)
   - `applications/resume-optimizer/roadmap/PHASE_P0A.md` through `PHASE_FINAL.md` (14 detail files)

3. Infrastructure verified healthy (2026-03-27): RTX 5090 33°C, vLLM Qwen3-Coder-30B on 8021, gateway on 8000.

4. Test baseline: INCOMPLETE — non-E2E suite (~1900 tests) was interrupted by token budget at ~48%. Partial: 1 failure, 1 skip observed. pytest-xdist installed in .venv.

### What needs to happen now (in order):

**Step 1: Verify GPU + infrastructure health** (quick check — may already be up)
```bash
nvidia-smi --query-gpu=temperature.gpu,power.draw --format=csv
curl -s http://localhost:8021/v1/models | jq '.data[0].id'
curl -s http://localhost:8000/health | jq '.status'
```
If anything is down, restart: `docker restart vllm-ngc && sleep 30` and/or `systemctl --user restart hybrid-ai-gateway`.

**Step 2: Complete test baseline**
Run with 2 workers (pytest-xdist already installed, CPU safety OK at 2 workers on 32 cores):
```bash
cd /home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer
source .venv/bin/activate && cd backend
python -m pytest tests/ -q --tb=short -p no:warnings -n 2 \
  --ignore=tests/test_e2e_functional.py \
  --ignore=tests/test_regression_e2e.py \
  --ignore=tests/test_agents_e2e.py \
  --ignore=tests/test_agents_wave2_live.py
```
Record: X passed, Y failed, Z errors, S skipped. Update `APPROVED_PLAN_2026-03-27.json` test_baseline.

**Step 3: Begin Phase P0-A** (roadmap already approved)
- Create branch: `feature/ro-phase-P0A-data-quality`
- Read `PHASE_P0A.md` for detailed task specs
- Follow the workflow contract in `INTEGRATION_ROADMAP_2026-03-27.md`:
  1. TDD — tests first
  2. FTAL delegation — all code gen through harness
  3. PersonaForge — pf_recall before, pf_remember after
  4. Honest assessment with FTAL gap scores
  5. User gate — present results, user accepts or requests alternative
  6. Update plan MD + JSON status fields
  7. Commit + push to feature branch

### Workflow rules (MANDATORY for all phases):

- **No stubs, skeletons, skips, or excuses** — every test asserts real behavior
- **FTAL + PersonaForge endpoints are mandatory** for all delegation and knowledge ops
- **Model tier protocol:**
  - Opus: architecture decisions, planning, honest assessments, code review
  - Sonnet: code generation, test writing, mechanical refactoring
  - **Always prompt user before switching models**
- **User gates:** Present honest assessment at each phase boundary. User decides accept or alternative.
- **On acceptance:** Update all documentation (CLAUDE.md, ROADMAP.md, plan MD+JSON), commit and push changed files
- **Git strategy:** Feature branch per phase (`feature/ro-phase-XX-<name>`), PR to main. Phase FINAL merges all branches with full E2E testing.
- **CPU safety:** Never run tests when CPU >70%. Max 2 pytest workers. Kernel panic risk.

### Phase order with model tiers:

| Phase | Model | Notes |
|-------|-------|-------|
| P0-A Data Quality | Sonnet | Mechanical cleanup |
| P0-B FTAL Integration | Sonnet + **switch to Opus** for B.2 (classification) and B.5 (assessment) |
| P1-A SQLite Hardening | Sonnet | Mechanical |
| P1-B PersonaForge | Sonnet + **switch to Opus** for B.2 (persona design) |
| P1-C E2E Validation | **Opus** entire phase | Quality judgment, RTX 5090 required |
| P1-D LinkedIn Regen | Sonnet | RTX 5090 required |
| P2-A Profile Staleness | Sonnet | |
| P2-B Graph Traceability | Sonnet | |
| P2-C Feedback Loop | Sonnet + **switch to Opus** for C.2 (correlation design) |
| P2-D httpx Migration | Sonnet | |
| P2-E Parallel Orchestrator | Sonnet + **switch to Opus** for E.1 (concurrency design) |
| P2-F PostgreSQL Migration | Sonnet | Depends on P1-A |
| P3-A Security | **Opus** (audit) + Sonnet (implementation) | Future phase |
| FINAL Merge + E2E | **Opus** | Integration judgment |

### Key file locations:

- **Resume optimizer:** `~/models/source/hybrid-ai-windows/applications/resume-optimizer/`
- **Backend:** `applications/resume-optimizer/backend/`
- **Roadmap:** `applications/resume-optimizer/roadmap/`
- **Gateway:** `~/models/source/hybrid-ai-windows/gateway/`
- **FTAL harness MCP:** `~/.mcp/mcp_harness_server.py`
- **PersonaForge:** http://localhost:8090
- **vLLM (RTX 5090):** http://localhost:8021
- **Gateway:** http://localhost:8000
