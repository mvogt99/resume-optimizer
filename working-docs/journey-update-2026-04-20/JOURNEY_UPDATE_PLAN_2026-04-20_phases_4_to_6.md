# AI Journey Update Plan — Phases 4-6

Companion to `JOURNEY_UPDATE_PLAN_2026-04-20.md` (entry + protocols) and the JSON state file. Read SS3.3 (quality gate), SS3.4 (reassessment), and SS3.5 (iteration) before starting any phase.

---

## Phase 4 — Code: PersonaForge Mining + Qdrant Data Migration

**Objective.** Two sub-objectives: (a) Add a new `_mine_personaforge()` method to the journey miner so future mining runs capture PersonaForge memories as sources. (b) Execute a one-time migration of the 859 frozen Qdrant knowledge sources + 500 FTAL history sources into ArangoDB-backed format so they remain queryable and augmentable.

**Required model:** Haiku (default). Sonnet for design (4.1) and brutal review (4.11).

**Pre-phase reassessment.**
- SS3.4 baseline.
- Phase 3 FTAL replacement method passing tests.
- PersonaForge :8090 responding (`curl -s http://localhost:8090/status`).
- PersonaForge API docs reviewed (retrieval endpoint schema).
- Frozen Qdrant sources counted: `SELECT COUNT(*) FROM journey_sources WHERE user_id=10 AND source_type IN ('qdrant','ftal_history')`.

### Sub-objective A: PersonaForge Mining Method

#### Deliverables

1. New method `_mine_personaforge()` in `backend/journey_miner_enrichment_mixin.py`.
2. Test file `backend/tests/test_journey_personaforge_mining.py`.
3. `progress/phase_4_MUTATIONS.md`.

#### Micro-tasks

| # | Task | task_type | Model | Notes |
|---|---|---|---|---|
| 4.1 | **Design:** PersonaForge retrieval API schema | analysis | **Sonnet** | MODEL SWITCH REQUIRED. Query `POST /api/v1/retrieval/query` with broad query. Map response fields to journey source schema. Determine: what namespaces exist, what metadata is available, how to extract event_date. |
| 4.2 | TDD: test for `_mine_personaforge()` | coding | Haiku | Delegated via FTAL. Fixture-based test. Must fail first. |
| 4.3 | Implement `_mine_personaforge()` | coding | Haiku | Delegated. Calls PersonaForge API. Maps to source_type="personaforge". SHA-256 dedup. |
| 4.4 | Run test — confirm passes | ops | Haiku | |
| 4.5 | Mutation-verify: break API call -> test fails -> restore -> passes | coding | Haiku | Log to `progress/phase_4_MUTATIONS.md` |
| 4.6 | Wire `_mine_personaforge()` into main mining pipeline | coding | Haiku | Add call in `JourneyMiner.mine()` or equivalent orchestrator method |
| 4.7 | Verify file stays under 500 lines | ops | Haiku | |

### Sub-objective B: Qdrant Data Migration

#### Deliverables

1. Migration script `backend/scripts/migrate_qdrant_to_arango.py`.
2. `progress/phase_4_MIGRATION_REPORT.md` — record counts, any data quality issues.

#### Micro-tasks

| # | Task | task_type | Model | Notes |
|---|---|---|---|---|
| 4.8 | Assess frozen Qdrant source data quality | analysis | Haiku | `SELECT source_type, COUNT(*), MIN(event_date), MAX(event_date) FROM journey_sources WHERE user_id=10 AND source_type IN ('qdrant','ftal_history') GROUP BY source_type` |
| 4.9 | TDD: test for migration script | coding | Haiku | Delegated. Verify: reads from journey_sources with source_type='qdrant', writes equivalent records with source_type='arango_migrated', preserves content_hash for dedup. |
| 4.10 | Implement migration script | coding | Haiku | Delegated. Script reads SQLite qdrant/ftal_history sources, writes to ArangoDB `ro_journey_knowledge` collection (or equivalent). Updates source_type to indicate migrated status. Does NOT delete originals. |
| 4.11 | Run migration against live data | ops | Haiku | Execute script. Record: input count, output count, errors, duration. |
| 4.12 | Verify migration record counts | ops | Haiku | ArangoDB query to confirm records exist |

### Phase-level tasks

| # | Task | task_type | Model | Notes |
|---|---|---|---|---|
| 4.13 | Run full journey test suite | ops | Haiku | `cd backend && python -m pytest tests/test_journey*.py -v` |
| 4.14 | Integration test: run mining and confirm PersonaForge sources appear | ops | Haiku | |
| 4.15 | **Brutal self-review** | review | **Sonnet** | MODEL SWITCH REQUIRED. Write `progress/phase_4_BRUTAL_REVIEW.md`. |
| 4.16 | Update JSON companion | ops | Haiku | |

### Quality gate

1. FTAL gap<10 on PersonaForge mining method + migration script.
2. Mutation-verified: break PersonaForge API call -> test fails -> restore.
3. Migration report shows: input records = output records (or documented exceptions).
4. Brutal self-review on Sonnet: 0 P0 items.

### Exit criteria

