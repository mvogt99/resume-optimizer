# Phase 17: Practical Usefulness Sprint

> **Created:** 2026-03-14
> **Status:** PLANNING
> **State file:** `roadmap/PHASE17_STATE.json` (machine-readable, survives compaction + reboots)
> **Ordering:** Dependency-first — MEDIUM quick wins that unblock CRITICAL items come first
> **Delegation:** Backend → RTX 5090 via FTAL harness ($0.00). Frontend → Expert AI.

---

## User Gate Protocol

Every completed task gets an **honest assessment** before proceeding. The gate is a **blocking CLI prompt** with these options:

| Option | Meaning |
|--------|---------|
| **ACCEPT** | Task is done. Move to next. |
| **FIX_SPECIFIC_ISSUES** | Describe what to fix. Expert or 5090 remediates, then re-gate. |
| **REGENERATE_VIA_5090** | Discard implementation, re-delegate to 5090 with teaching. |
| **SKIP_FOR_NOW** | Park this task, move to next. Can return later. |

Assessment format:
```
=== GATE: Task 17.XX — [Title] ===
What worked: ...
What's partial: ...
Known limitations: ...
Files changed: ...
Tests added: N

[ACCEPT / FIX_SPECIFIC_ISSUES / REGENERATE_VIA_5090 / SKIP_FOR_NOW]?
```

---

## Execution Order (dependency-optimized)

| Order | Task | Severity | Rationale |
|-------|------|----------|-----------|
| 1 | 17.01 Wire Resume Tailor | CRITICAL | Unblocks 17.02 orchestrated workflow + 17.13 checklist |
| 2 | 17.03 Interview Coach → Pipeline | MEDIUM | Quick UI wiring, no backend. Unblocks pipeline value. |
| 3 | 17.04 Cover Letter → Pipeline | MEDIUM | Quick UI wiring, no backend. Completes pipeline integration. |
| 4 | 17.02 Orchestrated Apply Workflow | CRITICAL | End-to-end pipeline. Depends on 17.01. |
| 5 | 17.09 Deep Profile → Scout Scoring | MEDIUM | Backend-only 5090 task. Improves scoring accuracy. |
| 6 | 17.11 Skills Interview → Optimization | MEDIUM | Backend-only 5090 task. Fixes wasted user effort. |
| 7 | 17.06 Cross-Posting JD Analysis | HIGH | Backend 5090 task. Skill demand patterns. |
| 8 | 17.05 Feedback Loop: Outcomes → Optimization | HIGH | Closes the learning loop. Backend 5090 + frontend. |
| 9 | 17.07 Experience → Builder Auto-populate | HIGH | Stops user double-entry. Backend 5090 + frontend. |
| 10 | 17.08 Salary Intelligence | HIGH | Highest-ROI job search activity. Backend 5090 + frontend. |
| 11 | 17.10 Follow-up Reminders | HIGH | Browser notifications + dashboard badge. Frontend-only. |
| 12 | 17.12 Cross-Session Learning | MEDIUM | Depends on 17.05. Aggregates optimization history. |
| 13 | 17.13 Ready-to-Apply Checklist | MEDIUM | Depends on 17.01, 17.02. Per-posting readiness view. |
| 14 | 17.14 Campaign Engagement Tracking | MEDIUM | Post performance feedback loop. |
| 15 | 17.15 Guided Onboarding Flow | MEDIUM | New-user setup wizard. Frontend-only. |

---

## Task Details

### 17.01 — Wire Resume Tailor Agent Routes + Frontend [CRITICAL]

**Problem:** Resume Tailor agent exists (`backend/agents/resume_tailor.py`, 187 lines) with `tailor_for_posting()` method. But API routes aren't connected in `agents_routes.py`, and `ResumeTailor.jsx` calls dead endpoints.

**What to do:**
- [ ] Add `POST /api/agents/tailor/<posting_id>` route in `agents_routes.py` calling `resume_tailor.tailor_for_posting()`
- [ ] Add `GET /api/agents/tailor/<posting_id>` route to retrieve existing tailored version
- [ ] Verify `ResumeTailor.jsx` frontend calls match the new route signatures
- [ ] Wire tailored resume storage into `resume_versions` table (source="tailor")
- [ ] Test: create posting → tailor → verify tailored version stored + retrievable

