# Phase 4 Developer Guide: Semantic Dedup + Event Clustering

## Quick Start for Phase 4 Implementation

**You are building on:** Phase 1 (watermarks) + Phase 3 (significance scoring)
**Your deliverable:** Semantic deduplication and event clustering
**Contract:** TDD mutation-verified, 10/10 quality with brutal honest assessment

---

## What You're Building

### Core Problem
After Phase 1 mines sources and Phase 3 scores them, the timeline contains many similar/duplicate events:
- Same git commit from multiple sources (workdir + Qdrant + git history)
- Multiple mentions of same project milestone
- Similar technologies mentioned across different contexts

**Your solution:**
1. **Semantic Dedup**: Find and merge duplicate sources before timeline building
2. **Event Clustering**: Group similar events within 7-day windows
3. **Cluster Heads**: Mark high-significance event as cluster representative

### Expected Output

#### journey_events (after Phase 4)
```
id                   INTEGER
title                TEXT
significance_score   INTEGER (1-5, from Phase 3)
cluster_id           INTEGER (new: which cluster this belongs to)
is_cluster_head      BOOLEAN (new: is this the representative?)
created_at           TIMESTAMP
```

#### journey_clusters (new table)
```
id                   INTEGER PRIMARY KEY
user_id              INTEGER
cluster_date         TEXT (YYYY-MM-DD: first event in window)
cluster_type         TEXT ('milestone' | 'achievement' | 'fix' | 'learning')
representative_event_id  INTEGER (highest significance in cluster)
event_count          INTEGER
created_at           TIMESTAMP
```

---

## Input Data Contract

**From Phase 3:**
- journey_sources: source_type, title, full_text, created_at
- journey_events: title, significance_score, source_ids (JSON list)

**Your job:** Use significance_score (1-5) to decide which events to keep as cluster heads.

---

## Semantic Dedup Algorithm

### Step 1: Identify Potential Duplicates

Group sources by:
1. **Exact match**: title + source_type + user_id → definitely duplicate
2. **Fuzzy match**: Similar titles (>80% string similarity) within 1-day window → likely duplicate

```python
def find_duplicates(sources: list) -> list[tuple]:
    """Return list of (source_id, duplicate_source_id) pairs."""
    duplicates = []

    # Exact match
    seen = {}
    for source in sources:
        key = (source["title"], source["source_type"], source["user_id"])
        if key in seen:
            duplicates.append((seen[key], source["id"]))
        else:
            seen[key] = source["id"]

    # Fuzzy match (80% threshold)
    for i, s1 in enumerate(sources):
        for s2 in sources[i+1:]:
            if same_day(s1["created_at"], s2["created_at"]):
                if string_similarity(s1["title"], s2["title"]) > 0.8:
                    duplicates.append((s1["id"], s2["id"]))

    return duplicates
```

**TDD Test:**
```python
def test_exact_match_found():
    """Break: Don't check for exact matches
       Result: Duplicates not detected → Test fails ✓
    """
    insert_sources([
        {"title": "feat: Auth", "source_type": "git_commit", "user_id": 1},
        {"title": "feat: Auth", "source_type": "git_commit", "user_id": 1},
    ])
    dups = find_duplicates(...)
    assert len(dups) == 1
```

### Step 2: Merge Duplicates

Keep higher-significance source, merge metadata:
```python
def merge_duplicates(sources: list, duplicates: list) -> list:
    """Keep high-score source, merge low-score source into it."""
    to_remove = set()
    merges = {}

    for src_id, dup_id in duplicates:
        src = sources[src_id]
        dup = sources[dup_id]

        # Keep higher significance
        if src["significance_score"] >= dup["significance_score"]:
            keep, remove = src_id, dup_id
        else:
            keep, remove = dup_id, src_id

        to_remove.add(remove)
        if keep not in merges:
            merges[keep] = {"source_ids": []}
        merges[keep]["source_ids"].append(remove)

    # Return sources with merges applied
    return [s for s in sources if s["id"] not in to_remove]
```