PersonaForge mining method integrated; Qdrant data migrated to ArangoDB; tests green; migration report clean; user approves Phase 5.

### Risk callouts

- PersonaForge may have very few memories or inconsistent schemas — design step (4.1) must assess before committing to implementation.
- Qdrant sources in SQLite may have truncated `full_text` — migration preserves what exists, doesn't try to re-fetch from dead Qdrant.
- `journey_miner_enrichment_mixin.py` is already the largest mixin — verify 500-line limit; split if needed.

### PersonaForge learnings to save

PersonaForge retrieval API actual schema; namespace inventory; data quality assessment; migration gotchas; file size management patterns.

---

## Phase 5 — Narrative Generation, Cohesion & ArangoDB Approval

**Objective.** Generate new narratives from the April events, then review the FULL journey (Dec 2025 - Apr 2026) for narrative cohesion — the story must be tellable to another human as a coherent career arc. Auto-approve all journey data (events, sources, narratives) to the ArangoDB knowledge graph.

**Required model:** Haiku (default). Sonnet for narrative coherence review (5.5) and brutal review (5.7).

**Pre-phase reassessment.**
- SS3.4 baseline.
- Phases 2-4 complete: new sources mined, FTAL path replaced, PersonaForge wired, Qdrant migrated.
- Event count increased (verify: `SELECT COUNT(*) FROM journey_events WHERE user_id=10`).
- Backend :5000 still running.
- ArangoDB :8529 accessible.

### Deliverables

1. New narratives generated (STAR entries, campaign seeds, skill narratives for April work).
2. `progress/phase_5_NARRATIVE_REVIEW.md` — full-arc cohesion assessment.
3. Journey data auto-approved to ArangoDB knowledge graph.
4. `progress/phase_5_APPROVAL_REPORT.md` — ArangoDB write confirmation.

### Micro-tasks

| # | Task | task_type | Model | Notes |
|---|---|---|---|---|
| 5.1 | Count existing narratives by type | ops | Haiku | Baseline before generation |
| 5.2 | Trigger narrative generation via API | ops | Haiku | `curl -X POST http://localhost:5000/api/journey/narratives -H "user-id: 10"` — may need to check if this is a background job |
| 5.3 | Monitor generation progress | ops | Haiku | Poll until complete |
| 5.4 | Count post-generation narratives | ops | Haiku | Verify increase |
| 5.5 | **Narrative coherence review** | review | **Sonnet** | MODEL SWITCH REQUIRED. Read ALL narratives. Assess: (a) Does the Dec 2025 - Apr 2026 arc tell a coherent story? (b) Are April achievements represented? (c) Are technology progressions logical? (d) Would a hiring manager find this credible? (e) Are there gaps or contradictions? Write `progress/phase_5_NARRATIVE_REVIEW.md`. |
| 5.6 | If coherence gaps found: generate targeted narratives to fill gaps | coding | Haiku | Use LLM to synthesize missing narrative segments. Delegated via FTAL. |
| 5.7 | Auto-approve journey data to ArangoDB | ops | Haiku | `curl -X POST http://localhost:5000/api/journey/approve -H "user-id: 10"` |
| 5.8 | Verify ArangoDB write success | ops | Haiku | Query `ro_journey_events`, `ro_journey_narratives` collections |
| 5.9 | Write `progress/phase_5_APPROVAL_REPORT.md` | docs | Haiku | |
| 5.10 | **Brutal self-review** | review | **Sonnet** | MODEL SWITCH REQUIRED. Write `progress/phase_5_BRUTAL_REVIEW.md`. Focus on: narrative quality, data completeness, ArangoDB consistency. |
| 5.11 | Update JSON companion | ops | Haiku | |

### Narrative coherence criteria (for 5.5)

The full journey must tell this story arc:

1. **Foundation (Dec 2025 - Jan 2026):** Initial hybrid AI gateway setup, RTX 5090 integration, early FTAL harness.
2. **Resume Optimizer Build (Feb - Mar 2026):** Full-stack app genesis via Digital Twin, phases 1-17 through A-grade quality.
3. **Platform Maturation (Mar - Apr 2026):** Architecture hardening, circuit breaker, as-built documentation authority, Opus assessments (83% -> 100%).
4. **Advanced Capabilities (Apr 2026):** Complexity routing, semantic indexing, keyword intelligence, subagent architecture, API docs hub, LOCAL_FIRST framework.
5. **Convergence (Apr 20, 2026):** Resume optimizer roadmap closure, all phases complete, 441 commits in 2 weeks, platform fully operational.

Each phase should have:
- At least 2 STAR-format resume entries
- At least 3 campaign seeds
- Technology progression that builds logically
- Quantified achievements where possible (test counts, assessment scores, commit volumes)

### Quality gate

1. Smoke-pass: all journey API endpoints return valid data after approval.
2. Narrative count increased (new entries for April work).
3. Narrative coherence review on Sonnet: full-arc story is credible and complete.
4. ArangoDB write confirmed (record counts match SQLite).
5. Brutal self-review on Sonnet: 0 P0 items.

### Exit criteria

