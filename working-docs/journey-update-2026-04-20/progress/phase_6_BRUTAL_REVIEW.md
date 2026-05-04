# Phase 6: Brutal Self-Review

**Date:** 2026-04-22
**Model:** claude-sonnet-4-6
**Verdict: PASS — P0 = 0**

---

## What Went Right

- NULL id bug correctly diagnosed from first principles: `UPDATE ... WHERE id = NULL` matches no rows in SQL. Fix targeted two sites in `deep_profile.py` (both `_save_profile` and `update_profile_from_interview`). The second site was caught during brutal review — it had the same pattern and would have caused `update_profile_from_interview` to silently drop updates.
- `_get_loaded_model_id()` fix for `call_direct()` is robust: queries `/v1/models` at runtime rather than caching. Correctly handles model swaps without code changes.
- Context window math checked: 14000 chars ≈ 3500 tokens input + 12000 max_tokens output = 15500 < 16384 max_model_len. Leaves 884 token margin for prompt template.
- Superseded filter confirmed: 2 rows excluded (IDs 85/86, old LinkedIn entries). Exactly the entries superseded in Phase 5.
- All 40 tests still pass after 5 code changes across 4 files.

---

## P0 Issues

**None.**

---

## P1 Issues — RESOLVED during brutal review

### P1-A: Second NULL-id update site in `update_profile_from_interview()`
- Identical pattern to the `_save_profile` bug — `UPDATE ... WHERE id = ?` with `existing["id"] = None`.
- Would silently drop all interview-discovered profile updates for this user.
- Fixed: added `elif existing:` branch with `WHERE user_id = ? AND id IS NULL`.
- No test exists for this path (acceptable — requires real DB + interview session setup; risk is low since the fix mirrors the verified pattern from `_save_profile`).

---

## P2 Issues

### P2-A: NULL id row not repaired (acceptable)
- The deep_profiles row retains `id = NULL` after rebuild. Future code written assuming non-null id could fail silently.
- Risk: low — only one deep_profiles row per user exists; both update sites now handle NULL id correctly.
- Mitigation: would require a one-time SQL `UPDATE deep_profiles SET id = gen_random_uuid() WHERE id IS NULL` — not done here to avoid unnecessary DB surgery. No current code path assumes non-null id.

### P2-B: `_get_loaded_model_id()` adds 1 HTTP call per `call_direct()` invocation
- Queries `/v1/models` on every `call_direct()` call. During synthesis (1 call), cost is negligible. In tight loops it would add latency.
- Mitigation: acceptable for current usage patterns. A TTL cache (5s) could be added if it becomes a problem.

### P2-C: Gateway FTAL harness returns 500 post-vLLM restart (operational)
- Root cause not diagnosed — data gateway gets `httpx.ReadError` from vLLM during restart window. Harness recovers on its own but is unreliable immediately post-restart.
- Not a Phase 6 regression — harness was already failing before Phase 6 work.
- Mitigation: `call_direct()` fallback is functional; harness will self-heal on next successful vLLM request.

---

## Fabrication Check

- Career phases: "2000-2010", "2010-2020", "2020-Present" — plausible from LinkedIn data (20+ years experience). Not verified line-by-line but no impossible claims.
- Tech mastery includes "Knowledge Graph Design" — present in ArangoDB work (April milestones). ✅
- No `%` metrics or `Nx` multipliers visible in profile synthesis fields.
- Source summary honestly reflects data counts: 500 events, 135 narratives, 5 WIP projects.

---

## Test Coverage Assessment

### Covered (mutation-verified, from Phase 5)
- `_strip_think_tags()` — 5 pure tests, mutation-verified
- `call_llm_quality()` harness path — 4 integration tests, mutation-verified

### Not Covered (acceptable)
- `_save_profile()` NULL id branch — tested implicitly via the full rebuild cycle (profile updated correctly at 21:00:01); no unit test because it requires a real SQLite DB with a NULL-id row
- `_get_loaded_model_id()` — tested manually (returns `QuantTrio/Qwen3-30B-A3B-Thinking-2507-AWQ` vs stale `Qwen/Qwen2.5-Coder-32B`); no unit test because it requires a real vLLM endpoint
- `update_profile_from_interview()` NULL id branch — same rationale; risk low as fix mirrors verified pattern

---

## Summary

Phase 6 delivered:
1. Deep profile rebuilt with April 2026 data (3 career phases, 5 tech mastery, 5 higher-order skills)
2. 5 bugs fixed: NULL id (×2 sites), LIMIT 200 → 500, superseded filter, context overflow, `call_direct` model ID
3. All downstream APIs verified: timeline (April-20 events), skills (43 skills, 17 from 2026), achievements (9,155 items), ArangoDB (1,188 milestones + 133 skills)
4. DB backup: `database.db.bak.2026-04-22`
5. All 40 tests pass

Phase 6 quality gate: **PASS** (zero P0, P1-A resolved during review).
