# Phase P1-B: PersonaForge Integration

**Branch:** `feature/ro-phase-P1B-personaforge`
**Model:** Sonnet (implementation) + Opus (persona design at B.2)
**Addresses:** Finding F2 (R2)
**Status:** COMPLETE (commit 8caf4b3, 2026-03-27)
**Estimated tests:** 20-25

---

## Objective

Integrate PersonaForge into the resume optimizer so LLM prompts carry personality
consistency, professional voice, and accumulated learning from past sessions.

## Tasks

### P1-B.1: Create PersonaForge client module (Sonnet)
- **Test first:** Tests for PF client with mocked HTTP responses
- **Implementation:** New `personaforge_client.py`:
  - `pf_recall(namespace, query)` — retrieve persona context
  - `pf_remember(namespace, content, metadata)` — store learning
  - `pf_feedback(outcome, confidence)` — send FTAL outcome
  - Fire-and-forget pattern (failures logged, never block)
  - 60s TTL cache on recall results
  - Config: `PF_URL` env var, default `http://localhost:8090`
- **Files:** New `backend/personaforge_client.py`

### P1-B.2: Define career persona namespace (Opus)
- **Design:** Define `career_profile` namespace:
  - Professional voice characteristics (tone, vocabulary level, focus areas)
  - Career positioning preferences (leadership vs IC, strategic vs tactical)
  - Tone preferences per output type (resume=formal, LinkedIn=approachable)
  - Successful narrative patterns from Phase P1-C validation
- **Implementation:** Seed initial persona from deep profile data via `pf_remember()`
- **Files:** New `backend/persona_seed.py`

### P1-B.3: Integrate PF recall into FTAL-aware LLM pipeline (Sonnet)
- **Test first:** Tests asserting persona context appears in prompts
- **Implementation:** Modify `call_llm_scored()` to:
  - Call `pf_recall("career_profile", task_summary)` before delegation
  - Prepend persona context to system prompt
  - Include career positioning and voice guidance
- **Files:** `llm_helper.py`

### P1-B.4: Integrate PF remember into successful outputs (Sonnet)
- **Test first:** Tests asserting pf_remember called after FTAL pass
- **Implementation:** After each gap < 30 output:
  - Store successful narrative patterns
  - Store effective prompt structures
  - Store career positioning that scored well
  - Adjust confidence based on FTAL gap score
- **Files:** `llm_helper.py`, `agents/base_agent.py`

## Acceptance Criteria

- [x] `personaforge_client.py` with recall/remember/feedback (25 tests)
- [x] Career persona namespace seeded from deep profile (29 tests)
- [x] LLM prompts include persona context on quality-sensitive calls (4 tests)
- [x] Successful outputs stored in PF memory (7 tests)
- [x] Fire-and-forget: PF failures never block pipeline
- [x] All existing tests still pass (zero regressions across all agent suites)

## User Gate P1-B

**Present:**
1. PersonaForge client API
2. Career persona namespace design
3. Sample prompt with vs without persona context
4. PF recall/remember flow diagram
5. Honest assessment

**Model switch:** Prompt user to Opus for P1-B.2 (persona design).