**Delegation:** Backend routes → 5090. Frontend wiring → Expert.
**Depends on:** Nothing.
**Leverages:** `resume_tailor.py`, `agents_routes.py`, `ResumeTailor.jsx`, `resume_versions` table.

---

### 17.02 — Orchestrated Apply Workflow [CRITICAL]

**Problem:** Job Scout, Resume Tailor, Cover Letter, and Application Tracker work independently. No "Apply to this job" button that orchestrates: tailor resume → generate cover letter → move to pipeline → prep interview.

**What to do:**
- [ ] Implement `POST /api/agents/orchestrate/apply` in `agents_routes.py` that calls tailor + cover letter + pipeline move in sequence
- [ ] Return orchestration result with links to each artifact (tailored resume ID, cover letter ID, pipeline status)
- [ ] Add "Quick Apply" button to `JobScout.jsx` posting cards
- [ ] Add orchestration status indicator showing which steps completed
- [ ] Error handling: if tailor fails, still generate cover letter + move to pipeline

**Delegation:** Backend orchestration → 5090. Frontend → Expert.
**Depends on:** 17.01 (Resume Tailor must be wired first).
**Leverages:** `orchestrator.py`, all agent singletons, `job_sessions` table.

---

### 17.03 — Interview Coach Linked from Pipeline [MEDIUM]

**Problem:** When a posting moves to `phone_screen`, `technical`, or `onsite` stage, there's no "Prepare for Interview" button. `interview_coach.start_session()` already accepts `posting_id`.

**What to do:**
- [ ] Add "Prepare" button to `ApplicationPipeline.jsx` for interview stages
- [ ] Button launches Interview Coach with posting context pre-loaded
- [ ] Show existing prep sessions if user already started one for this posting

**Delegation:** Frontend-only → Expert.
**Depends on:** Nothing.
**Leverages:** `InterviewCoachUI.jsx`, `interview_coach.start_session(posting_id=)`.

---

### 17.04 — Cover Letter Prompt on Pipeline Transition [MEDIUM]

**Problem:** When moving a posting to `applied` status, no prompt to generate a cover letter. `cover_letter.generate()` exists.

**What to do:**
- [ ] Add confirmation dialog to `ApplicationPipeline.jsx` when moving to "applied" stage
- [ ] Dialog asks: "Generate a cover letter for this application?" with Yes/Skip
- [ ] On Yes, call `api.generateCoverLetter(postingId)` and show result

**Delegation:** Frontend-only → Expert.
**Depends on:** Nothing.
**Leverages:** `CoverLetterUI.jsx`, `cover_letter.generate()`.

---

### 17.05 — Feedback Loop: Application Outcomes → Optimization [HIGH]

**Problem:** `application_feedback` table stores outcomes (rejected/interview/offer) but data doesn't feed back into resume optimization, skills gap analysis, or interview prep. "Rejected 5x for Kubernetes roles" insight is lost.

**What to do:**
- [ ] Create `backend/feedback_analyzer.py` — aggregate outcomes by skill, role type, company size
- [ ] Add `GET /api/agents/feedback/insights` endpoint returning: skills correlated with rejection, skills correlated with interviews, resume score vs outcome correlation
- [ ] Feed insights into `skills_gap` endpoint: "You've been rejected for roles requiring X — prioritize this skill"
- [ ] Surface insights in `AnalyticsDashboard.jsx` as "What's Working / What to Improve" panel

**Delegation:** Backend analysis → 5090. Frontend panel → Expert.
**Depends on:** Nothing (application_feedback table already exists).
**Leverages:** `application_feedback` table, `job_postings` skills data, `analytics_routes.py`.

---

### 17.06 — Cross-Posting JD Analysis: Skill Demand Patterns [HIGH]

**Problem:** System stores JDs per posting but doesn't analyze patterns. Can't answer "what skills appear in 80% of my target jobs?"

**What to do:**
- [ ] Add `GET /api/agents/scout/skill-demand` endpoint — aggregate NLP keyword extraction across all postings
- [ ] Return: `{skill: count, percentage_of_postings}` sorted by frequency
- [ ] Cross-reference against user's resume skills to show "market demand vs your coverage"
- [ ] Surface in `AnalyticsDashboard.jsx` skills demand chart

