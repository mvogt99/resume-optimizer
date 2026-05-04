# Phase 6: Incremental Update + Narrative Refresh

**Model:** ↑ SWAP TO SONNET (merge strategy, staleness detection, narrative re-synthesis)
**Estimated scope:** ~250 lines backend, ~80 lines test, ~60 lines frontend
**Status:** NOT STARTED
**Depends on:** All prior phases (1-5)

---

## Objective

Enable true incremental updates: mine only new content since last run, merge into existing corpus with semantic dedup, and flag stale narratives for refresh.

## Incremental Pipeline

```
1. Read watermarks from latest journey_mining_runs (Phase 1)
2. Fetch only new sources:
   - Git: --since={watermark}
   - Files: mtime > watermark
   - ArangoDB: created_at > watermark
3. For each new source:
   a. Generate embedding (Phase 2)
   b. Search existing sources for semantic match (cosine > 0.92)
   c. If match: UPDATE existing source (merge content, bump updated_at)
   d. If no match: INSERT new source
4. Re-score affected events only (Phase 3)
5. Re-cluster only affected clusters (Phase 4)
6. Sync affected milestones to graph (Phase 5)
7. Flag narratives referencing affected events as stale
```

## Semantic Merge Logic

```python
def merge_or_insert_source(new_source, user_id):
    """Merge new source with existing if semantically similar, else insert."""
    embedding = embed(new_source["content_preview"])

    # Search existing sources for semantic match
    similar = find_similar(
        collection="journey_sources",  # ArangoDB-embedded copy
        query_embedding=embedding,
        threshold=0.92,
        limit=3
    )

    if similar:
        best = similar[0]
        # Merge: keep original, append new content as addendum
        merged_text = best["full_text"] + "\n\n---\n" + new_source["full_text"]
        update_source(best["id"], {
            "full_text": merged_text,
            "content_preview": merged_text[:500],
            "updated_at": now()
        })
        return "merged", best["id"]
    else:
        insert_source(new_source)
        return "inserted", new_source["id"]
```

## Narrative Staleness

### Schema Changes
```sql
ALTER TABLE journey_narratives ADD COLUMN is_stale INTEGER DEFAULT 0;
ALTER TABLE journey_narratives ADD COLUMN stale_reason TEXT DEFAULT '';
ALTER TABLE journey_narratives ADD COLUMN source_event_count INTEGER DEFAULT 0;
```

### Detection Logic
```python
def check_narrative_staleness(narrative, new_event_embeddings):
    """Flag narrative as stale if new events are semantically related."""
    narrative_embedding = embed(narrative["content"])

    for event_emb in new_event_embeddings:
        similarity = cosine(narrative_embedding, event_emb)
        if similarity > 0.85:
            mark_stale(narrative["id"],
                       reason=f"New related event (similarity {similarity:.2f})")
            return True
    return False
```

### Narrative Refresh
```python
def refresh_narrative(narrative_id, user_id):
    """Re-synthesize a narrative from its updated source events."""
    narrative = get_narrative(narrative_id)
    source_event_ids = json.loads(narrative["source_event_ids"])
    events = get_events_by_ids(source_event_ids, user_id)

    # Also include new high-significance events from same time period
    date_range = (min(e["event_date"] for e in events),
                  max(e["event_date"] for e in events))
    new_events = get_events_in_range(
        date_range, user_id, min_significance=3
    )

    all_events = events + [e for e in new_events if e["id"] not in source_event_ids]

    # LLM synthesis (RTX 5090, $0)
    prompt = build_narrative_refresh_prompt(narrative, all_events)
    new_content = call_llm(prompt, task_type="reasoning", max_tokens=2048)

    update_narrative(narrative_id, {
        "content": new_content,
        "is_stale": 0,
        "stale_reason": "",
        "source_event_ids": json.dumps([e["id"] for e in all_events]),
        "source_event_count": len(all_events)
    })
```

## Tasks

- [ ] **6.1** Update `_mining_worker` to read watermarks when opts doesn't override
- [ ] **6.2** Implement semantic merge in `_store_source`: embed, search existing, merge if similar
- [ ] **6.3** Implement incremental rescore: only affected events
- [ ] **6.4** Implement incremental re-cluster: only affected date ranges
- [ ] **6.5** Implement incremental graph sync: only changed milestones
- [ ] **6.6** Add staleness columns migration, staleness detection after mining
- [ ] **6.7** Update `get_narratives()` to return staleness info
- [ ] **6.8** Add `POST /api/journey/narratives/<id>/refresh` endpoint
- [ ] **6.9** Frontend: stale indicator on narratives, "Refresh" button
- [ ] **6.10** Update criteria panel: "Incremental (since last run)" default option

## TDD Contract

| Test | Mutation Target | Pass Criteria |
|------|----------------|---------------|
| `test_incremental_only_new` | Remove watermark filtering | Must fail |
| `test_semantic_merge_updates` | Remove similarity search | Must fail: should update not insert |
| `test_staleness_detected` | Remove staleness check | Must fail |
| `test_incremental_rescore_targeted` | Rescore all instead of affected | Must fail |
| `test_refresh_uses_updated_events` | Feed old events to LLM | Must fail |
| `test_watermark_advances` | Don't update watermark | Must fail |

## Acceptance Criteria

- Incremental with 10 new commits: < 30 seconds
- Semantic merge correctly identifies 0 matches for genuinely novel content
- Stale narratives flagged in same mining run
- Refreshed narratives incorporate new events
- Frontend shows "last updated: {date}" + "Incremental update available"

**After Phase 6 tests pass:** ↓ SWAP BACK TO HAIKU for cleanup
