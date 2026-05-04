# AI Journey Update — Implementation Plan (entry + protocols)

| Field | Value |
|---|---|
| Plan ID | `JOURNEY_UPDATE_PLAN_2026-04-20` |
| Companion JSON (authoritative state) | `working-docs/journey-update-2026-04-20/JOURNEY_UPDATE_PLAN_2026-04-20.json` |
| Phases 0–3 detail | `working-docs/journey-update-2026-04-20/JOURNEY_UPDATE_PLAN_2026-04-20_phases_0_to_3.md` |
| Phases 4–6 detail | `working-docs/journey-update-2026-04-20/JOURNEY_UPDATE_PLAN_2026-04-20_phases_4_to_6.md` |
| Source analysis | `workdir/reports/JOURNEY_UPDATE_ANALYSIS_2026-04-20.{json,md}` |
| Planned by | Claude Opus 4.6, 2026-04-20 |
| Default implementation model | **Haiku 4.5** (`claude-haiku-4-5-20251001`) |
| Status | **APPROVED_PENDING — awaiting user approval to start Phase 0** |

This file is the **entry point**. The JSON companion is the **single source of truth for progress**. Per-phase detail is split across the two phases files to comply with the 500-line-per-file invariant. MD files are human-readable; all state lives in JSON.

---

## 0. How to read this plan

**Fresh-session resume order:**
1. Read this file (entry + protocols).
2. Read the JSON companion — current phase, current micro-task, outstanding gate items.
3. Read the relevant phases file (`phases_0_to_3.md` or `phases_4_to_6.md`).
4. Read the newest `working-docs/journey-update-2026-04-20/progress/phase_<N>_PROGRESS.md` if present.
5. Run the pre-phase reassessment checklist (SS3.4) before writing any code.

**Invariants (violating these requires explicit user approval):**
- Delegation is mandatory for code/refactor/bugfix/test/review/debug. Claude Code orchestrates; FTAL harness executes.
- Correctness > speed. Gate failure -> iterate in the current phase; never skip forward.
- TDD first. Test written and observed failing before implementation; implementation turns it green without changing the assertion.
- Mutation verification. Every test claimed as coverage must be proved by breaking the production line, observing expected failure, then restoring.
- PersonaForge + learnings updated at phase boundaries.
- Default Haiku. Switch to Sonnet/Opus only with documented rationale, via explicit user `/model <name>` action.
- User gives express permission for shell execution per standing rule. Plan emits commands; user executes.
- Never modify `architectural-audit-2026-03-15.md` or `architectural-audit-2026-03-15-1.md`.
- Never write files >500 lines (`immutable_file_size_limit.md`); split into modules.
- Resume-optimizer backend must be running for API calls. Use `./ro start` (NOT docker-compose).

---

## 1. As-built snapshot to verify before Phase 0

Before starting Phase 0 (and at every pre-phase reassessment), confirm the as-built state below still holds. If any item drifts, patch the plan *before* proceeding.

| Claim | Verification | Expected |
|---|---|---|
| Resume-optimizer backend up on :5000 | `./ro status` | backend running PID, port 5000 |
| Resume-optimizer frontend on :3000 | `./ro status` | frontend running PID, port 3000 |
| Gateway up on :8000 | `curl -s http://localhost:8000/health` | active |
| vLLM up on :8021 | `curl -s http://localhost:8021/v1/models` | model loaded |
| PersonaForge up on :8090 | `curl -s http://localhost:8090/status` | active |
| ArangoDB up on :8529 | Python `db.version()` | accessible |
| Journey events for user 10 | `sqlite3 backend/database.db "SELECT COUNT(*) FROM journey_events WHERE user_id=10"` | 10,316 |
| Journey sources for user 10 | `sqlite3 backend/database.db "SELECT COUNT(*) FROM journey_sources WHERE user_id=10"` | 12,086 |
| Latest event date | `sqlite3 backend/database.db "SELECT MAX(event_date) FROM journey_events WHERE user_id=10"` | 2026-03-10 |
| FTAL harness callable | `curl -s http://localhost:8000/api/harness/stats` | responds |
| API docs hub on :8900 | `curl -s http://localhost:8900/catalog` | 6 services |

---

## 2. Decisions locked in this session

