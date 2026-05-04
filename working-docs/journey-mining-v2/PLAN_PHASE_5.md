# Phase 5: ArangoDB Graph Integration

**Model:** Haiku (mechanical graph writes, schema already defined)
**↑ SWAP TO SONNET only if edge-resolution logic gets complex**
**Estimated scope:** ~200 lines backend, ~80 lines test
**Status:** NOT STARTED
**Depends on:** Phase 4 (cluster heads become milestones)

---

## Objective

Populate the empty `ro_journey_projects` and `ro_journey_milestones` collections. Create edges to existing `ro_skills`, `ro_technologies`, `ro_client_projects`, `ro_business_outcomes`.

## Graph Population Strategy

### Journey Projects (from commit phases + checkpoints)
```
1. Parse commit messages for phase numbers: "feat(phase26):" → project "Phase 26"
2. Parse report titles: "SESSION_CHECKPOINT_2026-04-11" → project milestone
3. Group by project identifier
4. Key: SHA1(f"journey_project:{project_name}")
```

### Journey Milestones (from cluster heads, significance ≥ 3)
```
1. Each high-significance cluster head becomes a milestone vertex
2. Fields: title, description, event_date, technologies[], significance_score
3. Key: SHA1(f"milestone:{event_id}")
```

### Edges
```
ro_milestone_demonstrated_skill: milestone → ro_ai_skills (match technologies by name)
ro_milestone_belongs_to_project: milestone → ro_journey_projects
ro_project_used_skill: project → ro_ai_skills

Cross-references to existing graph:
- milestone.technologies → ro_technologies (name match)
- milestone.description → ro_business_outcomes (embedding similarity from Phase 2)
- milestone context → ro_client_projects (client name appears in event)
```

### Key Generation (consistent with existing arango_client.py)
```python
# Deterministic keys via SHA-1 — idempotent re-runs
milestone_key = hashlib.sha1(f"milestone:{event_id}".encode()).hexdigest()
project_key = hashlib.sha1(f"journey_project:{project_name}".encode()).hexdigest()
```

## Tasks

- [ ] **5.1** Create `backend/journey_graph_writer.py` — reads high-significance events, writes to ArangoDB
- [ ] **5.2** Implement project extraction: parse phase numbers, group related events
- [ ] **5.3** Implement milestone creation: significance ≥ 3 cluster heads → `ro_journey_milestones`
- [ ] **5.4** Implement skill edge creation: match `event.technologies` against `ro_ai_skills`
- [ ] **5.5** Implement cross-reference edges: embedding similarity milestone↔`ro_business_outcomes`
- [ ] **5.6** Add `POST /api/journey/sync-graph` route (background job)
- [ ] **5.7** Add `GET /api/journey/graph-stats` — vertex/edge counts for journey subgraph
- [ ] **5.8** Idempotency: SHA-1 deterministic keys, upsert semantics

## TDD Contract

| Test | Mutation Target | Pass Criteria |
|------|----------------|---------------|
| `test_milestones_created` | Remove INSERT into ro_journey_milestones | Must fail |
| `test_skill_edges_created` | Remove edge creation for technologies | Must fail |
| `test_deterministic_keys` | Change key to random UUID | Must fail: re-run duplicates |
| `test_only_high_significance` | Filter ≥3 → ≥1 | Must fail |
| `test_cross_reference_edges` | Remove client name matching | Must fail |
| `test_idempotent_rerun` | Run sync twice, count vertices | Must fail if doubled |

## Acceptance Criteria

- `ro_journey_milestones`: 200-500 vertices
- `ro_journey_projects`: 15-30 vertices
- Edges: 500-2000 across all edge types
- Cross-references: ≥ 50 edges to `ro_technologies`, `ro_client_projects`
- Re-running produces identical graph (idempotent)
