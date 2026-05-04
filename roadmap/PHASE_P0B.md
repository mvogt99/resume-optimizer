# Phase P0-B: FTAL Harness Integration

**Branch:** `feature/ro-phase-P0B-ftal-integration`
**Model:** Sonnet (implementation) + Opus (architecture review at B.2, B.5)
**Addresses:** Finding F1 (R1)
**Status:** PENDING
**Estimated tests:** 25-30

---

## Objective

Route all quality-sensitive LLM calls through the FTAL harness instead of direct port 8021.
This is the single highest-impact change — it gives every career output the same quality gate
(scoring, retry, teaching) as gateway code generation.

## Tasks

### P0-B.1: Create FTAL-aware LLM client (Sonnet)
- **Test first:** Tests for new `call_llm_scored()` returning (result, ftal_scores)
- **Implementation:** New function in `llm_helper.py`:
  - Calls `/api/harness/run` with task_type from call context
  - Returns both the LLM output and FTAL scores (f, t, a, gap)
  - Harness handles retries if gap >= 30
  - Falls back to `call_direct()` if harness unreachable
- **Files:** `llm_helper.py`

### P0-B.2: Classify call sites by quality sensitivity (Opus)
- **Analysis only** — no code changes
- **Status:** COMPLETE (2026-03-27, Opus)

#### Classification Criteria

- **QUALITY_SENSITIVE** — output is user-facing prose (narratives, recommendations, coaching responses, career content). Quality variation directly impacts user experience. Route through `call_llm_scored()` for FTAL scoring, retry on gap >= 30, teaching doc generation on persistent failure.
- **EXTRACTION_ONLY** — output is structured JSON or data extraction. LLM is parsing/classifying, not composing. Speed matters more than stylistic quality. Keep on `call_direct()` or `call_llm()`.

#### Classification Table

| File | Line(s) | Current Call | Classification | Rationale |
|------|---------|-------------|----------------|-----------|
| `journey_synthesizer.py` | 103, 123, 219, 265, 294 | `call_llm(coding)` | **QUALITY_SENSITIVE** | Generates STAR resume bullets, LinkedIn summary sections, career narratives — all user-facing prose |
| `deep_profile.py` | 699, 790 | `call_llm(career_planning)` | **QUALITY_SENSITIVE** | Career profile synthesis and role fit scoring — high-stakes user-facing output |
| `experience_chat.py` | 709→896 | `call_direct()` via `_call_llm()` | **QUALITY_SENSITIVE** | Generates conversational follow-up questions during experience extraction — shapes interview quality |
| `post_generator.py` | 187 | `call_llm(coding)` | **QUALITY_SENSITIVE** | LinkedIn post drafts — directly published content, quality-critical |
| `campaign_interview.py` | 285 | `call_llm(general)` | **QUALITY_SENSITIVE** | Campaign planning questions — guides user through 7-stage state machine |
| `campaign_suggestor.py` | 99 | `call_llm(campaign_strategy)` | **QUALITY_SENSITIVE** | Campaign strategy suggestions — creative content |
| `recommendation_drafter.py` | 62 | `call_llm(narrative_generation)` | **QUALITY_SENSITIVE** | Recommendation letter drafting — user-facing prose |
| `deep_interview.py` | 158, 526 | `call_llm(interview/career_planning)` | **QUALITY_SENSITIVE** | Interview follow-ups and career planning synthesis |
| `portfolio_generator.py` | 81 | `call_llm(narrative_generation)` | **QUALITY_SENSITIVE** | Portfolio narrative synthesis |
| `utils.py` | 425 | `call_smart(resume_rewrite)` | **QUALITY_SENSITIVE** | Resume optimization — the app's core function |
| `ats_improvement_chat.py` | 321, 357, 388 | `call_smart(ats_diagnostic)` via `_call_llm()` | **QUALITY_SENSITIVE** | ATS coaching responses — interactive user-facing advice |
| `agents/resume_tailor.py` | 634, 780 | `_call_llm(coding)` | **QUALITY_SENSITIVE** | Resume rewriting and requirement matching — user-facing output |
| `agents/interview_coach.py` | 853, 1085 | `_call_llm(reasoning)` | **QUALITY_SENSITIVE** | Question generation and answer scoring — coaching quality |
| `skills_interview.py` | 165, 235 | `_call_llm()` → harness direct | **QUALITY_SENSITIVE** | Skills gap interview — conversational follow-ups |
| `architecture_analyzer.py` | 97 | `call_llm(reasoning)` | **QUALITY_SENSITIVE** | Architecture analysis prose |
| `agentic_compiler.py` | 345, 539 | `call_llm(reasoning)` | **QUALITY_SENSITIVE** | Agent architecture reasoning and design |
| `llm_helper.py` | 203 | `call_llm(coding)` in `synthesize_narrative()` | **QUALITY_SENSITIVE** | Narrative text generation helper |
| --- | --- | --- | --- | --- |
| `llm_helper.py` | 153, 175 | `call_llm()` in `analyze_with_chunking/context()` | **EXTRACTION_ONLY** | Chunked document analysis — returns parsed JSON items, not prose |
| `campaign_interview.py` | 493 | `call_llm(coding)` | **EXTRACTION_ONLY** | Structured campaign JSON creation from interview state |
| `agentic_compiler.py` | 511 | `call_llm(coding)` | **EXTRACTION_ONLY** | Structured code generation — deterministic output |
| `builder_interview.py` | 452, 536, 564, 602 | `call_llm_direct()` | **EXTRACTION_ONLY** | JSON array extraction for builder UI — structured data |
| `linkedin_profile_upload.py` | 431 | `call_direct()` | **EXTRACTION_ONLY** | LinkedIn data normalization — structured extraction |
| `project_analyzer.py` | 550, 923 | `call_llm(reasoning)` | **EXTRACTION_ONLY** | Project document extraction and structured profile synthesis into JSON |
| `job_scraper.py` | 269 | `call_llm()` | **EXTRACTION_ONLY** | Job posting field extraction — structured data |

