# Phase 3: Significance Scoring

**Model:** Haiku (rule-based scoring, no complex reasoning)
**Estimated scope:** ~180 lines backend, ~60 lines test
**Status:** NOT STARTED
**Depends on:** Nothing (can run parallel with Phase 1)

---

## Objective

Add `significance_score` (1-5) to every journey event. Replace broken `_classify_event()` with multi-signal scoring. Surface only top ~500 events to consumers.

## Scoring Algorithm

```python
def score_event(source: dict, event: dict) -> int:
    """Return 1-5 significance score."""
    score = 1  # baseline

    # Source type signals
    if source["source_type"] == "git_commit":
        msg = source["title"].lower()
        if msg.startswith("feat"):       score += 2  # new feature
        elif msg.startswith("fix"):      score += 1  # bug fix
        elif msg.startswith("refactor"): score += 1
        # docs, test, chore → +0 (stay at baseline)
    elif source["source_type"] == "arango":
        score += 1  # curated knowledge
    elif source["source_type"] == "governance":
        score += 2  # governance achievement
    elif source["classification"] == "report":
        if "CHECKPOINT" in source["title"].upper():
            score += 2  # session checkpoint = phase completion
        else:
            score += 1

    # Content signals
    text = (source.get("full_text") or "").lower()
    if any(w in text for w in ["complete", "deployed", "production", "shipped", "launched"]):
        score += 1
    if any(w in text for w in ["critical", "breakthrough", "first time", "milestone"]):
        score += 1

    # Technology breadth bonus
    techs = event.get("technologies") or []
    if len(techs) >= 5:
        score += 1

    return min(score, 5)
```

## Improved Classification (replaces `_classify_event`)

```python
def classify_event(source: dict) -> str:
    """Structured classification using source metadata."""
    stype = source.get("source_type", "")
    classification = source.get("classification", "")
    title = source.get("title", "").lower()

    if stype == "git_commit":
        if title.startswith("feat"):     return "achievement"
        if title.startswith("fix"):      return "fix"
        if title.startswith("test"):     return "development"
        if title.startswith("docs"):     return "documentation"
        if title.startswith("refactor"): return "development"
        return "development"

    if stype == "governance":            return "governance"
    if classification == "teaching":     return "learning"
    if classification == "learning":     return "learning"
    if classification == "report":       return "milestone"
    if classification == "coordinator":  return "development"
    if classification == "task_spec":    return "planning"

    return "development"
```

## Schema Changes

```sql
ALTER TABLE journey_events ADD COLUMN significance_score INTEGER DEFAULT 1;
ALTER TABLE journey_events ADD COLUMN cluster_id TEXT DEFAULT '';
ALTER TABLE journey_events ADD COLUMN is_cluster_head INTEGER DEFAULT 0;
```

## Tasks

- [ ] **3.1** Add 3 new columns to journey_events (migration in models.py)
- [ ] **3.2** Create `backend/journey_scorer.py` — `score_event()` + `classify_event()`
- [ ] **3.3** Integrate scoring into `_build_timeline()` — score each event during construction
- [ ] **3.4** Add `POST /api/journey/rescore` — re-scores all events without re-mining
- [ ] **3.5** Update `get_timeline()` to accept `min_significance` filter (default: 1)
- [ ] **3.6** Frontend: significance badges on JourneyTimeline + filter dropdown
- [ ] **3.7** Replace `_classify_event()` calls with new `classify_event()`

## TDD Contract

| Test | Mutation Target | Pass Criteria |
|------|----------------|---------------|
| `test_feat_commit_scores_3` | `score += 2` → `score += 0` for feat | Must fail |
| `test_docs_commit_scores_1` | docs score → `+= 2` | Must fail |
| `test_governance_scores_high` | Remove governance bonus | Must fail |
| `test_max_score_capped_at_5` | Remove `min(score, 5)` | Must fail |
| `test_timeline_filters_by_significance` | Remove WHERE for min_significance | Must fail |
| `test_classify_feat_is_achievement` | Return "development" for feat | Must fail |

## Acceptance Criteria

- Distribution: ~500 at score 3+, ~1500 at 2+, all 10K at 1+
- `GET /api/journey/timeline?min_significance=3` returns ≤ 500 events
- No event scores 0 (minimum is 1)
- Rescore completes < 10 seconds for 10K events
