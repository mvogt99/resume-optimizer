# Phase P0-A: Data Quality Remediation

**Branch:** `feature/ro-phase-P0A-data-quality`
**Model:** Sonnet (mechanical data cleanup)
**Addresses:** Finding F3 (R3)
**Status:** PENDING
**Estimated tests:** 15-20

---

## Objective

Clean the data foundation before any integration work. Duplicate clients inflate graph
traversal results. Bad event titles pollute narrative synthesis. Stale LinkedIn headline
misrepresents career level.

## Tasks

### P0-A.1: Deduplicate client_projects (Sonnet)
- **Test first:** Write test asserting each client_name appears exactly once after dedup
- **Implementation:** SQL script to keep newest row per (client_name), delete older duplicates
- **Validation:** Count before/after, verify ArangoDB graph consistency
- **Files:** `models.py` (migration), new `migrations/dedup_clients.py`

### P0-A.2: Clean bad journey_events (Sonnet)
- **Test first:** Write test asserting no events match bad-title patterns after cleanup
- **Implementation:** Delete or retitle events matching:
  - `^SESSION` prefix
  - `^ARCHIVE` prefix
  - `^\d{4}.\d{2}.\d{2}$` (date-only titles)
  - Titles < 10 chars with no meaningful content
- **Validation:** Count before/after, sample timeline quality

### P0-A.3: Regenerate journey narratives with deep profile context (Sonnet)
- **Test first:** Write test asserting LinkedIn headline contains leadership keywords
- **Implementation:** Re-run `journey_synthesizer._generate_linkedin_sections()` with deep
  profile summary injected as context
- **Validation:** Compare old vs new narratives, verify headline alignment
- **Note:** Requires RTX 5090 online for LLM calls via FTAL harness

### P0-A.4: Add new journey milestone events (Sonnet)
- **Test first:** Write test asserting new milestone events exist for FTAL governance, PF
  integration, 6-agent system, 10K knowledge graph
- **Implementation:** Insert milestone events reflecting:
  - FTAL-governed career intelligence capability (2026-03-27)
  - PersonaForge-enhanced career prompts (2026-03-27)
  - 10,475-event knowledge graph achievement (2026-03-27)
  - 6-agent career intelligence system on $0 local GPU (2026-03-27)
- **Validation:** Timeline shows new milestones in correct position

## Acceptance Criteria

- [ ] Zero duplicate client_name rows in client_projects
- [ ] Zero journey_events with date-only or session-prefix titles
- [ ] LinkedIn headline reflects leadership profile (not IC engineer)
- [ ] New milestone events present in journey_events
- [ ] All existing tests still pass
- [ ] FTAL gap score < 30 on regenerated narratives

## User Gate P0-A

**Present to user:**
1. Before/after data counts (clients, events)
2. Sample cleaned timeline (10 most recent events)
3. Old vs new LinkedIn headline and summary
4. New milestone events
5. FTAL gap scores on regenerated narratives
6. Honest assessment of data quality improvement

**User decides:** Accept or request alternative approach.