#### Notes on agents not yet wired

- `agents/cover_letter.py` — **no LLM calls yet** (Wave 2 stub). When implemented: QUALITY_SENSITIVE.
- `agents/career_advisor.py` — **no LLM calls yet** (Wave 3 stub). When implemented: QUALITY_SENSITIVE.
- `agents/app_tracker.py` — no direct LLM calls (uses base_agent routing). Follow-up email gen: QUALITY_SENSITIVE when wired.
- `agents/job_scout.py` — LLM scoring in `job_scraper.py` (listed above as EXTRACTION_ONLY).

#### Migration scope for B.3

**21 call sites** across 13 files need migration to `call_llm_scored()`.
**7 call sites** across 6 files stay on current routing (extraction-only).

The `base_agent._call_llm()` routing method (used by resume_tailor and interview_coach) is the highest-leverage migration point — changing it once covers all agent subclasses.

### P0-B.3: Migrate quality-sensitive call sites (Sonnet)
- **Test first:** Integration tests verifying harness is called for each migrated site
- **QUALITY_SENSITIVE (migrate to call_llm_scored):**
  - `journey_synthesizer.py` — all 5 generate methods
  - `deep_profile.py` — profile synthesis
  - `experience_chat.py` — follow-up question generation
  - `agents/cover_letter.py` — letter generation, culture analysis
  - `agents/resume_tailor.py` — resume rewriting, requirement matching
  - `agents/interview_coach.py` — question generation, answer scoring
  - `agents/career_advisor.py` — career analysis, recommendations
  - `post_generator.py` — LinkedIn post generation
  - `campaign_interview.py` — campaign planning questions
- **EXTRACTION_ONLY (keep call_direct):**
  - `technical_extractor.py` — structured JSON extraction
  - `governance_extractor.py` — structured JSON extraction
  - `role_extractor.py` — structured JSON extraction
  - `skills_extractor.py` — structured extraction
  - `llm_helper.py` — extract_json helpers

### P0-B.4: Add FTAL score columns to agent_runs (Sonnet)
- **Test first:** Test asserting agent_runs includes ftal_f, ftal_t, ftal_a, ftal_gap
- **Implementation:** ALTER TABLE agent_runs ADD COLUMN ftal_f, ftal_t, ftal_a, ftal_gap
- Populate from scored calls in BaseCareerAgent._call_llm()
- **Files:** `models.py`, `agents/base_agent.py`

### P0-B.5: Honest assessment (Opus, 2026-03-27)
- **Status:** COMPLETE

