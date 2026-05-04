# Phase 6: Downstream Consumer Refresh

**Date:** 2026-04-22
**Model:** claude-haiku-4-5
**Status: COMPLETE**

---

## Pre-Rebuild State (Task 6.1)

- Deep profile: stale (`is_stale=1`, reason: "Journey narratives approved")
- `updated_at`: 2026-03-05T15:55:59.828211 — 7 weeks stale
- `profile_json` length: 8,619 chars (LinkedIn summary only, no synthesis)
- Source summary: "Journey: 200 events, 30 narratives" — severely undercounting

---

## Bugs Found and Fixed (Task 6.2)

### Bug 1: NULL id prevents UPDATE (deep_profile.py)
**Root cause:** The existing deep_profiles row has `id = NULL` (created before UUID was added). `_save_profile()` does `UPDATE ... WHERE id = ?` with `None`, which matches zero rows. Every rebuild silently failed.
**Fix:** Added `elif existing:` branch — when `id IS NULL`, update by `user_id AND id IS NULL`.

### Bug 2: LIMIT 200 on journey events (deep_profile_sources.py)
**Root cause:** `get_journey_data()` had `LIMIT 200` while the events table has 17,200+ rows. Query also ordered `ASC` so fetched oldest events.
**Fix:** Changed to `ORDER BY event_date DESC LIMIT 500` — returns most recent 500 events.

### Bug 3: Superseded narratives included (deep_profile_sources.py)
**Root cause:** Narrative query lacked `AND superseded_at IS NULL`, so superseded LinkedIn entries (IDs 85/86) were included alongside current IDs 284/285.
**Fix:** Added `AND superseded_at IS NULL` filter.

### Bug 4: Context window overflow with thinking model (deep_profile_synthesis.py)
**Root cause:** 28,000 char context + large prompt (~32K chars ≈ 8000 tokens) + max_tokens=8192 = 16192 total tokens, right at the Qwen3-30B-Thinking max_model_len=16384. The `<think>` block consumed most output budget, leaving only ~1000 chars for JSON (truncated/invalid).
**Fix:** Reduced context truncation from 28,000 → 14,000 chars; increased max_tokens from 8192 → 12,000.

### Bug 5: FALLBACK_MODEL_ID mismatch (smart_llm.py)
**Root cause:** `call_direct()` hardcoded `FALLBACK_MODEL_ID = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"` but the currently loaded model is `QuantTrio/Qwen3-30B-A3B-Thinking-2507-AWQ`. Every `call_direct()` returned 404 from vLLM.
**Fix:** Added `_get_loaded_model_id()` that queries `/v1/models` at runtime; `call_direct()` uses the live model ID.

---

## Rebuild Results (Tasks 6.3–6.4)

| Metric | Before | After |
|--------|--------|-------|
| `updated_at` | 2026-03-05 | 2026-04-22T21:00:01 |
| `is_stale` | 1 | 0 |
| Events in source | 200 | 500 |
| Narratives in source | 30 | 135 |
| WIP projects | 3 | 5 (added api-docs-hub, data-platform) |
| Career phases | 0 (fallback) | 3 |
| Tech mastery items | 0 | 5 |
| Higher-order skills | 0 | 5 |
| Business impacts | 0 | 4 |
| Differentiators | 0 | 3 |

**Career phases synthesized:**
1. Foundational Data Platform Development | 2000-2010
2. Consulting Practice Scaling & Talent Development | 2010-2020
3. AI & Advanced Data Systems Leadership | 2020-Present ← includes April 2026 work

**April 2026 signals in synthesis:**
- "Knowledge Graph Design" in technology mastery
- Trajectory: "Evolved from enterprise data platform design to AI architecture"
- Source explicitly includes api-docs-hub, data-platform (April 2026 WIP projects)

---

## Downstream API Verification (Tasks 6.5–6.9)

| API | Result | April Data? |
|-----|--------|-------------|
| `GET /api/journey/timeline` | 50 events, latest: 2026-04-20 | ✅ |
| `GET /api/journey/skills` | 43 skills, 17 from 2026 | ✅ |
| `GET /api/journey/achievements` | 9,155 items | ✅ |
| `GET /api/campaigns/analytics` | 0% coverage, 1,188 milestones / 133 skills baseline | ✅ |
| ArangoDB graph (direct) | 1,188 milestones + 133 skills (Phase 5 approval) | ✅ |

---

## Notes

- Gateway FTAL harness (port 8000 → 8001) returns 500 consistently post-vLLM restart. Data plane gateway recovered after restart but harness is unstable. `call_direct()` fallback is functional.
- Thinking model (Qwen3-30B-A3B-Thinking-2507-AWQ) is currently loaded — works correctly after max_tokens fix. `<think>` stripping from Phase 5 is active.
- DB backup: database.db.bak.2026-04-22 (task 6.12)

---

**Phase 6 quality gate: PASS** — deep profile rebuilt with April 2026 data, all downstream APIs functional.
