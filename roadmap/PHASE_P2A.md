# Phase P2-A: Deep Profile Staleness Detection

**Branch:** `feature/ro-phase-P2A-profile-staleness`
**Model:** Sonnet
**Addresses:** Finding F9 (R9)
**Status:** PENDING
**Estimated tests:** 10-12

---

## Objective

Detect when the deep profile is stale (source data changed since last build) and
offer incremental rebuild. Currently built once and never refreshed.

## Tasks

### P2-A.1: Add staleness tracking columns (Sonnet)
- **Test first:** Test asserting `is_stale` flag, `source_hash`, `stale_reason` exist
- **Implementation:** ALTER TABLE deep_profiles ADD:
  - `source_hash TEXT` — hash of source data counts
  - `is_stale INTEGER DEFAULT 0`
  - `stale_reason TEXT DEFAULT ''`
  - `last_checked_at TIMESTAMP`
- Compute hash from: client_project count + experience count + journey_event count +
  narrative count + linkedin_profile update timestamp

### P2-A.2: Add staleness check after data changes (Sonnet)
- **Test first:** Test asserting profile marked stale after new project approval
- **Implementation:** After these events, recompute hash and compare:
  - `POST /api/projects/<id>/approve` — new client project
  - `POST /api/experience/finalize/<id>` — new experience
  - `POST /api/journey/mine` — new journey mining
  - `POST /api/import/linkedin` — LinkedIn profile update
  - `POST /api/journey/approve` — narratives approved
- If hash differs, set `is_stale=1`, `stale_reason=<what changed>`

### P2-A.3: Staleness status API (Sonnet)
- **Test first:** Test asserting status endpoint returns freshness info
- **Implementation:** `GET /api/deep-profile/status` returning:
  - `is_stale: bool`
  - `stale_reason: str`
  - `last_built_at: timestamp`
  - `source_counts: {projects, experiences, events, narratives}`
  - `current_hash vs stored_hash`

### P2-A.4: Incremental rebuild endpoint (Sonnet)
- **Test first:** Test asserting rebuild produces updated profile when stale
- **Implementation:** `POST /api/deep-profile/refresh`:
  - Only rebuilds if stale (returns 304 if fresh)
  - Uses FTAL harness for synthesis
  - Stores PF memory of successful synthesis patterns
  - Updates source_hash and clears is_stale

## Acceptance Criteria

- [ ] Staleness columns exist and populated
- [ ] Profile auto-detected as stale after data changes
- [ ] Status API returns accurate freshness info
- [ ] Refresh endpoint rebuilds when stale, skips when fresh
- [ ] FTAL harness used for synthesis
- [ ] PF memory updated on success
- [ ] All existing tests pass

## User Gate P2-A

**Present:** Staleness detection demo, refresh timing, before/after profile diff.
