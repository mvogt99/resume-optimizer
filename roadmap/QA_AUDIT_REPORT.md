# QA Audit Report

**Generated:** 2026-03-08T03:00:43.316651+00:00
**Overall Grade:** C+
**Tests:** 418 across 35 files

## Per-File Tier Breakdown

| File | Tier | Tests | Content% | DB% | Schema% | LLM | Anti-Patterns |
|------|------|-------|----------|-----|---------|-----|---------------|
| test_builder.py | A | 6 | 83.3% | 33.3% | 0.0% | 0 | — |
| test_campaigns.py | A | 8 | 75.0% | 37.5% | 0.0% | 0 | — |
| test_jobs.py | A | 6 | 83.3% | 33.3% | 0.0% | 0 | — |
| test_agents_wave2_live.py | B | 30 | 66.7% | 36.7% | 0.0% | 3 | — |
| test_campaigns_full.py | B | 18 | 55.6% | 44.4% | 0.0% | 0 | — |
| test_commit_gate.py | B | 5 | 0.0% | 0.0% | 0.0% | 0 | — |
| test_experience.py | B | 7 | 71.4% | 28.6% | 0.0% | 0 | — |
| test_journey.py | B | 10 | 80.0% | 30.0% | 0.0% | 0 | — |
| test_pmo_state.py | B | 15 | 0.0% | 0.0% | 0.0% | 0 | — |
| test_qa_audit.py | B | 18 | 0.0% | 11.1% | 0.0% | 0 | — |
| test_schema_guard.py | B | 11 | 0.0% | 0.0% | 9.1% | 0 | — |
| test_sessions.py | B | 6 | 66.7% | 66.7% | 0.0% | 0 | — |
| test_agents.py | C | 13 | 69.2% | 15.4% | 0.0% | 0 | — |
| test_background_jobs.py | C | 6 | 50.0% | 50.0% | 0.0% | 0 | — |
| test_deep_profile_interview.py | C | 12 | 33.3% | 33.3% | 0.0% | 0 | — |
| test_integration_agents.py | C | 6 | 83.3% | 0.0% | 0.0% | 0 | — |
| test_integration_builder.py | C | 4 | 50.0% | 0.0% | 0.0% | 0 | — |
| test_integration_campaigns.py | C | 4 | 100.0% | 0.0% | 0.0% | 0 | — |
| test_integration_experience.py | C | 5 | 60.0% | 0.0% | 0.0% | 0 | — |
| test_integration_jobs.py | C | 3 | 100.0% | 0.0% | 0.0% | 0 | — |
| test_integration_resume.py | C | 4 | 75.0% | 0.0% | 0.0% | 0 | — |
| test_integration_sessions.py | C | 4 | 50.0% | 50.0% | 0.0% | 0 | — |
| test_journey_review.py | C | 14 | 64.3% | 14.3% | 0.0% | 0 | — |
| test_profile.py | C | 7 | 85.7% | 14.3% | 0.0% | 0 | — |
| test_projects.py | C | 8 | 87.5% | 12.5% | 0.0% | 0 | — |
| test_projects_analysis.py | C | 14 | 35.7% | 42.9% | 0.0% | 0 | — |
| test_regression_e2e.py | C | 37 | 48.6% | 0.0% | 0.0% | 0 | — |
| test_resume.py | C | 6 | 66.7% | 0.0% | 0.0% | 0 | — |
| test_uncovered_routes.py | C | 3 | 33.3% | 33.3% | 0.0% | 0 | — |
| test_auth.py | D | 8 | 25.0% | 0.0% | 0.0% | 0 | — |
| test_builder_workflow.py | D | 10 | 30.0% | 20.0% | 0.0% | 2 | — |
| test_e2e_functional.py | D | 52 | 25.0% | 17.3% | 0.0% | 0 | — |
| test_llm_chat_modules.py | D | 31 | 22.6% | 71.0% | 0.0% | 0 | — |
| test_security.py | D | 19 | 15.8% | 0.0% | 0.0% | 0 | — |
| test_external_services.py | F | 8 | 0.0% | 0.0% | 0.0% | 0 | — |

## Department Accountability Matrix

