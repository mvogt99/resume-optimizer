# Phase P1-C: End-to-End Agent Validation

**Branch:** `feature/ro-phase-P1C-e2e-validation`
**Model:** Opus (requires judgment to assess output quality)
**Addresses:** Finding F11 (R11)
**Status:** PENDING
**Depends on:** P0-B (FTAL integration), P1-B (PersonaForge integration)
**Estimated tests:** 10-15 integration tests

---

## Objective

Validate that all 6 agents produce quality output with real career data.
Cover Letter, Interview Coach, Career Advisor, and Orchestrator have never been
exercised — this phase proves they work with Mike's actual profile.

## Tasks

### P1-C.1: Select representative test data (Opus)
- Pick 3 real job postings from the 295:
  - Senior/Director Data Architect role
  - AI/ML Engineering Leadership role
  - Enterprise Solutions Architect role
- Verify Mike's LinkedIn profile, deep profile, and project data are loaded
- Document the test data selection rationale

### P1-C.2: Run individual agent pipelines (Opus)
- **Resume Tailor:** Tailor resume for each posting
  - Assert: ATS score > 60, keywords matched, tailored text not empty
  - Record FTAL gap scores
- **Cover Letter:** Generate letter for each posting
  - Assert: Score > 50, body > 200 words, no placeholder text
  - Record FTAL gap scores
- **Interview Coach:** Start session for each posting
  - Assert: Questions generated, persona applied, STAR evaluation works
  - Record FTAL gap scores
- **Career Advisor:** Analyze career trajectory
  - Assert: Trajectory, strengths, growth areas populated
  - Record FTAL gap scores

### P1-C.3: Run full orchestrator pipeline (Opus)
- **Test:** `orchestrator.full_application_pipeline()` with real posting
- **Validation:**
  - All 3 steps complete (or documented partial failure)
  - All FTAL gap scores < 30
  - Pipeline moves posting to "applied" stage

### P1-C.4: Run career deep dive (Opus)
- **Test:** `orchestrator.career_deep_dive()` with real profile
- **Validation:** Career analysis, role recommendations, skills roadmap populated

### P1-C.5: Expert quality assessment (Opus)
- Review all generated content against Mike's actual career data
- Grade each output on:
  - **Accuracy** — facts match profile data
  - **Relevance** — content targets the specific role
  - **Differentiation** — highlights unique strengths, not generic
  - **Voice** — consistent with professional persona
  - **Completeness** — no missing sections or placeholder text
- Document specific issues found with remediation plan

## Acceptance Criteria

- [ ] All 6 agents produce output with real data
- [ ] All FTAL gap scores < 30
- [ ] Expert quality grade >= B on all outputs
- [ ] No placeholder text in any output
- [ ] Specific issues documented with remediation plan
- [ ] PersonaForge remember called for all passing outputs

## User Gate P1-C (CRITICAL GATE)

**Present to user:**
1. Full pipeline output for each test posting:
   - Tailored resume text + ATS score
   - Cover letter (subject, body, closing) + score
   - Interview prep questions + talking points
   - Career analysis + role recommendations
2. FTAL gap scores for every agent call
3. Expert quality assessment (accuracy, relevance, differentiation, voice)
4. Specific issues found
5. PersonaForge learning stored

**This is the most important gate.** User reviews actual generated career content
and decides if quality is acceptable before proceeding to later phases.

**Model:** Opus for entire phase (quality judgment required).