**Delegation:** Backend NLP aggregation → 5090. Frontend chart → Expert.
**Depends on:** Nothing.
**Leverages:** `job_postings.description`, `nlp_engine.extract_skill_phrases()`, existing analytics routes.

---

### 17.07 — Experience Extraction → Resume Builder Auto-populate [HIGH]

**Problem:** Experience extraction creates `resume_versions` as text blobs but doesn't feed structured data (title, employer, bullets, technologies) into the builder's section model. User does the work twice.

**What to do:**
- [ ] Add `POST /api/builder/import-experience/<experience_id>` endpoint
- [ ] Map `extracted_experiences` fields → builder section structure (employer, title, date range, bullet points, technologies)
- [ ] Add "Import to Builder" button on finalized experience cards
- [ ] Builder pre-populates experience section with extracted data

**Delegation:** Backend mapping → 5090. Frontend button → Expert.
**Depends on:** Nothing.
**Leverages:** `extracted_experiences` table, `builder_routes.py`, `ResumeBuilder.jsx`.

---

### 17.08 — Salary Intelligence [HIGH]

**Problem:** Career Advisor has placeholder `salary_benchmark()`. Job postings store `salary_min`/`salary_max` but not surfaced in analytics or negotiation prep.

**What to do:**
- [ ] Implement `salary_benchmark()` in Career Advisor — aggregate salary data from user's postings
- [ ] Add `GET /api/agents/advisor/salary-insights` endpoint returning: median salary by role, salary range for user's target roles, salary vs experience level
- [ ] Surface salary data in posting detail view and pipeline analytics
- [ ] Add negotiation talking points based on salary data + user's deep profile differentiators

**Delegation:** Backend salary analysis → 5090. Frontend display → Expert.
**Depends on:** Nothing.
**Leverages:** `job_postings.salary_min/max`, `career_advisor.py`, deep profile differentiators.

---

### 17.09 — Deep Profile Feeds into Job Scout Scoring [MEDIUM]

**Problem:** Job Scout scoring uses NLP + LLM but doesn't leverage deep profile's higher-order skills, career phases, or differentiators. A job requiring "design thinking" scores low even though deep profile identified it.

