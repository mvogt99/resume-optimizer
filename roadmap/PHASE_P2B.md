# Phase P2-B: Graph Traceability Edges

**Branch:** `feature/ro-phase-P2B-graph-traceability`
**Model:** Sonnet
**Addresses:** Finding F10 (R10)
**Status:** PENDING
**Estimated tests:** 12-15

---

## Objective

Add traceability edges to the ArangoDB knowledge graph connecting resume versions
to the evidence that generated them. Enables "why does this bullet exist?" queries
and evidence coverage analysis.

## Tasks

### P2-B.1: Add resume version vertex collection (Sonnet)
- **Test first:** Test asserting `ro_resume_versions` collection exists
- **Implementation:** New vertex collection in `arango_client.py`:
  - `ro_resume_versions` — stores version_id, user_id, source, created_at
- New edge collection: `ro_version_sourced_from`
  - From: `ro_resume_versions`
  - To: `ro_client_projects`, `ro_business_outcomes`, `ro_journey_milestones`
- Update `GRAPH_NAME` edge definitions
- **Files:** `arango_client.py`

### P2-B.2: Write traceability edges on resume generation (Sonnet)
- **Test first:** Test asserting edges created when Resume Tailor generates output
- **Implementation:** After Resume Tailor produces output:
  - Parse LLM output for referenced client names, outcomes, milestones
  - Match against existing graph vertices
  - Create `ro_version_sourced_from` edges with edge data:
    - `reference_type`: "client" | "outcome" | "milestone"
    - `confidence`: how certain the reference match is
    - `section`: which resume section references this evidence
- **Files:** `agents/resume_tailor.py`, `arango_client.py`

### P2-B.3: Evidence coverage API (Sonnet)
- **Test first:** Test asserting coverage endpoint returns correct counts
- **Implementation:** `GET /api/graph/evidence-coverage` returning:
  - `total_evidence`: count of projects + outcomes + milestones
  - `evidence_used`: count with at least one inbound version edge
  - `evidence_untapped`: count with zero inbound version edges
  - `coverage_pct`: used / total * 100
  - `untapped_items`: list of untapped evidence names
- **AQL query:** Count vertices with/without inbound `ro_version_sourced_from`
- **Files:** `arango_client.py`, `app.py` (new route)

### P2-B.4: Untapped evidence prompt injection (Sonnet)
- **Test first:** Test asserting untapped evidence appears in tailor prompt
- **Implementation:** When Resume Tailor runs:
  - Query untapped evidence
  - Inject top 5 untapped items into prompt as "consider highlighting"
  - Track whether untapped evidence gets used in output
- **Files:** `agents/resume_tailor.py`

## Acceptance Criteria

- [ ] `ro_resume_versions` and `ro_version_sourced_from` collections exist
- [ ] Edges created on resume generation
- [ ] Coverage API returns accurate counts
- [ ] Untapped evidence injected into tailor prompts
- [ ] All existing tests pass

## User Gate P2-B

**Present:** Sample traceability graph, coverage metrics, untapped evidence list.