| Department | # Agents | Governed | Ungoverned | Metric | Status |
|-----------|----------|----------|-----------|--------|--------|
| PMO | — | — | — | Session state persisted, phases gated | GOVERNED |
| Architecture | — | — | — | Schemas defined for tested routes | GOVERNED |
| Software Engineering | 3 | 3 | 0 | Zero thread leaks, zero crashes | GOVERNED |
| Resume & Talent | 9 | 9 | 0 | All agents Tier-A tested | GOVERNED |
| Job Management | 2 | 2 | 0 | Maintained Tier-A | GOVERNED |
| Marketing | 2 | 2 | 0 | test_campaigns.py upgraded or deleted | GOVERNED |
| QA/Testing | — | — | — | qa_audit.py enforcing quality gates | GOVERNED |
| DevOps/Frontend | — | — | — | Build passes, E2E tests exist | NO GOVERNANCE |

## Governance Rule Compliance

| Rule | Status | Detail |
|------|--------|--------|
| G-1_no_false_positives | PASS | No anti-patterns detected |
| G-2_honest_reporting | PASS | Honest Assessment generated on request |
| G-3_quality_ratchet | INFORMATIONAL | Enforced by pmo_state.py — compare via session-end |
| G-4_test_code_symmetry | INFORMATIONAL | Flag commits with production changes but no test changes |
| G-5_agent_evaluation | PASS | All agents have test coverage |
| G-6_escalation_protocol | FAIL |  |

---

# Honest Assessment — QA Audit

**Date:** 2026-03-08T03:00:43.316651+00:00
**Overall Grade:** C+
**Total Tests:** 418
**Total Files:** 35

## What Actually Works

- 3 test files at Tier-A quality
- 179 content-validated assertions
- 92 DB-verified assertions

## What Doesn't Work (or Is Untested)

- **test_agents.py**: Tier-C (content=69.2%, db=15.4%)
- **test_auth.py**: Tier-D (content=25.0%, db=0.0%)
- **test_background_jobs.py**: Tier-C (content=50.0%, db=50.0%)
- **test_builder_workflow.py**: Tier-D (content=30.0%, db=20.0%)
- **test_deep_profile_interview.py**: Tier-C (content=33.3%, db=33.3%)
- **test_e2e_functional.py**: Tier-D (content=25.0%, db=17.3%)
- **test_external_services.py**: Tier-F (content=0.0%, db=0.0%)
- **test_integration_agents.py**: Tier-C (content=83.3%, db=0.0%)
- **test_integration_builder.py**: Tier-C (content=50.0%, db=0.0%)
- **test_integration_campaigns.py**: Tier-C (content=100.0%, db=0.0%)
- **test_integration_experience.py**: Tier-C (content=60.0%, db=0.0%)
- **test_integration_jobs.py**: Tier-C (content=100.0%, db=0.0%)
- **test_integration_resume.py**: Tier-C (content=75.0%, db=0.0%)
- **test_integration_sessions.py**: Tier-C (content=50.0%, db=50.0%)
- **test_journey_review.py**: Tier-C (content=64.3%, db=14.3%)
- **test_llm_chat_modules.py**: Tier-D (content=22.6%, db=71.0%)
- **test_profile.py**: Tier-C (content=85.7%, db=14.3%)
- **test_projects.py**: Tier-C (content=87.5%, db=12.5%)
- **test_projects_analysis.py**: Tier-C (content=35.7%, db=42.9%)
- **test_regression_e2e.py**: Tier-C (content=48.6%, db=0.0%)
- **test_resume.py**: Tier-C (content=66.7%, db=0.0%)
- **test_security.py**: Tier-D (content=15.8%, db=0.0%)
- **test_uncovered_routes.py**: Tier-C (content=33.3%, db=33.3%)

## Known Gaps

- **G-6_escalation_protocol**: FAIL —

**Ungoverned departments:**
- DevOps/Frontend: Build passes, E2E tests exist

## Tier Distribution

| Tier | Count |
|------|-------|
| A | 3 |
| B | 9 |
| C | 17 |
| D | 5 |
| F | 1 |

## Recommendations

1. **CRITICAL**: Eliminate all Tier-F files before proceeding
2. Upgrade Tier-D files to at least Tier-C
3. Upgrade 9 Tier-B files to Tier-A (add DB verification)
4. Increase overall content validation from 42.8% to >60%
