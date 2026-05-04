# Phase 4: Semantic Dedup + Event Clustering

**Model:** ↑ SWAP TO SONNET (semantic similarity logic, clustering algorithm, LLM prompts)
**Estimated scope:** ~300 lines backend (may split), ~100 lines test
**Status:** NOT STARTED
**Depends on:** Phase 2 (ArangoDB embeddings) + Phase 3 (significance scores)

---

## Objective

Cluster semantically similar events and generate a canonical summary per cluster. Uses Phase 2 ArangoDB embeddings for similarity search.

## Algorithm

```
1. For each event with significance_score >= 2:
   a. Get embedding from ArangoDB (or generate if missing)
   b. Find similar events (cosine > 0.88) within ±7 days
   c. If cluster found: assign cluster_id, mark highest-scored as cluster_head
   d. If cluster has 3+ members: generate LLM synthesis for cluster_head description

2. Cluster head inherits:
   - Combined source_ids from all members
   - Union of technologies from all members
   - Max significance_score from all members
   - LLM-synthesized description (RTX 5090, $0 cost)
```

## Clustering Rules

| Rule | Threshold | Rationale |
|------|-----------|-----------|
| Cosine similarity | ≥ 0.88 | Catches paraphrases, not just near-identical |
| Time window | ±7 days | Same project phase, different days |
| Same category required | Yes | Don't merge "fix" with "achievement" |
| Min cluster for LLM synthesis | 3 | Don't waste LLM calls on pairs |
| Max cluster size | 20 | Prevent mega-clusters |

## LLM Synthesis Prompt (RTX 5090)

```
Summarize these related career events into one concise achievement statement.
Focus on: what was accomplished, technologies used, and business impact.
Write 2-3 sentences in first person, suitable for a resume or LinkedIn post.

Events:
{event_titles_and_descriptions}

Return ONLY the summary text, no JSON, no markup.
```

## Implementation: Union-Find for Cluster Assignment

```python
class UnionFind:
    """Disjoint set for merging overlapping similarity groups."""

    def __init__(self):
        self.parent = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        px, py = self.find(x), self.find(y)
        if px != py:
            self.parent[px] = py

# Usage: for each pair (event_a, event_b) with cosine > 0.88:
#   uf.union(event_a.id, event_b.id)
# Then group by uf.find(event.id) to get clusters
```

## Tasks

- [ ] **4.1** Create `backend/journey_clustering.py` — `cluster_events(user_id)` function
- [ ] **4.2** Implement similarity search: for each event, find neighbors via ArangoDB embedding
- [ ] **4.3** Implement union-find cluster assignment
- [ ] **4.4** Implement cluster head selection: highest significance_score
- [ ] **4.5** Implement LLM synthesis for 3+ member clusters (RTX 5090 via `call_llm`)
- [ ] **4.6** Add `POST /api/journey/cluster` route (background job)
- [ ] **4.7** Update timeline view to collapse clusters (show head, expandable)
- [ ] **4.8** Frontend: cluster indicator + expand/collapse UI

## TDD Contract

| Test | Mutation Target | Pass Criteria |
|------|----------------|---------------|
| `test_similar_events_clustered` | Threshold 0.88→0.01 | Must fail: too many clustered |
| `test_different_categories_not_clustered` | Remove category check | Must fail |
| `test_time_window_enforced` | ±7→±365 | Must fail |
| `test_cluster_head_highest_scored` | Select MIN not MAX | Must fail |
| `test_synthesis_only_for_3plus` | Threshold→1 | Must fail |
| `test_max_cluster_size_20` | Remove cap | Must fail |
| `test_head_inherits_sources` | Remove source merge | Must fail |

## Acceptance Criteria

- 10,316 → ~3,000 visible after clustering, ~500 at significance ≥ 3
- Each cluster: exactly 1 head, 0+ members
- LLM-synthesized heads have coherent, resume-quality descriptions
- Clustering completes < 3 minutes

**After Phase 4 tests pass:** ↓ SWAP BACK TO HAIKU
