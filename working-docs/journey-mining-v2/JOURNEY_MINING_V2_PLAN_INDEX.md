# Journey Mining v2 — Production Quality Plan

**Created:** 2026-04-15 | **Status:** PLANNING
**Default model:** Haiku | **Escalation gates marked inline**
**Approach:** TDD + mutation-verify on every phase. No claims without evidence.

> Detail for each phase is in `PLAN_PHASE_{N}.md`. This file is the index + cross-cutting concerns.

---

## Overview

Transform the journey mining corpus from a 10K-event file inventory into a production-quality career knowledge base. Six phases across four layers, each independently testable and deployable.

**Targets:**
- Significance-scored events with top ~500 surfaced to consumers
- ArangoDB-native embeddings (384D) replacing Qdrant dependency
- Full graph integration (ro_journey_* populated, edges to existing entities)
- Incremental update with watermarks and semantic merge
- 10/10 production quality: every behavior mutation-verified

---

## Phase Index

| Phase | Title | Model | File | Depends On |
|-------|-------|-------|------|------------|
| 1 | Watermarks + Mining Runs | Haiku | [PLAN_PHASE_1.md](PLAN_PHASE_1.md) | — |
| 2 | ArangoDB Embedding Pipeline | **Sonnet** | [PLAN_PHASE_2.md](PLAN_PHASE_2.md) | Phase 1 |
| 3 | Significance Scoring | Haiku | [PLAN_PHASE_3.md](PLAN_PHASE_3.md) | — (parallel with 1) |
| 4 | Semantic Dedup + Clustering | **Sonnet** | [PLAN_PHASE_4.md](PLAN_PHASE_4.md) | Phases 2 + 3 |
| 5 | ArangoDB Graph Integration | Haiku (↑Sonnet if needed) | [PLAN_PHASE_5.md](PLAN_PHASE_5.md) | Phase 4 |
| 6 | Incremental Update + Narrative Refresh | **Sonnet** | [PLAN_PHASE_6.md](PLAN_PHASE_6.md) | All prior |

**Phases 1 and 3 can run in parallel** (no dependency between them).

---

## Model Cost Strategy

| Phase | Default | Escalation Trigger | Escalated |
|-------|---------|-------------------|-----------|
| 1 | **Haiku** | — | — |
| 2 | **Sonnet** | Complex AQL optimization | **Opus** (user approval required) |
| 3 | **Haiku** | — | — |
| 4 | **Sonnet** | Cluster quality issues | **Opus** (user approval required) |
| 5 | **Haiku** | Edge resolution ambiguity | **Sonnet** |
| 6 | **Sonnet** | Merge strategy edge cases | **Opus** (user approval required) |

**Rule:** User must approve every Sonnet→Opus escalation. Haiku→Sonnet pre-approved at phase boundaries. RTX 5090 handles all LLM synthesis ($0 cost).

---

## File Size Compliance (500-line limit)

| New File | Est. Lines | Notes |
|----------|-----------|-------|
| `journey_scorer.py` | ~180 | Self-contained |
| `arango_embedding_service.py` | ~200 | Self-contained |
| `journey_clustering.py` | ~250 | May split: `+ journey_cluster_synthesis.py` |
| `journey_graph_writer.py` | ~200 | Self-contained |

---

## Regression Safety

Each phase tests its own behavior AND verifies no regression in:
- Existing `journey_miner` functionality (mine, timeline, skills, achievements, narratives)
- Existing `arango_client.py` graph operations
- Frontend rendering (JourneyMiner, JourneyTimeline, JourneySkills, JourneyNarratives)

---

## Qdrant Deprecation Path

Phase 2 introduces ArangoDB embeddings. Qdrant is NOT removed — it continues serving gateway. Journey miner's `_scan_qdrant()` remains but is deprioritized. Full Qdrant retirement is separate.

---

## Definition of Done: 10/10 Production Quality

ALL must be true:

1. **Every test mutation-verified**: Break production line → test fails → restore → passes. No exceptions.
2. **Significance scoring accurate**: Manual review of 20 random events per score level (1-5).
3. **Semantic dedup effective**: 10K → ~3K visible after clustering. Top 500 have no semantic duplicates (spot-check 50).
4. **Graph populated**: `ro_journey_milestones` 200-500 vertices. 50+ edges to existing entities. Traversal queries work.
5. **Incremental works**: 10 new commits via incremental < 30s. No duplicates.
6. **Narratives reflect reality**: Stale detected. Refreshed incorporates new events. 5 manual reviews.
7. **All consumers served**: Resume, campaign, career advisory, deep profile all benefit.
8. **No regression**: All pre-existing tests pass. Frontend renders. Full mine still works.
9. **Embeddings durable**: 384D in ArangoDB. Similarity search correct. Service failure graceful.
10. **Watermarks reliable**: Run history queryable. Monotonic. No data missed or double-counted.
