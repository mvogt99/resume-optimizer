import contextlib
import sqlite3


def _init_schema_part2(cursor):
    """Execute CREATE TABLE for schema tables 18-24: cover_letters through career_analyses."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cover_letters (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            posting_id TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            greeting TEXT DEFAULT '',
            body TEXT DEFAULT '',
            closing TEXT DEFAULT '',
            tone TEXT DEFAULT 'professional',
            company TEXT DEFAULT '',
            role_title TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # --- Phase 8 Wave 2: Interview coach ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS interview_coach_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            posting_id TEXT DEFAULT '',
            stage TEXT DEFAULT 'prep',
            persona TEXT DEFAULT 'hiring_manager',
            question_count INTEGER DEFAULT 5,
            current_question INTEGER DEFAULT 0,
            context_json TEXT DEFAULT '{}',
            scores_json TEXT DEFAULT '[]',
            overall_assessment_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_complete INTEGER DEFAULT 0
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS interview_coach_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            question_index INTEGER DEFAULT -1,
            score_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # --- Phase 13: Resume templates ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            role_type TEXT NOT NULL DEFAULT 'general',
            base_content TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    # --- Phase 13: LinkedIn profile update tracking ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS linkedin_profile_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            section_name TEXT NOT NULL,
            current_content TEXT DEFAULT '',
            suggested_content TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    # --- Phase 13: Application feedback ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            posting_id TEXT DEFAULT '',
            outcome TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    # --- Phase 12: Career Advisor persistence ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS career_analyses (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            analysis_type TEXT NOT NULL,
            target_role TEXT DEFAULT '',
            result_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )


def _run_migrations(cursor):
    """Run safe ALTER TABLE migrations — no-op if columns already exist."""
    # --- Agentic pipeline columns (safe ALTER TABLE — no-op if already exists) ---
    for col_stmt in [
        "ALTER TABLE project_documents ADD COLUMN classification_json TEXT DEFAULT '{}'",
        "ALTER TABLE client_projects ADD COLUMN skills_json TEXT DEFAULT '[]'",
        "ALTER TABLE client_projects ADD COLUMN correlation_json TEXT DEFAULT '{}'",
        "ALTER TABLE builder_interview_sessions ADD COLUMN cross_source_json TEXT DEFAULT '{}'",
        # Phase 13: Business outcomes extraction
        "ALTER TABLE project_documents ADD COLUMN outcomes_json TEXT DEFAULT '[]'",
        "ALTER TABLE client_projects ADD COLUMN business_outcomes_json TEXT DEFAULT '[]'",
        # Phase 8 Wave 2: Agent cross-references
        "ALTER TABLE job_postings ADD COLUMN tailored_version_id TEXT DEFAULT ''",
        "ALTER TABLE job_postings ADD COLUMN cover_letter_id TEXT DEFAULT ''",
        # Phase C: Multi-user isolation — add user_id to tables missing it
        "ALTER TABLE journey_sources ADD COLUMN user_id INTEGER DEFAULT 0",
        "ALTER TABLE journey_events ADD COLUMN user_id INTEGER DEFAULT 0",
        "ALTER TABLE project_documents ADD COLUMN user_id INTEGER DEFAULT 0",
        # Phase 17.14: Campaign post engagement tracking
        "ALTER TABLE campaign_posts ADD COLUMN impressions INTEGER DEFAULT 0",
        "ALTER TABLE campaign_posts ADD COLUMN reactions INTEGER DEFAULT 0",
        "ALTER TABLE campaign_posts ADD COLUMN comments_count INTEGER DEFAULT 0",
        "ALTER TABLE campaign_posts ADD COLUMN shares INTEGER DEFAULT 0",
        "ALTER TABLE campaign_posts ADD COLUMN published_url TEXT DEFAULT ''",
        # Phase P0-B: FTAL score columns for agent_runs (existing DBs)
        "ALTER TABLE agent_runs ADD COLUMN ftal_f INTEGER",
        "ALTER TABLE agent_runs ADD COLUMN ftal_t INTEGER",
        "ALTER TABLE agent_runs ADD COLUMN ftal_a INTEGER",
        "ALTER TABLE agent_runs ADD COLUMN ftal_gap INTEGER",
        # Phase P1-D: LinkedIn narrative supersession
        "ALTER TABLE journey_narratives ADD COLUMN superseded_at TIMESTAMP",
        # Phase P2-A: Deep profile staleness tracking
        "ALTER TABLE deep_profiles ADD COLUMN source_hash TEXT DEFAULT ''",
        "ALTER TABLE deep_profiles ADD COLUMN is_stale INTEGER DEFAULT 0",
        "ALTER TABLE deep_profiles ADD COLUMN stale_reason TEXT DEFAULT ''",
        "ALTER TABLE deep_profiles ADD COLUMN last_checked_at TIMESTAMP",
        # Phase P2-C: Application feedback loop — stage transition tracking
        "ALTER TABLE application_feedback ADD COLUMN resume_version_id TEXT DEFAULT ''",
        "ALTER TABLE application_feedback ADD COLUMN cover_letter_id TEXT DEFAULT ''",
        "ALTER TABLE application_feedback ADD COLUMN old_stage TEXT DEFAULT ''",
        "ALTER TABLE application_feedback ADD COLUMN new_stage TEXT DEFAULT ''",
        "ALTER TABLE application_feedback ADD COLUMN transitioned_at TIMESTAMP",
        "ALTER TABLE application_feedback ADD COLUMN ats_score REAL DEFAULT 0",
        "ALTER TABLE application_feedback ADD COLUMN cover_letter_score REAL DEFAULT 0",
        "ALTER TABLE application_feedback ADD COLUMN outcome_type TEXT DEFAULT ''",
        # Pre-G8: Acceptance verification columns for agent_runs
        "ALTER TABLE agent_runs ADD COLUMN acceptance_passed INTEGER",
        "ALTER TABLE agent_runs ADD COLUMN acceptance_details TEXT DEFAULT ''",
        "ALTER TABLE agent_runs ADD COLUMN acceptance_attempts INTEGER DEFAULT 1",
        # Test-job flag — mark demo/seed postings so they show a TEST badge in the UI
        "ALTER TABLE job_postings ADD COLUMN is_test INTEGER DEFAULT 0",
    ]:
        try:  # noqa: SIM105
            cursor.execute(col_stmt)
        except sqlite3.OperationalError as e:
            err_msg = str(e).lower()
            if "duplicate column" in err_msg or "no such table" in err_msg:
                pass
            else:
                raise


def _init_schema_part3(cursor):
    """Execute CREATE TABLE for journey_mining_runs, recommendation_drafts, and final tables."""
    # --- Phase 10 v2: Journey Mining Runs Tracking ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS journey_mining_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running',
            opts_json TEXT DEFAULT '{}',
            watermarks_json TEXT DEFAULT '{}',
            sources_scanned INTEGER DEFAULT 0,
            events_added INTEGER DEFAULT 0,
            events_updated INTEGER DEFAULT 0,
            events_deduplicated INTEGER DEFAULT 0,
            error_message TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )

    # --- Phase 15: Recommendation drafts ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendation_drafts (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            target_name TEXT NOT NULL,
            relationship TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            draft_text TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    # --- Database indexes for performance ---
    index_stmts = [
        "CREATE INDEX IF NOT EXISTS idx_resumes_user ON resumes(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_resume_versions_user ON resume_versions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_descriptions_user ON job_descriptions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_postings_user ON job_postings(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_campaigns_user ON campaigns(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_campaign_posts_campaign ON campaign_posts(campaign_id)",
        "CREATE INDEX IF NOT EXISTS idx_search_criteria_user ON search_criteria(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_user ON agent_runs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_experience_sessions_user ON experience_sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_experience_msgs_session ON experience_messages(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_campaign_sessions_user ON campaign_sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_campaign_msgs_session ON campaign_messages(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_sessions_user ON job_sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_client_projects_user ON client_projects(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_cover_letters_user ON cover_letters(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_coach_sessions_user ON interview_coach_sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_coach_msgs_session ON interview_coach_messages(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_docs_client ON project_documents(client_id)",
        "CREATE INDEX IF NOT EXISTS idx_journey_sources_user ON journey_sources(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_journey_events_user ON journey_events(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_docs_user ON project_documents(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_career_analyses_user ON career_analyses(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_resume_templates_user ON resume_templates(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_linkedin_profile_updates_user"
        " ON linkedin_profile_updates(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_application_feedback_user"
        " ON application_feedback(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_recommendation_drafts_user"
        " ON recommendation_drafts(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_resume_interview_sessions_user"
        " ON resume_interview_sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_resume_interview_msgs_session"
        " ON resume_interview_messages(session_id)",
    ]
    for stmt in index_stmts:
        with contextlib.suppress(sqlite3.OperationalError):
            cursor.execute(stmt)


def _init_schema_final(cursor):
    """Execute CREATE TABLE for final schema tables: keyword_equivalencies through keyword_ignores."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS keyword_equivalencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_keyword TEXT NOT NULL,
            equivalent_phrase TEXT NOT NULL,
            confidence REAL DEFAULT 0.8,
            status TEXT DEFAULT 'equivalent',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, job_keyword)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS linkedin_profiles (
            user_id INTEGER PRIMARY KEY,
            profile_json TEXT NOT NULL DEFAULT '{}',
            raw_json TEXT NOT NULL DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    # --- Guided resume interview (from-scratch builder) ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_interview_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            stage TEXT DEFAULT 'welcome',
            sub_stage TEXT DEFAULT '',
            context_json TEXT DEFAULT '{}',
            experience_index INTEGER DEFAULT 0,
            education_index INTEGER DEFAULT 0,
            compiled_text TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_finalized INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_interview_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            stage TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES resume_interview_sessions (id)
        )
    """
    )

    # --- Phase 5: Resume recommendation (multi-resume comparison + session linking) ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_recommendations (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            job_description_text TEXT NOT NULL,
            resume_scores_json TEXT DEFAULT '[]',
            recommended_resume_id INTEGER,
            recommended_version_id INTEGER,
            rationale TEXT,
            user_chosen_resume_id INTEGER,
            user_chosen_version_id INTEGER,
            session_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    # --- Phase A: Alignment analysis persistence ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alignment_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resume_id INTEGER NOT NULL,
            job_id INTEGER,
            gaps_json TEXT DEFAULT '[]',
            requirements_json TEXT DEFAULT '[]',
            candidate_profile_json TEXT DEFAULT '{}',
            scores_json TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, resume_id, job_id)
        )
    """
    )

    # --- Equivalency rewrite history ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rewrite_suggestions_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resume_id INTEGER,
            job_id INTEGER,
            rewrites_json TEXT DEFAULT '[]',
            resolved_keywords_json TEXT DEFAULT '[]',
            label TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    # --- Keyword ignore list (user-configurable, persisted, excludes from scoring) ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS keyword_ignores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, keyword),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    # --- Option C1: Governance audit events ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            details_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_audit_events_user ON audit_events(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type)",
        "CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at)",
    ]:
        with contextlib.suppress(sqlite3.OperationalError):
            cursor.execute(stmt)