**What to do:**
- [ ] In `job_scout.score_posting()`, load deep profile and extract higher-order skills + differentiators
- [ ] Append deep profile skills to the skill matching corpus
- [ ] Weight deep profile skills higher (they're validated across multiple sources)
- [ ] Update LLM scoring prompt to include deep profile context

**Delegation:** Backend-only → 5090.
**Depends on:** Nothing.
**Leverages:** `deep_profile.get_profile()`, `job_scout.py` scoring methods.

---

### 17.10 — Follow-up Reminder Notifications [HIGH]

**Problem:** Pipeline `get_reminders()` computes which applications need follow-up but no push notification, badge, or alert. User must manually check.

**What to do:**
- [ ] Add reminder badge count to Dashboard header (poll `/api/agents/pipeline/reminders` on load)
- [ ] Add browser Notification API integration (request permission, show desktop notifications)
- [ ] Show reminder count on "AI Agents" tab badge
- [ ] Add snooze/dismiss per reminder

**Delegation:** Frontend-only → Expert.
**Depends on:** Nothing.
**Leverages:** `get_reminders()` endpoint, browser Notification API.

---

### 17.11 — Skills Interview Results → Optimization Scoring [MEDIUM]

**Problem:** Skills interview validates/confirms skills through conversation, but confirmed skills don't boost ATS optimization score.

**What to do:**
- [ ] In `optimize_resume()`, query finalized skills interview results for the user
- [ ] Add confirmed skills to the resume skill corpus (with high confidence weight)
- [ ] Adjust scoring: confirmed skills should count even if not explicitly in resume text

**Delegation:** Backend-only → 5090.
**Depends on:** Nothing.
**Leverages:** Skills interview finalized data, `utils.optimize_resume()`.

---

### 17.12 — Cross-Session Optimization Learning [MEDIUM]

**Problem:** Each optimization is independent. System doesn't learn "this resume scored 85 for DevOps but 60 for PM" across sessions.

**What to do:**
- [ ] Add `GET /api/sessions/insights` endpoint — aggregate `job_sessions` by role category + ATS score
- [ ] Return: avg score by role type, best-performing resume version per role, score trends over time
- [ ] Cross-reference with feedback outcomes (from 17.05) to show "your DevOps resume gets interviews, your PM resume doesn't"
- [ ] Surface in analytics dashboard

**Delegation:** Backend aggregation → 5090. Frontend chart → Expert.
**Depends on:** 17.05 (feedback loop for outcome correlation).
**Leverages:** `job_sessions` table (stores `ats_score` + `optimization_result_json`).

---

### 17.13 — Ready-to-Apply Checklist per Posting [MEDIUM]

**Problem:** When applying, user should see completion status: resume tailored? cover letter? interview prep? LinkedIn updated? All data exists in separate tables but no aggregated view.

**What to do:**
- [ ] Add `GET /api/agents/pipeline/<posting_id>/checklist` endpoint
- [ ] Query: tailored resume version exists? cover letter exists? interview coach session exists? campaign post mentioning this role?
- [ ] Return checklist with completion status per item
- [ ] Show checklist in posting detail view in `ApplicationPipeline.jsx`

**Delegation:** Backend query → 5090. Frontend checklist → Expert.
**Depends on:** 17.01 (tailor wired), 17.02 (orchestration).
**Leverages:** All existing tables — cross-query by `posting_id`.

---

### 17.14 — Campaign Post Engagement Tracking [MEDIUM]

**Problem:** Posts are generated and exported but no way to record which performed well. This data should feed into future campaign planning.

**What to do:**
- [ ] Add `impressions`, `reactions`, `comments`, `shares` columns to `campaign_posts` table
- [ ] Add `PUT /api/campaigns/<id>/posts/<post_id>/engagement` endpoint for recording metrics
- [ ] Add engagement input fields to `PostEditor.jsx`
- [ ] Use engagement data in campaign analytics to identify high-performing content patterns

**Delegation:** Backend schema + route → 5090. Frontend inputs → Expert.
**Depends on:** Nothing.
**Leverages:** `campaign_posts` table, `PostEditor.jsx`, campaign analytics.

---

### 17.15 — Guided New-User Onboarding Flow [MEDIUM]

**Problem:** `Onboarding.jsx` is a feature walkthrough, not a guided setup. New user has no clear path: upload resume → import LinkedIn → build deep profile → start searching.

**What to do:**
- [ ] Replace passive walkthrough with active setup wizard (4-5 steps)
- [ ] Step 1: Upload resume OR import LinkedIn profile
- [ ] Step 2: Paste a target job description
- [ ] Step 3: View initial ATS score + skills gap
- [ ] Step 4: Optional: start experience interview or import projects
- [ ] Step 5: "You're ready — start searching" with pre-filled scout criteria
- [ ] Track onboarding completion in user record; skip if already done

**Delegation:** Frontend-only → Expert.
**Depends on:** Nothing (all underlying endpoints exist).
**Leverages:** All existing upload/import/optimize/scout endpoints.

---

## State Tracking

All state is persisted in `roadmap/PHASE17_STATE.json`:
- **Per-task fields:** `status`, `started_at`, `completed_at`, `gate_result`, `gate_assessment`, `files_changed`, `tests_added`
- **Summary metrics:** totals by severity, completion counts, tests added
- **Survives:** session compaction (JSON on disk), machine reboots (file-based), conversation restarts (read from file)

To resume after any interruption:
```bash
cat roadmap/PHASE17_STATE.json | python3 -m json.tool
```

---

## Dependency Graph

```
17.01 (Wire Tailor) ──→ 17.02 (Orchestrate) ──→ 17.13 (Checklist)
                                                      ↑
17.03 (Coach → Pipeline)                              │
17.04 (CL → Pipeline)                                 │
17.05 (Feedback Loop) ──→ 17.12 (Cross-Session)       │
17.06 (JD Patterns)                                    │
17.07 (Exp → Builder)                                  │
17.08 (Salary Intel)                                   │
17.09 (Profile → Scout)                                │
17.10 (Reminders)                                      │
17.11 (Skills → Optimize)                              │
17.14 (Engagement Tracking)
17.15 (Onboarding)
```

Tasks without arrows are independent and can be parallelized.
