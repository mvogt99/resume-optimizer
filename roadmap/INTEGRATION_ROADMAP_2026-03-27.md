# Resume Optimizer Integration Roadmap

**Created:** 2026-03-27
**Author:** Claude Opus 4.6 (Expert AI)
**Source:** `ARCHITECTURE_ANALYSIS_2026-03-27.md`
**Status:** DRAFT — Pending user approval before implementation

---

## Workflow Contract (applies to ALL phases)

Each phase follows this mandatory workflow:

1. **Branch** — Create `feature/ro-phase-XX-<name>` from `main`
2. **TDD** — Write tests FIRST, then implement until tests pass
3. **FTAL Delegation** — All code generation delegated to RTX 5090 via FTAL harness
4. **PersonaForge** — `pf_recall` before task, `pf_remember` after success
5. **Honest Assessment** — Score output with FTAL, document gap scores
6. **User Gate** — Present results + honest assessment to user:
   - **Accept** — Merge to feature branch, update plan status, update docs
   - **Reject + Alternative** — Expert AI generates alternative, honest assessment, new gate
7. **Documentation** — Update CLAUDE.md, ROADMAP.md, architecture docs, plan (MD + JSON)
8. **Commit + Push** — All changed files committed to feature branch

### Model Tier Protocol

| Task Type | Model | Justification |
|-----------|-------|---------------|
| Architecture decisions, plan creation, honest assessments | Opus | Complex reasoning |
| Code generation, test writing, mechanical refactoring | Sonnet | Cost-efficient |
| Code review, security audit | Opus | Requires judgment |
| Data cleanup scripts, SQL migrations | Sonnet | Mechanical |

### No-Skip Policy

- No stubs, skeletons, skips, or excuses
- Every test must assert real behavior
- Every agent call must produce validated output
- Every honest assessment must include concrete gap scores

## Phase Index

| Phase | Name | Priority | File |
|-------|------|----------|------|
| P0-A | Data Quality Remediation | P0 | [PHASE_P0A.md](PHASE_P0A.md) |
| P0-B | FTAL Harness Integration | P0 | [PHASE_P0B.md](PHASE_P0B.md) |
| P1-A | SQLite Hardening | P1 | [PHASE_P1A.md](PHASE_P1A.md) |
| P1-B | PersonaForge Integration | P1 | [PHASE_P1B.md](PHASE_P1B.md) |
| P1-C | End-to-End Agent Validation | P1 | [PHASE_P1C.md](PHASE_P1C.md) |
| P1-D | LinkedIn Narrative Regeneration | P1 | [PHASE_P1D.md](PHASE_P1D.md) |
| P2-A | Deep Profile Staleness Detection | P2 | [PHASE_P2A.md](PHASE_P2A.md) |
| P2-B | Graph Traceability Edges | P2 | [PHASE_P2B.md](PHASE_P2B.md) |
| P2-C | Application Feedback Loop | P2 | [PHASE_P2C.md](PHASE_P2C.md) |
| P2-D | requests to httpx Migration | P2 | [PHASE_P2D.md](PHASE_P2D.md) |
| P2-E | Parallel Orchestrator via Artemis | P2 | [PHASE_P2E.md](PHASE_P2E.md) |
| P2-F | PostgreSQL Migration | P2 | [PHASE_P2F.md](PHASE_P2F.md) |
| P3-A | Security Remediation | P3 | [PHASE_P3A.md](PHASE_P3A.md) |
| FINAL | Merge + Full E2E Validation | — | [PHASE_FINAL.md](PHASE_FINAL.md) |

## Dependency Graph

```
P0-A (Data Quality) ─────────────────────────────────────────┐
P0-B (FTAL Integration) ──┬──────────────────────────────────┤
P1-A (SQLite Hardening) ──┤                                  │
P1-B (PersonaForge) ──────┤                                  │
P1-C (E2E Validation) ────┤ (depends: P0-B, P1-B)           │
P1-D (LinkedIn Regen) ────┤ (depends: P0-A, P1-B)           ├── FINAL
P2-A (Profile Staleness) ─┤                                  │
P2-B (Graph Traceability) ┤                                  │
P2-C (Feedback Loop) ─────┤                                  │
P2-D (httpx Migration) ───┤                                  │
P2-E (Parallel Orch) ─────┤                                  │
P2-F (PostgreSQL) ────────┤ (depends: P1-A)                  │
P3-A (Security) ──────────┘──────────────────────────────────┘
```

### Hard Dependencies

- P1-C depends on P0-B + P1-B (FTAL + PF must be integrated before E2E validation)
- P1-D depends on P0-A + P1-B (clean data + PF context needed for narrative regen)
- FINAL depends on all phases

### Soft Dependencies (recommended order, not blocking)

- P0-A before P0-B (clean data before quality-scoring LLM output)
- P1-A before P1-B (SQLite stable before adding PF writes)
- P2-A before P2-C (staleness detection useful for feedback loop)

## Estimated Timeline

| Phase | Sessions | Notes |
|-------|----------|-------|
| P0-A | 1 | Data cleanup |
| P0-B | 1-2 | Core integration |
| P1-A | 0.5 | Mechanical |
| P1-B | 1 | New module |
| P1-C | 1 | RTX 5090 required |
| P1-D | 0.5 | Regen + review |
| P2-A/B/C/D/E | 4 | Mixed effort |
| P2-F | 2-3 | PostgreSQL migration |
| P3-A | 1-2 | Future session |
| FINAL | 1 | Merge + validation |
| **Total** | **~12-15** | |
