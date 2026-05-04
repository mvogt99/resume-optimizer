# Resume Recommender — Implementation Plan

## Context

**Problem:** No way to compare multiple resumes against a JD and recommend the best starting point. Scoring logic is embedded inside `optimize_resume()` (utils.py:186-364) alongside content enhancement — can't score-only without side effects. `utils.py` is 558 lines (over 500-line limit).

**Outcome:** Select 1–N resumes → provide JD → see ranked recommendations with rationale → customize chosen resume.

## Workflow (Every Phase)
1. Write tests FIRST (TDD red) → 2. Implement (green-refactor) → 3. Test with real data, NO mocks/stubs → 4. Brutal assessment: as-built vs as-claimed → 5. Fix gaps → 6. **User gate** (accept or request alternative) → 7. Next phase

---

## Phase 1: Extract Scoring — `resume_scorer.py` (**haiku**)

**Delivers:** Pure `score_resume()` function. `utils.py` drops to ~490 lines. All existing tests pass.

| Action | File | Δ Lines |
|--------|------|---------|
| CREATE | `backend/resume_scorer.py` | ~120 |
| CREATE | `backend/tests/test_resume_scorer.py` | ~110 |
| MODIFY | `backend/utils.py` | -70 extract, +5 import |

**Tests first:** `test_score_returns_expected_keys`, `test_score_deterministic`, `test_score_no_side_effects`, `test_no_llm_calls`, `test_well_matched_scores_high` (>40), `test_mismatched_scores_low` (<20), `test_breakdown_components_valid`, `test_optimize_resume_regression` (±2pts), `test_with_linkedin_endorsements`, `test_empty_resume_returns_zero`

**Key:** Extract utils.py lines 201–271 into `score_resume(resume_data, job_keywords, job_text, linkedin_profile)`. Fix stale weight comments (208: "40%"→"20%", 221: "30%"→"20%", 224: "20%"→"50%").

**Done when:** score_resume() works without side effects, utils.py < 500 lines, all existing tests pass, 10 new tests green.

---

## Phase 2: Multi-Resume Comparison Endpoint (**haiku**)

**Delivers:** `POST /api/resumes/compare` — scores N resumes, returns ranked list. `ResumeRecommendation` model persists results. No LLM yet.

| Action | File | Δ Lines |
|--------|------|---------|
| CREATE | `backend/resume_recommender.py` | ~150 |
| CREATE | `backend/routes/recommender_routes.py` | ~120 |
| CREATE | `backend/tests/test_resume_recommender.py` | ~180 |
| MODIFY | `backend/models.py` | +45 |
| MODIFY | `backend/app.py` | +3 |

**API:** `POST /api/resumes/compare` — Body: `{resume_ids, resume_version_ids, job_description_text}` → Response: `{recommendation_id, rankings: [{resume_id, resume_version_id, filename, source, score, score_breakdown, matching_keywords, missing_keywords, rank}], recommended_resume_id}`

**DB Table:** `resume_recommendations` — id(UUID), user_id, job_description_text, resume_scores_json, recommended_resume_id, recommended_version_id, rationale(null), user_chosen_resume_id, session_id(null), created_at

**Tests first:** auth required (401), empty resume_ids (400), empty job text (400), nonexistent resume (404), other user's resume (403), two resumes ranked correctly, per-resume breakdown present, best match first, single resume works, persists recommendation, version IDs accepted, 5 resumes under 10s, LinkedIn enrichment affects scores

**Reuses:** `score_resume()` (Phase 1), `process_resume()`, `Resume.get_by_id()`, `ResumeVersion.get_by_id()`, `extract_skill_phrases()`

**Done when:** Rankings sorted by score, persisted in DB, both resume_ids and version_ids work, 13 tests green, < 10s for 5 resumes.

---

## Phase 3: LLM Rationale (**sonnet** for prompt, **haiku** for code)

**Delivers:** 3–5 sentence explanation of why top resume is best, per-resume strengths/weaknesses. Template fallback when LLM unavailable.

| Action | File | Δ Lines |
|--------|------|---------|
| CREATE | `backend/recommendation_rationale.py` | ~140 |
| CREATE | `backend/tests/test_recommendation_rationale.py` | ~130 |
| MODIFY | `backend/resume_recommender.py` | +15 |
| MODIFY | `backend/routes/recommender_routes.py` | +10 |

**Tests first:** returns non-empty string, mentions top filename, mentions ≥1 matching keyword, mentions ≥1 gap, fallback on LLM failure (template), fallback references scores, integration includes rationale (`llm_required`), skip_rationale flag works, under 30s (`llm_required`)

**Key:** `generate_rationale(rankings, job_text, timeout=30)` calls `call_llm_quality(prompt, task_type="reasoning")` → RTX 5090. Blocks up to 30s. On timeout/failure → `template_rationale(rankings)` deterministic fallback. Compare endpoint returns rankings + rationale (or template) in a single response — no async polling.

**Done when:** Rationale references specific skills/keywords, template works without LLM, integration test passes with real GPU, skip_rationale bypasses LLM, total compare response ≤ 30s.

---