| # | Question | Decision |
|---|---|---|
| D1 | Scope | **Both** data refresh AND code changes (replace Qdrant paths, add PersonaForge mining) |
| D2 | Qdrant handling | **(b)** Write replacement mining paths + **(c)** one-time data migration |
| D3 | Narrative strategy | **(a)** Supplement existing, ensuring cohesive full-arc story |
| D4 | ArangoDB approval | **Auto-approve** — no manual review gate |
| D5 | Service management | Use `./ro start/stop/status` (local dev), NOT docker-compose |
| D6 | Downstream refresh | **Yes** — deep profile, campaign seeds, resume narratives all refreshed |
| D7 | Model-swap handling | **Prompt-based hard pause.** Plan emits `/model <name>` + resume prompt; session pauses until user replies "proceed". |
| D8 | Quality gate per phase | **All four**: FTAL gap<10 + mutation-verified tests + narrative coherence check + brutal self-review. |
| D9 | User ID scope | **User 10 only** — single-user journey update |
| D10 | Qdrant snapshot source | Global Qdrant was on port 6333 (decommissioned 2026-03-19). Snapshot data may exist in ArangoDB collections already migrated. |

---

## 3. Cross-phase protocols

These apply to every phase. Any deviation must be justified in the phase's progress log.

### 3.1 Session-resume protocol

**Context budget** measured in tokens consumed in the current Claude Code session.

| Model | Budget | 75% soft | 85% hard |
|---|---:|---:|---:|
| Opus 4.6 | 100,000 | 75,000 | 85,000 |
| Sonnet 4.6 | 200,000 | 150,000 | 170,000 |
| Haiku 4.5 | 400,000 | 300,000 | 340,000 |

**At 75% (soft pause):**
- Emit: current phase, current micro-task, last completed step, files touched, git-status summary, required model for resume, outstanding quality-gate items.
- Write to `working-docs/journey-update-2026-04-20/progress/phase_<N>_PROGRESS.md`; update JSON `current_state`.

**At 85% (hard pause):**
- Refuse to start any new file write or test run.
- Emit the copy-paste resume prompt (SS3.1.1).
- Instruct user: `/clear` and start a new session using the prompt.

#### 3.1.1 Resume-prompt template

```
Resume JOURNEY_UPDATE implementation at phase <PHASE_ID>, micro-task <TASK_ID>.

Plan entry:   applications/resume-optimizer/working-docs/journey-update-2026-04-20/JOURNEY_UPDATE_PLAN_2026-04-20.md
Phases file:  applications/resume-optimizer/working-docs/journey-update-2026-04-20/JOURNEY_UPDATE_PLAN_2026-04-20_phases_<0_to_3|4_to_6>.md
State JSON:   applications/resume-optimizer/working-docs/journey-update-2026-04-20/JOURNEY_UPDATE_PLAN_2026-04-20.json
Last progress: working-docs/journey-update-2026-04-20/progress/phase_<N>_PROGRESS.md

Required model: <MODEL_NAME>
Before starting: run `/model <MODEL_NAME>` and reply "proceed".

Before touching any file:
  1. Re-read the plan entry SS0-3 (how-to-use + decisions + protocols).
  2. Re-read phase <PHASE_ID> section in the phases file.
  3. Run the pre-phase reassessment checklist (SS3.4) and record pass/fail.
  4. Verify prior phases still pass their exit criteria.

Resume micro-task <TASK_ID> only after (1)-(4) are clean.
Correctness over speed. Mutation-verify every test claim. Update the JSON progress after every step.
```

### 3.2 Model-switch protocol (Haiku default)

**Default** for all implementation: **Haiku 4.5** (`claude-haiku-4-5-20251001`).

Switch to **Sonnet 4.6** for:
- Post-phase brutal self-review (SS3.3 item 4).
- Code architecture design decisions (new mining methods).
- Narrative coherence review (Phase 5).
- Any micro-task flagged `required_model: sonnet` in JSON.

Switch to **Opus 4.6** for:
- Plan revision when a prior-phase assumption is invalid.
- Genuine architectural ambiguity requiring a new decision.
- Any micro-task flagged `required_model: opus`.

**How switching is initiated** — plan emits a switch block:
```
MODEL SWITCH REQUIRED
Reason: <reason>
Run: /model <target>
Then reply: "proceed"
```
Session hard-pauses until user confirms with "proceed". If user declines, plan documents the deviation and downgrades the phase's gate accordingly.

### 3.3 Quality-gate protocol — the 10/10 definition

A phase may not advance until **all four** are satisfied:

