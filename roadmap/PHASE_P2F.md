# Phase P2-F: PostgreSQL Migration

**Branch:** `feature/ro-phase-P2F-postgresql`
**Model:** Sonnet (implementation) + Opus (schema design)
**Addresses:** Finding F4 (R4) — full resolution
**Status:** PENDING
**Depends on:** P1-A (WAL hardening proves concurrent patterns work)
**Estimated tests:** 20-25

---

## Objective

Migrate from SQLite to PostgreSQL for true concurrent write support, production
readiness, and alignment with DQM Local AI (Phase 44 pattern). WAL mode from P1-A
is the interim fix; this phase is the permanent solution.

## Tasks

### P2-F.1: Create database abstraction layer (Sonnet)
- **Test first:** Tests for db_engine module with both SQLite and PostgreSQL backends
- **Implementation:** Follow DQM Local AI pattern (`db_engine.py`):
  - `get_engine()` returns SQLAlchemy engine (SQLite or PostgreSQL)
  - `get_session()` returns scoped session
  - Backend selected via `DATABASE_URL` env var
  - Default: SQLite (backward compatible)
  - PostgreSQL: `postgresql://user:pass@localhost:5432/resume_optimizer`
- **Files:** New `backend/db_engine.py`

### P2-F.2: Convert raw SQL to SQLAlchemy ORM models (Sonnet)
- **Test first:** Tests asserting ORM models match existing table schemas
- **Implementation:** Create SQLAlchemy models for all 17+ tables:
  - users, resumes, job_descriptions, resume_versions
  - experience_sessions, experience_messages, extracted_experiences
  - client_projects, project_documents
  - journey_sources, journey_events, journey_narratives
  - campaign_sessions, campaign_messages, campaigns, campaign_posts
  - batch_jobs, agent_runs, job_postings, search_criteria
  - cover_letters, interview_coach_sessions/messages
  - deep_profiles, role_syntheses
  - linkedin_profiles, career_analyses, application_feedback
- **Files:** Refactor `models.py` or new `backend/orm_models.py`

### P2-F.3: Replace raw SQL calls with ORM (Sonnet)
- **Implementation:** Replace `conn.execute("SELECT ...")` with ORM queries
- **Scope:** All modules using `get_db()` or `sqlite3.connect()`
- **Note:** This is the largest task — 17+ tables across 30+ files

### P2-F.4: PostgreSQL docker-compose service (Sonnet)
- **Implementation:** Add PostgreSQL to `docker-compose.yml`
- **Migration script:** Alembic migration from SQLite export
- **Files:** `docker-compose.yml`, new `alembic/` directory

### P2-F.5: Data migration validation (Sonnet)
- **Test:** Compare row counts and sample data between SQLite and PostgreSQL
- **Validation:** All 10,475 journey events, 174 narratives, etc. present

## Acceptance Criteria

- [ ] Database abstraction layer supports both backends
- [ ] SQLAlchemy ORM models for all tables
- [ ] Raw SQL replaced with ORM queries
- [ ] PostgreSQL docker service running
- [ ] Data migration verified
- [ ] All existing tests pass with both backends
- [ ] `DATABASE_URL` env var switches backend

## User Gate P2-F

**Present:** Schema comparison, row count validation, ORM query examples,
performance comparison (SQLite vs PostgreSQL for concurrent writes).