## Phase 4: Frontend — Recommendation Step (**haiku** + **sonnet** for Dashboard)

**Delivers:** Conditional step 2.5 in wizard. Multi-resume → ranked cards with scores + rationale → accept/override → optimize. Single-resume unchanged.

| Action | File | Δ Lines |
|--------|------|---------|
| CREATE | `frontend/src/components/ResumeRecommendation.jsx` | ~280 |
| CREATE | `frontend/src/__tests__/recommendation.test.jsx` | ~120 |
| MODIFY | `frontend/src/services/api.jsx` | +15 |
| MODIFY | `frontend/src/components/Dashboard.jsx` | +70 |
| MODIFY | `frontend/src/components/ResumeUpload.jsx` | +30 |

**Props:** `{recommendation, loading, onSelect(resume_id, version_id), onRecompare}`

**Dashboard changes:** New state: `recommendation`, `showRecommendation`. Step 2 JD submit → if 2+ resumes in Compare mode: call compareResumes(), show ResumeRecommendation, step=2.5. On select → optimize chosen resume → step=3. Single resume or Merge mode: step 2→3 unchanged.

**ResumeUpload mode toggle:** Add Compare/Merge toggle when 2+ files selected. Compare mode (default): files are comparison candidates. Merge mode: existing behavior (context merging). Library picker shows all sources: uploads, GDrive, LinkedIn, interview-built.

**Tests first:** renders ranked cards, highlights recommended, shows scores, shows rationale, shows keyword chips, accept fires callback, override fires callback, loading spinner, single resume skips step, multi resume shows step, mode toggle switches behavior

**Done when:** Multi-resume Compare flow works, Merge mode preserved, all sources in library, scores render, rationale displays, accept/override both work, 11 Vitest tests pass.

---

## Phase 5: E2E Integration & Session Linking (**haiku**)

**Delivers:** Full flow with session persistence. Recommendation linked to JobSession. Past recommendations retrievable.

| Action | File | Δ Lines |
|--------|------|---------|
| CREATE | `backend/tests/test_recommendation_e2e.py` | ~200 |
| MODIFY | `backend/routes/recommender_routes.py` | +50 |
| MODIFY | `backend/routes/sessions_routes.py` | +10 |
| MODIFY | `backend/models.py` | +10 |
| MODIFY | `frontend/src/components/Dashboard.jsx` | +15 |
| MODIFY | `frontend/src/services/api.jsx` | +10 |

**New endpoints:** `POST /api/resumes/recommendations/{id}/select` (record user choice), `GET /api/resumes/recommendations` (list history)

**Tests first:** full flow upload→compare→select→optimize (200 each step), recommendation links to session, override works, recompare with new resumes, list past recommendations, get detail, version IDs work, LinkedIn enrichment, concurrent compares safe, optimize uses chosen resume only

**Done when:** Full journey works E2E, session links to recommendation, override works, 10 E2E tests pass with real data.

---

## Functions Reused (NOT reimplemented)

| Function | File | Phase |
|----------|------|-------|
| `analyze_resume_vs_job()` | `nlp_engine.py` | 1 |
| `extract_skill_phrases()` | `nlp_engine.py` | 1, 2 |
| `calculate_similarity()` | `nlp_engine.py` | 1 |
| `weighted_skill_match()` | `skills_optimizer.py` | 1 |
| `process_resume()` | `utils.py` | 2 |
| `call_llm_quality()` | `llm_helper.py` | 3 |
| `Resume.get_by_id()` | `models.py` | 2 |
| `ResumeVersion.get_by_id/get_all_for_user()` | `models.py` | 2, 4 |
| `RESUME_TEXT, JD_TEXT, LINKEDIN_PROFILE` | `tests/test_helpers.py` | all |
| `upload_resume(), upload_jd()` | `tests/test_helpers.py` | 2+ |

## Architecture Decisions

1. **Dedicated `resume_recommendations` table** — not in JobSession. A recommendation precedes and may not lead to a session.
2. **`score_resume()` is pure** — no LLM, no content mod. LLM rewrite stays in `optimize_resume()`.
3. **All sources in library picker** — uploads, GDrive, LinkedIn, interview-built all shown in unified multi-select.
4. **Both resume_ids and resume_version_ids** in compare — users have multi-source libraries.
5. **Conditional wizard step** — single-resume flows 100% unchanged.
6. **LLM rationale waits up to 30s** — compare endpoint blocks up to 30s for rationale, then falls back to template. No async polling needed.
7. **Mode toggle in ResumeUpload** — "Compare" mode (rank candidates) vs "Merge" mode (combine for context). Default to Compare when 2+ files selected. Preserves existing merge behavior.

## Verification

Per-phase: `pytest tests/test_resume_scorer.py -v` (P1), `test_resume_recommender.py` (P2), `test_recommendation_rationale.py` (P3), `npm run test:unit -- recommendation.test.jsx` (P4), `test_recommendation_e2e.py` (P5). Full regression after each: `pytest tests/ -x --timeout=120` + `npm run test:unit`.

Manual E2E (Phase 5): start backend+frontend → upload 2+ resumes → paste real JD → verify recommendation step → accept → verify optimization → override → verify → check session list.