Narratives generated; full-arc coherence verified; ArangoDB approved; user approves Phase 6.

### PersonaForge learnings to save

Narrative generation batch behavior; coherence review methodology; ArangoDB approval workflow; any LLM quality issues in synthesis; story arc structure for future updates.

---

## Phase 6 — Downstream Consumer Refresh

**Objective.** Trigger rebuilds of all systems that consume journey data: deep career profile, campaign seeds, resume narratives. Verify each downstream system reflects the updated journey.

**Required model:** Haiku (default). Sonnet for brutal review (6.7).

**Pre-phase reassessment.**
- SS3.4 baseline.
- Phase 5 complete: narratives generated, ArangoDB approved.
- All downstream API endpoints responsive.
- ArangoDB journey collections populated and queryable.

### Deliverables

1. Deep career profile rebuilt for user 10.
2. Campaign seed refresh triggered.
3. Resume narratives updated.
4. `progress/phase_6_DOWNSTREAM_REPORT.md` — each system's before/after state.

### Micro-tasks

| # | Task | task_type | Model | Notes |
|---|---|---|---|---|
| 6.1 | Record current deep profile state | ops | Haiku | `curl -s http://localhost:5000/api/deep-profile/build -X POST -H "user-id: 10" -H "Content-Type: application/json" -d '{}'` — check if existing profile exists first |
| 6.2 | Trigger deep profile rebuild | ops | Haiku | `POST /api/deep-profile/build` with user-id 10. This aggregates all sources (projects, LinkedIn, journey, resumes). May be a background job. |
| 6.3 | Monitor deep profile job | ops | Haiku | Poll until complete |
| 6.4 | Verify deep profile includes April data | ops | Haiku | Check that technologies, skills, achievements from April are present in the rebuilt profile. Look for: TaskComplexityAnalyzer, circuit breaker, semantic indexing, keyword equivalency, etc. |
| 6.5 | Refresh campaign analytics | ops | Haiku | `GET /api/campaigns/analytics -H "user-id: 10"` — verify knowledge graph coverage reflects new journey data |
| 6.6 | Verify journey timeline API returns April events | ops | Haiku | `GET /api/journey/timeline -H "user-id: 10"` — confirm events through April 2026 |
| 6.7 | Verify journey skills API shows new technologies | ops | Haiku | `GET /api/journey/skills -H "user-id: 10"` — check for new tech: TaskComplexityAnalyzer, SemanticFileIndexer, MCP global, subagent arch, etc. |
| 6.8 | Verify journey achievements API includes April milestones | ops | Haiku | `GET /api/journey/achievements -H "user-id: 10"` — check for: roadmap closure, 120/120 Opus, Phase 61, etc. |
| 6.9 | Verify graph technology endpoint reflects new data | ops | Haiku | `GET /api/graph/technologies -H "user-id: 10"` |
| 6.10 | Write `progress/phase_6_DOWNSTREAM_REPORT.md` | docs | Haiku | Before/after counts for each system |
| 6.11 | **Brutal self-review** | review | **Sonnet** | MODEL SWITCH REQUIRED. Write `progress/phase_6_BRUTAL_REVIEW.md`. Focus on: data consistency across systems, downstream gaps, credibility of the updated journey to a hiring manager. |
| 6.12 | Final database backup | ops | Haiku | `cp backend/database.db backend/database.db.post-update.2026-04-20` |
| 6.13 | Update JSON companion — mark plan COMPLETE | ops | Haiku | |

### Quality gate

1. Deep profile rebuild returns valid data with April technologies.
2. Campaign analytics shows increased knowledge graph coverage.
3. Journey timeline, skills, achievements APIs all include April data.
4. Brutal self-review on Sonnet: 0 P0 items.

### Exit criteria

All downstream systems reflect updated journey data; deep profile includes April work; campaign analytics updated; journey APIs return April events/skills/achievements; final backup created; plan marked COMPLETE.

### PersonaForge learnings to save

Deep profile rebuild behavior; campaign analytics dependency on journey data; which downstream systems are most sensitive to journey updates; end-to-end data flow confirmation.

---

## Post-plan verification checklist

After Phase 6 completes, verify the entire update succeeded:

- [ ] Journey events for user 10: count significantly higher than 10,316.
- [ ] Latest event date: 2026-04-20 (or latest commit date).
- [ ] Journey sources: new git_commit, local_file, governance, cost_data, personaforge types present.
- [ ] FTAL history mining: reads from ArangoDB, not Qdrant.
- [ ] PersonaForge mining: wired into pipeline, sources appear.
- [ ] Qdrant data: migrated to ArangoDB, originals preserved in SQLite.
- [ ] Narratives: new entries for April work; full-arc story is cohesive.
- [ ] ArangoDB: journey data approved and written.
- [ ] Deep profile: includes April technologies and achievements.
- [ ] Campaign analytics: knowledge graph coverage increased.
- [ ] All journey API endpoints return valid, up-to-date data.
- [ ] Database backups exist: pre-update and post-update.
- [ ] No test regressions in journey test suite.

---

*End of phases 4-6. See entry file for protocols and JSON companion for authoritative state.*