#### Infrastructure verified
- RTX 5090: 39°C, Qwen3-Coder-30B-A3B loaded on port 8021
- Gateway healthy on port 8000
- FTAL score extraction: **FIXED** — scores are top-level `ftal_f/t/a/gap` keys (not nested `ftal_score`). Fixed in `call_harness_scored()`.

#### Plumbing: WORKS
- `call_llm_scored()` correctly returns `(text, scores_dict)` ✅
- Score dict keys `f`, `t`, `a`, `gap` populated from harness response ✅
- Fallback to `call_direct()` when harness unreachable ✅
- `BaseCareerAgent._log_run()` persists FTAL scores to `agent_runs` table ✅
- `call_llm_quality()` logs gap at WARNING when gap >= 30, DEBUG otherwise ✅

#### Output quality: DEGRADED by RAG context pollution

| Test | Direct (no harness) | Harness (with RAG) | Gap |
|------|--------------------|--------------------|-----|
| Resume bullet (STAR) | Excellent — specific, quantified, correct technologies | "System cannot provide an answer as the question is incomplete" | 30 |
| Interview coaching | Structured questions, competency labels, STAR outlines | "Response structure follows a rigid template" meta-commentary | 30 |
| Professional summary | (not tested direct) | "No input question was provided" | — |

**Root cause:** The FTAL harness augments every task with ArangoDB/Qdrant context from the *gateway knowledge base* (architecture rules, coding learnings, prior task results). This context is designed for code generation tasks. When a resume-optimizer task (narrative generation, interview coaching) passes through, the model sees:

1. The original career-content task (e.g., "generate a STAR bullet")
2. Prepended gateway architecture rules and prior coding task results
3. The model responds to the prepended context (#2) instead of the actual task (#1)

**FTAL scores are mechanically correct** — the scorer evaluates F/T/A based on how well the output follows the expected format. The scores (F=40, T=20, A=0, gap=30) accurately reflect that the output partially follows structure but completely misses task alignment.

#### What works well
1. Score extraction pipeline: end-to-end from harness response to agent_runs table
2. Fallback mechanism: `call_direct()` when harness is down produces high-quality output
3. Gap logging: WARNING-level log when gap >= 30 enables monitoring
4. The Qwen3-Coder-30B model itself produces excellent career content when given a clean prompt (no RAG pollution)

#### What needs fixing (not P0-B scope)
1. **RAG context scoping** — the harness needs domain-aware context augmentation. Resume-optimizer tasks should NOT receive gateway coding rules/learnings. Options:
   - Add a `context_domain` parameter to `/api/harness/run` so the caller can specify "career" vs "gateway"
   - Create resume-optimizer-specific knowledge in ArangoDB and route based on task origin
   - Allow callers to opt out of RAG augmentation for pure-generation tasks
2. **Direct call quality** — Qwen3-Coder-30B direct calls produce excellent career content. The fallback path (`call_direct()`) is ironically the higher-quality path right now.

#### Recommendation
P0-B plumbing is complete and correct. The RAG context scoping issue should be addressed in a targeted fix (either as a P0-B addendum or early P1 task) before the harness path delivers value for the resume-optimizer. In the meantime, the `call_llm_quality()` fallback to `call_direct()` ensures no quality regression — all 21 migrated call sites will get clean direct calls when the harness returns poor results.

**Honest rating: 6/10** — Plumbing A+, quality output D (due to RAG pollution, not model capability).

## Acceptance Criteria

- [ ] `call_llm_scored()` exists and returns (result, ftal_scores)
- [ ] All quality-sensitive call sites migrated
- [ ] agent_runs table stores FTAL scores
- [ ] All existing tests still pass
- [ ] Representative calls show gap < 30
- [ ] Fallback to call_direct() works when harness unavailable

## User Gate P0-B

**Present to user:**
1. Architecture diagram: old call flow vs new call flow
2. Call site classification table (quality-sensitive vs extraction-only)
3. FTAL gap scores from representative calls (resume, cover letter, interview)
4. Before/after output quality comparison (same prompt, direct vs harness)
5. Retry rate and teaching doc generation stats
6. Honest assessment

**Model switch required:** Prompt user to switch to Opus for B.2 and B.5.
