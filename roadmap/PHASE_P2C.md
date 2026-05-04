# Phase P2-C: Application Feedback Loop

**Branch:** `feature/ro-phase-P2C-feedback-loop`
**Model:** Sonnet (implementation) + Opus (correlation analysis design at C.2)
**Addresses:** Finding F8 (R8)
**Status:** PENDING
**Estimated tests:** 15-18

---

## Objective

Wire pipeline stage transitions into a feedback loop so the system learns which
resume versions and cover letters lead to interviews. The `application_feedback`
table exists with 0 rows — this phase makes it functional.

## Tasks

### P2-C.1: Wire pipeline transitions to feedback storage (Sonnet)
- **Test first:** Test asserting feedback row created on stage change
- **Implementation:** On pipeline stage change (`PUT /api/agents/pipeline/<id>`):
  - Query the posting's current resume_version_id and cover_letter_id
  - Insert into `application_feedback`:
    - posting_id, resume_version_id, cover_letter_id
    - old_stage, new_stage, transitioned_at
    - ats_score (from posting), cover_letter_score
  - Special tracking for key transitions:
    - applied -> phone_screen = "callback"
    - phone_screen -> interview = "advanced"
    - interview -> offer = "success"
    - any -> rejected = "rejected"
- **Files:** `agents_routes.py`, `models.py`

### P2-C.2: Outcome correlation analysis (Opus)
- **Test first:** Test asserting correlation endpoint returns structured data
- **Implementation:** `GET /api/agents/pipeline/correlations`:
  - ATS score distribution: callback group vs rejected group
  - Cover letter score distribution: callback vs rejected
  - Top keywords in successful applications
  - Style/tone patterns in successful cover letters
  - Average gap scores for successful vs unsuccessful
- **Note:** Will return sparse data initially — designed to improve over time
- **Files:** New `feedback_analyzer.py`, `agents_routes.py`

### P2-C.3: Feed correlations into agent prompts (Sonnet)
- **Test first:** Test asserting feedback context appears in agent prompts
- **Implementation:** When agents generate output:
  - Query recent correlations
  - Inject success patterns into prompts:
    - Resume Tailor: "Keywords that led to interviews: [list]"
    - Cover Letter: "Tone that led to callbacks: [pattern]"
  - Store feedback patterns in PersonaForge
- **Files:** `agents/resume_tailor.py`, `agents/cover_letter.py`

### P2-C.4: Feedback dashboard data (Sonnet)
- **Test first:** Test asserting dashboard endpoint returns summary
- **Implementation:** `GET /api/agents/pipeline/feedback-summary`:
  - Total applications, callbacks, interviews, offers
  - Success rate by resume version
  - Success rate by cover letter style
  - Trend over time

## Acceptance Criteria

- [ ] Pipeline transitions create feedback rows
- [ ] Correlation endpoint returns structured analysis
- [ ] Agent prompts enriched with success patterns
- [ ] Dashboard summary endpoint functional
- [ ] PersonaForge stores feedback patterns
- [ ] All existing tests pass

## User Gate P2-C

**Present:** Feedback architecture, sample correlation data, agent prompt enrichment.

**Model switch:** Opus for P2-C.2 (correlation design).