**TDD Test:**
```python
def test_keep_higher_significance():
    """Break: Always keep first source
       Result: Low-score source kept instead of high → Test fails ✓
    """
    sources = [
        {"id": 1, "title": "feat: Auth", "significance_score": 2},
        {"id": 2, "title": "feat: Auth", "significance_score": 4},
    ]
    merged = merge_duplicates(sources, [(1, 2)])
    assert merged[0]["id"] == 2  # Keep high-score
```

---

## Event Clustering Algorithm

### Step 1: Group by 7-Day Windows

```python
def cluster_events(events: list, window_days=7) -> dict:
    """Group events into 7-day clusters.

    Returns: {cluster_id: [event_ids]}
    """
    from datetime import timedelta

    clusters = {}
    cluster_counter = 1

    sorted_events = sorted(events, key=lambda e: e["event_date"])

    current_cluster = []
    current_window_start = None

    for event in sorted_events:
        event_date = parse_date(event["event_date"])

        if current_window_start is None:
            current_window_start = event_date

        # Check if within window
        window_end = current_window_start + timedelta(days=window_days)
        if event_date <= window_end:
            current_cluster.append(event["id"])
        else:
            # Save cluster and start new one
            clusters[cluster_counter] = current_cluster
            cluster_counter += 1
            current_window_start = event_date
            current_cluster = [event["id"]]

    # Save last cluster
    if current_cluster:
        clusters[cluster_counter] = current_cluster

    return clusters
```

**TDD Test:**
```python
def test_7day_window():
    """Break: Use 3-day window instead of 7
       Result: Events split incorrectly → Test fails ✓
    """
    events = [
        {"id": 1, "event_date": "2026-04-01"},
        {"id": 2, "event_date": "2026-04-05"},
        {"id": 3, "event_date": "2026-04-10"},
    ]
    clusters = cluster_events(events, window_days=7)
    # Events 1 & 2 in same cluster (5 days apart)
    # Event 3 in new cluster (9 days from event 1)
    assert 1 in clusters[1] and 2 in clusters[1]
    assert 3 not in clusters[1]
```

### Step 2: Mark Cluster Heads

Within each cluster, keep highest-significance event as head:

```python
def mark_cluster_heads(events: list, clusters: dict) -> dict:
    """Mark highest-significance event in each cluster as head.

    Returns: {event_id: is_cluster_head}
    """
    heads = {}

    for cluster_id, event_ids in clusters.items():
        cluster_events = [e for e in events if e["id"] in event_ids]

        # Find highest significance
        head = max(cluster_events, key=lambda e: e["significance_score"])
        heads[head["id"]] = True

        # All others not heads
        for event in cluster_events:
            if event["id"] != head["id"]:
                heads[event["id"]] = False

    return heads
```

**TDD Test:**
```python
def test_highest_significance_is_head():
    """Break: Mark lowest-significance as head
       Result: Wrong event marked → Test fails ✓
    """
    cluster_1_events = [
        {"id": 1, "significance_score": 2},
        {"id": 2, "significance_score": 4},
        {"id": 3, "significance_score": 1},
    ]
    heads = mark_cluster_heads(cluster_1_events, {1: [1, 2, 3]})
    assert heads[2] is True  # Score 4 is highest
    assert heads[1] is False
    assert heads[3] is False
```

---

## Database Integration

### Phase 4 Schema Changes

```sql
-- Add to journey_events table
ALTER TABLE journey_events ADD COLUMN cluster_id INTEGER DEFAULT NULL;
ALTER TABLE journey_events ADD COLUMN is_cluster_head BOOLEAN DEFAULT 0;

-- Create journey_clusters table
CREATE TABLE journey_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    cluster_date TEXT,  -- YYYY-MM-DD of first event
    cluster_type TEXT,  -- classification from Phase 3
    representative_event_id INTEGER,
    event_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (representative_event_id) REFERENCES journey_events (id)
);
```