1. **FTAL gap<10** on every code artifact (harness-scored). For non-code (config/data/ops): smoke test green + expected output verified.
2. **Mutation-verified tests** — record in `progress/phase_<N>_MUTATIONS.md`:
   - Production line (file:line)
   - Mutation applied
   - Expected failure (pytest output)
   - Restoration confirmed (pytest output)
3. **Narrative coherence check** — journey events tell a cohesive story; no orphaned events, no contradictory timelines, technologies match commit evidence.
4. **Brutal self-review** at `progress/phase_<N>_BRUTAL_REVIEW.md`:
   - What could silently corrupt the journey data?
   - What assumption did I rely on without verifying?
   - What did I skip because it was hard?
   - Are the new events consistent with existing ones?
   - Would this journey data be credible to a hiring manager? If not, what's missing?
   - Severity-rated residual risks (P0 / P1 / P2).
   - **Any P0 blocks the phase gate.**
   - Produced on Sonnet (model-switch required).

### 3.4 Pre-phase reassessment protocol

Every phase starts with this. Failure -> patch the plan *before* proceeding.

- [ ] Re-verify SS1 claims still hold (services up, data counts match).
- [ ] Verify each prior phase's exit criteria still pass.
- [ ] Re-read the current phase section.
- [ ] Read latest `progress/phase_<N>_PROGRESS.md` if present.
- [ ] Confirm no commits since last progress altered any assumption.
- [ ] Record reassessment result (pass/fail + notes) in the progress file.

### 3.5 Iteration & re-plan protocol

**Within a phase:** gate fail -> iterate.
- Identify which of the 4 gate items failed.
- Fix the specific failure.
- Re-run the gate.
- **Max 3 iterations per phase.** After 3rd failure -> escalate to re-plan.

**Re-plan escalation:**
- Switch to **Opus 4.6** (user confirms "proceed").
- Re-read source analysis + this plan.
- Analyze root cause.
- Update plan; bump plan version in JSON.
- Resume phase from the beginning.

### 3.6 Delegation protocol

Every code/refactor/test/review/debug task goes through FTAL harness:
```
POST http://localhost:8000/api/harness/run
{"task": "<task description>", "task_type": "<coding|review|...>", "max_tokens": <n>}
```
Or via MCP `delegate_task`. Expert AI (Claude Code) does not emit final work-product code; it orchestrates, validates, applies.

If FTAL gap >= 30 -> create teaching doc; retry with teaching context. If gap stays >= 30 after 3 retries -> escalate to Sonnet/Opus.

### 3.7 PersonaForge integration points

- **Phase start:** `pf_recall(namespace="project_knowledge", query="journey mining <phase topic>")`
- **Each micro-task completion:** `pf_remember(namespace="project_knowledge", content="<learning>")`
- **Phase end:** `pf_remember` with brutal self-review summary tagged `phase_gate`.

### 3.8 Service management protocol

```bash
# Start services (must be in resume-optimizer root)
cd /home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer
./ro start

# Check status
./ro status

# Stop after completion
./ro stop
```

Backend must be running for all API calls (Phases 2, 5, 6). Verify with `curl -s http://localhost:5000/api/agents/status`.

---

## 4. Phase index

Full detail in the phases files.

| Phase | Title | File | Typical model |
|---|---|---|---|
| 0 | Preflight & Service Verification | phases_0_to_3.md | Haiku |
| 1 | Data Preparation — Governance & SESSION_STATE | phases_0_to_3.md | Haiku |
| 2 | Incremental Mining — Git + Files + Cost | phases_0_to_3.md | Haiku |
| 3 | Code: Replace Qdrant FTAL Path with ArangoDB | phases_0_to_3.md | Haiku (Sonnet for design + brutal) |
| 4 | Code: PersonaForge Mining + Qdrant Data Migration | phases_4_to_6.md | Haiku (Sonnet for design + brutal) |
| 5 | Narrative Generation & Cohesion + ArangoDB Approval | phases_4_to_6.md | Haiku (Sonnet for narrative review + brutal) |
| 6 | Downstream Consumer Refresh | phases_4_to_6.md | Haiku (Sonnet for brutal) |

Each phase provides: Objective, Pre-phase reassessment, Required model, Deliverables, Micro-tasks, Quality gate, Exit criteria, PersonaForge learnings.

---

## 5. Risks and non-goals (plan-wide)

