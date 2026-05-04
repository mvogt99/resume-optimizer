# AI Journey Knowledge Mining — Deep Analysis

**Date:** 2026-04-15
**Author:** Claude Opus 4.6 (analysis), reviewed by user (Mike Vogt)
**Status:** Reference document — informs PLAN.md

---

## Part 1: Can the User Do an Incremental Update Today?

**Short answer: No.** The current architecture is mine-everything-or-nothing.

`start_mining()` → `_mining_worker()` always runs the full pipeline: harvest all local files, scan all ArangoDB docs, parse all git history (back to 2025-12-01 hardcoded — recently made configurable via `since_date`), run all 7 enrichment miners, then deduplicate and rebuild the entire timeline.

`_deduplicate()` uses SHA-256 content hashes — it catches exact byte-identical duplicates, but that's it. Two documents describing the same achievement in different words? Both survive. A git commit message and a teaching doc about the same incident? Both survive as separate events.

`_store_source()` does a `SELECT ... WHERE content_hash = ?` check — so re-running mining won't create duplicate *sources* if the file content hasn't changed. But if the file content *has* changed (even whitespace), you get a new source entry alongside the old one, and both generate events.

The criteria panel added on 2026-04-15 gives date-range and scope filtering, which gets partway there. A user could set `since_date` to the last mining date, select specific sources, and hit "Start Mining." But this creates **additive-only** new events without merging into the existing corpus. There's no:
- Reconciliation of new events against existing ones
- Semantic dedup across the old + new corpus
- Timeline re-synthesis that incorporates new data into existing narrative arcs
- Any concept of "last mined at" watermark

---

## Part 2: What Would a Real Incremental Update Architecture Look Like?

### Layer 1 — Source Watermarking (Mechanical, Straightforward)

Each source type needs a "high-water mark" — the latest timestamp/commit-hash/document-key already ingested.

- **Git**: `git log --since={last_commit_date}` — trivial, already parameterized
- **Local files**: `os.path.getmtime(fpath) > last_harvest_timestamp` — file mtime filtering
- **ArangoDB**: `FOR doc IN collection FILTER doc.created_at > @watermark` — AQL filter
- **FTAL history**: same pattern, filter by timestamp
- **Enrichment sources**: most pull from ArangoDB/PersonaForge which have timestamps

Watermark stored in `journey_mining_runs` table: `{id, user_id, started_at, completed_at, sources_used, events_added, opts_json}`. This table doesn't exist today.

### Layer 2 — Semantic Deduplication (Hard, Requires Embedding Infrastructure)

1. **Near-duplicate detection**: Two sources describing the same thing in different words. Requires embedding similarity (cosine > 0.92 threshold). Infrastructure exists (gateway has all-MiniLM-L6-v2 + Qdrant) but journey_miner doesn't use it for dedup. **Decision: Build ArangoDB-native embedding pipeline, retire Qdrant dependency.**

2. **Event consolidation**: Same real-world event appears from multiple sources (git commit + report file + learning entry + FTAL history). All generate separate `journey_events`. Semantic dedup would cluster and merge.

3. **Narrative invalidation**: When new events are added, existing narratives may become stale. No mechanism to flag this.

### Layer 3 — Merge Strategy

Options when new-event-A is semantically similar to existing-event-B:
- **Tiered approach (selected)**: Keep all raw events/sources, add `significance_score` (1-5). Timeline/narrative views surface top ~500 high-scoring events. Raw data preserved for re-analysis. Event clusters get a synthesized canonical summary.

---

## Part 3: Quality Assessment of the Existing Corpus

### Raw Numbers
- **10,316 events** — 81% classified as "milestone" (meaningless — keyword-match on "complete"/"pass")
- **12,086 sources** — 9,878 local files (essentially every .md/.txt/.json in workdir/)
- **670 git commits** — highest-quality source, but stored flat without phase grouping
- **100 narratives** — LLM-generated from undifferentiated input
- **0 journey graph docs** — `ro_journey_projects` and `ro_journey_milestones` both empty

### Quality Issues

| Issue | Severity | Root Cause |
|-------|----------|------------|
| 81% "milestone" classification | HIGH | `_classify_event()` keyword-matches "complete"/"pass" — too broad |
| Raw JSON in event descriptions | HIGH | `content_preview[:500]` stores raw content, not extracted meaning |
| No semantic dedup | HIGH | SHA-256 only catches byte-identical duplicates |
| No significance scoring | MEDIUM | All events weighted equally regardless of career impact |
| No cross-reference to graph | MEDIUM | Journey events exist in SQLite silo, `ro_journey_*` empty |
| No embeddings on events | MEDIUM | Can't query "similar to X" or detect clusters |
| Git commits ungrouped | LOW | No concept of "these commits belong to Phase 26" |
| Enrichment data thin | LOW | FTAL: 500, governance: 17, cost: 23 — adequate |

### Signal-to-Noise Assessment

The corpus has **breadth but not depth**. It ingested everything indiscriminately, classified poorly, didn't deduplicate semantically, and didn't cross-reference with the structured knowledge already in ArangoDB (`ro_skills`: 6,130; `ro_business_outcomes`: populated; `ro_client_projects`: 6).

The raw material is there — 12K sources spanning 5 months of intense AI development — but needs a significant quality pass.

---

## Part 4: What Would Make This Production-Quality?

1. **Tiered significance scoring** — Score sources 1-5 on career relevance. Only surface high-scoring events.
2. **Event clustering with LLM** — Group related events (same phase/feature/week), generate synthesis per cluster.
3. **ArangoDB graph integration** — Populate `ro_journey_projects`, `ro_journey_milestones`, create edges to `ro_skills`, `ro_technologies`, `ro_client_projects`, `ro_business_outcomes`.
4. **ArangoDB-native embeddings** — Generate 384D vectors via all-MiniLM-L6-v2, store in ArangoDB documents. Replace Qdrant for journey operations.
5. **Incremental with watermarks** — Store high-water mark per source type, only fetch new content, merge with semantic similarity.
6. **Narrative staleness tracking** — Flag narratives needing refresh when related events arrive.

---

## Infrastructure Available (No New Dependencies Required)

| Component | Location | Status |
|-----------|----------|--------|
| Embedding model (all-MiniLM-L6-v2) | `gateway/app/services/embedding_service.py` | Running, GPU-accelerated |
| ArangoDB (94 collections) | localhost:8529, `hybrid_ai` db | Running, 182K+ docs |
| Named graph `ro_knowledge_graph` | 21 vertex + 19 edge collections | Initialized, journey colls empty |
| Batch job system | `backend/batch_jobs.py` | Running, supports progress tracking |
| LLM (RTX 5090) | port 8021, vLLM | Running, Qwen3-Coder-30B |
| FTAL harness | port 8000, `/api/harness/run` | Running |