### Mutation-Verified Integration Test

```python
def test_phase3_to_phase4_flow():
    """Break: Don't cluster events
       Result: No cluster_id set → Test fails ✓
    """
    # Setup: Insert Phase 3 events with significance scores
    insert_events([
        {"id": 1, "title": "feat: Auth", "significance_score": 4, "event_date": "2026-04-01"},
        {"id": 2, "title": "feat: Auth", "significance_score": 2, "event_date": "2026-04-02"},
    ])

    # Run Phase 4 clustering
    clusters = cluster_events(...)
    heads = mark_cluster_heads(...)

    # Update database
    for event_id, cluster_id in clusters.items():
        for event_id in cluster_events:
            update_event(event_id, cluster_id=cluster_id, is_cluster_head=heads[event_id])

    # Verify
    assert get_event(1)["cluster_id"] is not None
    assert get_event(1)["is_cluster_head"] is True  # Higher score
    assert get_event(2)["is_cluster_head"] is False
```

---

## TDD Structure for Phase 4

### Test Files to Create

1. **test_journey_phase4_dedup.py** (15+ tests)
   - Exact match detection
   - Fuzzy match (80% threshold)
   - Merge by significance
   - Source tracking

2. **test_journey_phase4_clustering.py** (15+ tests)
   - 7-day window grouping
   - Cluster head selection
   - Multi-cluster scenarios
   - Edge cases (single event clusters, overlapping dates)

3. **test_journey_phase3_phase4_integration.py** (3+ tests)
   - Phase 3 events → Phase 4 clustering
   - Cluster_id persisted correctly
   - Cluster table populated

4. **test_journey_phase4_performance.py** (2+ tests)
   - Dedup 1000 events <2s
   - Cluster 1000 events <1s

### Target Quality: 10/10

- **35+ tests** total
- **100% mutation verification** (each test breaks on one specific code change)
- **Integration verified** (Phase 3 → Phase 4)
- **Performance validated** (O(n) or O(n log n) for sort)
- **Brutal honest assessment** of each piece

---

## Similarity Scoring (for Fuzzy Match)

Use Levenshtein distance or cosine similarity:

```python
def string_similarity(s1: str, s2: str) -> float:
    """Return 0.0-1.0 similarity score."""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

def same_day(date1: str, date2: str) -> bool:
    """Check if dates are within 24 hours."""
    from datetime import timedelta, datetime
    d1 = datetime.fromisoformat(date1)
    d2 = datetime.fromisoformat(date2)
    return abs((d1 - d2).days) <= 1
```

---

## Gotchas & Pitfalls

1. **Cluster ordering**: Sort events by event_date FIRST, then group by windows
   - Mutation check: Reverse sort order → clusters wrong dates

2. **Significance tie-breaking**: If two events in cluster have same score, keep the earlier one
   - Mutation check: Keep later one → test fails

3. **User isolation**: Dedup/cluster by user_id, never cross-user
   - Mutation check: Remove user_id filter → user 1 dupes merged with user 2

4. **Window boundaries**: 7-day window = inclusive on both ends
   - Mutation check: Change to 6-day → boundary events incorrectly split

---

## Success Criteria

✅ 35+ tests, all passing
✅ 100% mutation verification (each test catches one specific break)
✅ Integration test: Phase 3 scores → Phase 4 clusters
✅ Performance: 1000 events in <2s
✅ Brutal honest assessment: 10/10 verified

---

## Next: Phase 5-6

After Phase 4 (10/10):
- **Phase 5**: ArangoDB graph integration (write clusters to knowledge graph)
- **Phase 6**: Incremental updates + narrative refresh (use watermarks + clusters)

**You are here:** Phase 4 development with TDD + mutation verification