**Cross-phase risks:**
- SQLite corruption during mining (large INSERT batch) — backup `database.db` before each mining phase.
- FTAL harness timeout on LLM-heavy narrative generation — break into small batches.
- ArangoDB write failures during auto-approve — retry logic exists in `arango_client.py`.
- Downstream refresh triggers LLM calls that may fail if vLLM is busy — sequence, don't parallel.
- Qdrant data migration relies on snapshot integrity — validate record counts.

**Non-goals:**
- Rebuilding the journey mining UI (frontend unchanged).
- Adding new journey event categories beyond existing 5 (milestone, development, achievement, fix, learning).
- Changing the mining pipeline architecture (mixin pattern stays).
- Modifying the journey miner for other users (user 10 only).
- Re-running downstream systems for non-journey data changes.

**Honest limits:**
- Qdrant knowledge sources may have lost fidelity during decommission; migration captures what's in snapshots.
- PersonaForge mining method is additive; it won't backfill pre-PersonaForge data.
- Narrative cohesion is subjective; the brutal review assesses it, but "cohesive story" depends on LLM quality.

---

## 6. Open-item register

| # | Item | Raised_in | Owner |
|---|---|---|---|
| O1 | Qdrant snapshot location — does a snapshot file exist post-decommission? | Phase 4 | impl session |
| O2 | PersonaForge memory count — how much data is stored? | Phase 4 | impl session |
| O3 | FTAL harness_runs table schema in gateway — confirm column names | Phase 3 | impl session |
| O4 | Narrative LLM batch size — how many events per synthesis call? | Phase 5 | impl session |
| O5 | Deep profile rebuild — does it require all journey data approved first? | Phase 6 | impl session |

---

## 7. Quick-reference tables

### 7.1 Required model per phase

| Phase | Most tasks | Special tasks |
|---|---|---|
| 0 | Haiku | (none) |
| 1 | Haiku | (none) |
| 2 | Haiku | (none) |
| 3 | Haiku | 3.1 design -> Sonnet; 3.9 brutal -> Sonnet |
| 4 | Haiku | 4.1 design -> Sonnet; 4.11 brutal -> Sonnet |
| 5 | Haiku | 5.5 narrative review -> Sonnet; 5.7 brutal -> Sonnet |
| 6 | Haiku | 6.7 brutal -> Sonnet |

### 7.2 Quality-gate summary

1. FTAL gap<10 (code) / smoke-pass (non-code/ops)
2. Mutation-verified tests (documented)
3. Narrative coherence (events consistent, timeline valid, technologies match evidence)
4. Brutal self-review on Sonnet; 0 P0 items

### 7.3 Context pause thresholds

| Model | 75% soft | 85% hard |
|---|---:|---:|
| Opus | 75,000 | 85,000 |
| Sonnet | 150,000 | 170,000 |
| Haiku | 300,000 | 340,000 |

---

## 8. Starting Phase 0 — user-facing handoff

On user approval:
1. User runs `/model haiku` (current is Opus).
2. User replies "proceed" to confirm.
3. Implementation session reads this file, the JSON companion, and `phases_0_to_3.md`.
4. Begin micro-task 0.1.

### 8.1 Initial resume prompt for Phase 0

```
Resume JOURNEY_UPDATE implementation at phase 0, micro-task 0.1.

Plan entry:   applications/resume-optimizer/working-docs/journey-update-2026-04-20/JOURNEY_UPDATE_PLAN_2026-04-20.md
Phases file:  applications/resume-optimizer/working-docs/journey-update-2026-04-20/JOURNEY_UPDATE_PLAN_2026-04-20_phases_0_to_3.md
State JSON:   applications/resume-optimizer/working-docs/journey-update-2026-04-20/JOURNEY_UPDATE_PLAN_2026-04-20.json
Last progress: (none, fresh start)

Required model: Haiku 4.5.
Confirm: `/model haiku` then reply "proceed".

Before touching any file:
  1. Re-read plan entry SS0-3.
  2. Re-read phases_0_to_3 Phase 0 in full.
  3. Run pre-phase reassessment (SS3.4); record pass/fail.
  4. Verify backend :5000, gateway :8000, vLLM :8021, PersonaForge :8090, ArangoDB :8529 are up.

Start with micro-task 0.1 (service verification).
Correctness over speed. Update JSON progress after every step.
```

---

*End of entry file. See `phases_0_to_3.md`, `phases_4_to_6.md`, and the JSON companion.*
