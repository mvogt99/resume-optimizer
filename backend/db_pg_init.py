"""PostgreSQL DDL for init_db().

Called from models.init_db() when DATABASE_URL is a PostgreSQL URL.
All AUTOINCREMENT → SERIAL translations are done here; SQLite-only
PRAGMA statements are omitted.
"""

from __future__ import annotations

_CREATE_TABLES = [
    """CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS resumes (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS job_descriptions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS resume_versions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        source TEXT NOT NULL,
        source_id TEXT DEFAULT '',
        file_name TEXT NOT NULL,
        file_type TEXT DEFAULT '',
        parsed_text TEXT DEFAULT '',
        metadata_json TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS client_projects (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        client_name TEXT NOT NULL,
        folder_id TEXT NOT NULL,
        folder_name TEXT DEFAULT '',
        document_count INTEGER DEFAULT 0,
        analysis_status TEXT DEFAULT 'pending',
        technical_analysis_json TEXT DEFAULT '{}',
        governance_analysis_json TEXT DEFAULT '{}',
        role_analysis_json TEXT DEFAULT '{}',
        approved INTEGER DEFAULT 0,
        skills_json TEXT DEFAULT '[]',
        correlation_json TEXT DEFAULT '{}',
        business_outcomes_json TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS project_documents (
        id SERIAL PRIMARY KEY,
        client_id INTEGER NOT NULL,
        file_id TEXT NOT NULL,
        file_name TEXT NOT NULL,
        mime_type TEXT DEFAULT '',
        file_type TEXT DEFAULT '',
        folder_path TEXT DEFAULT '',
        parsed_text TEXT DEFAULT '',
        text_length INTEGER DEFAULT 0,
        analysis_json TEXT DEFAULT '{}',
        classification_json TEXT DEFAULT '{}',
        outcomes_json TEXT DEFAULT '[]',
        status TEXT DEFAULT 'pending',
        error_message TEXT DEFAULT '',
        user_id INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES client_projects (id)
    )""",
    """CREATE TABLE IF NOT EXISTS journey_sources (
        id SERIAL PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_path TEXT DEFAULT '',
        content_hash TEXT DEFAULT '',
        title TEXT DEFAULT '',
        content_preview TEXT DEFAULT '',
        full_text TEXT DEFAULT '',
        classification TEXT DEFAULT '',
        event_date TEXT DEFAULT '',
        metadata_json TEXT DEFAULT '{}',
        user_id INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS journey_events (
        id SERIAL PRIMARY KEY,
        event_date TEXT DEFAULT '',
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        category TEXT DEFAULT '',
        source_ids TEXT DEFAULT '[]',
        technologies TEXT DEFAULT '[]',
        metrics TEXT DEFAULT '{}',
        confidence REAL DEFAULT 0.5,
        user_id INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS event_attribution (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        source_id INTEGER NOT NULL UNIQUE,
        client_project_id INTEGER,
        workdir_category TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS journey_narratives (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        narrative_type TEXT NOT NULL,
        title TEXT DEFAULT '',
        content TEXT DEFAULT '',
        source_event_ids TEXT DEFAULT '[]',
        approved INTEGER DEFAULT 0,
        approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS campaign_sessions (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        stage TEXT DEFAULT 'theme',
        context_json TEXT DEFAULT '{}',
        campaign_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_finalized INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS campaign_messages (
        id SERIAL PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES campaign_sessions (id)
    )""",
    """CREATE TABLE IF NOT EXISTS campaigns (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        session_id TEXT DEFAULT '',
        theme TEXT DEFAULT '',
        audience TEXT DEFAULT '',
        tone TEXT DEFAULT '',
        storyline TEXT DEFAULT '',
        cadence TEXT DEFAULT '',
        status TEXT DEFAULT 'draft',
        post_count INTEGER DEFAULT 0,
        metadata_json TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS campaign_posts (
        id SERIAL PRIMARY KEY,
        campaign_id INTEGER NOT NULL,
        position INTEGER DEFAULT 0,
        title TEXT DEFAULT '',
        content TEXT DEFAULT '',
        hashtags TEXT DEFAULT '',
        source_refs TEXT DEFAULT '[]',
        char_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'draft',
        scheduled_date TEXT DEFAULT '',
        feedback TEXT DEFAULT '',
        draft_history TEXT DEFAULT '[]',
        impressions INTEGER DEFAULT 0,
        reactions INTEGER DEFAULT 0,
        comments_count INTEGER DEFAULT 0,
        shares INTEGER DEFAULT 0,
        published_url TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
    )""",
    """CREATE TABLE IF NOT EXISTS job_sessions (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        session_name TEXT DEFAULT '',
        resume_id INTEGER,
        resume_version_id INTEGER,
        job_description_text TEXT DEFAULT '',
        optimization_result_json TEXT DEFAULT '{}',
        ats_score REAL DEFAULT 0,
        status TEXT DEFAULT 'draft',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS job_postings (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        company TEXT DEFAULT '',
        location TEXT DEFAULT '',
        url TEXT DEFAULT '',
        source TEXT DEFAULT '',
        description TEXT DEFAULT '',
        salary_min REAL DEFAULT 0,
        salary_max REAL DEFAULT 0,
        is_remote INTEGER DEFAULT 0,
        match_score REAL DEFAULT 0,
        llm_score_json TEXT DEFAULT '{}',
        skills_overlap TEXT DEFAULT '[]',
        skills_missing TEXT DEFAULT '[]',
        status TEXT DEFAULT 'discovered',
        is_starred INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        posted_date TEXT DEFAULT '',
        tailored_version_id TEXT DEFAULT '',
        cover_letter_id TEXT DEFAULT '',
        discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS search_criteria (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        search_name TEXT DEFAULT 'Default',
        target_roles TEXT DEFAULT '[]',
        locations TEXT DEFAULT '[]',
        remote_preference TEXT DEFAULT 'any',
        salary_min REAL DEFAULT 0,
        industries TEXT DEFAULT '[]',
        excluded_companies TEXT DEFAULT '[]',
        keywords TEXT DEFAULT '[]',
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS agent_runs (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        agent_type TEXT NOT NULL,
        task_description TEXT DEFAULT '',
        input_json TEXT DEFAULT '{}',
        output_json TEXT DEFAULT '{}',
        model_used TEXT DEFAULT '',
        task_type TEXT DEFAULT '',
        duration_ms INTEGER DEFAULT 0,
        status TEXT DEFAULT 'running',
        error_message TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS cover_letters (
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
    )""",
    """CREATE TABLE IF NOT EXISTS interview_coach_sessions (
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
    )""",
    """CREATE TABLE IF NOT EXISTS interview_coach_messages (
        id SERIAL PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        question_index INTEGER DEFAULT -1,
        score_json TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS resume_templates (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        role_type TEXT NOT NULL DEFAULT 'general',
        base_content TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS linkedin_profile_updates (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        section_name TEXT NOT NULL,
        current_content TEXT DEFAULT '',
        suggested_content TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS application_feedback (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        posting_id TEXT DEFAULT '',
        outcome TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS career_analyses (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        analysis_type TEXT NOT NULL,
        target_role TEXT DEFAULT '',
        result_json TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS recommendation_drafts (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        target_name TEXT NOT NULL,
        relationship TEXT DEFAULT '',
        subject TEXT DEFAULT '',
        draft_text TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS linkedin_profiles (
        user_id INTEGER PRIMARY KEY,
        profile_json TEXT NOT NULL DEFAULT '{}',
        raw_json TEXT NOT NULL DEFAULT '{}',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""",
    """CREATE TABLE IF NOT EXISTS resume_interview_sessions (
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
    )""",
    """CREATE TABLE IF NOT EXISTS resume_interview_messages (
        id SERIAL PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        stage TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES resume_interview_sessions (id)
    )""",
    """CREATE TABLE IF NOT EXISTS journey_mining_runs (
        id SERIAL PRIMARY KEY,
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
        error_message TEXT DEFAULT ''
    )""",
    # --- Tables formerly created only lazily (SQLite-only) by feature modules ---
    """CREATE TABLE IF NOT EXISTS ats_improvement_sessions(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, resume_id TEXT, job_desc_text TEXT, original_resume_text TEXT, optimized_resume_text TEXT, score_json TEXT DEFAULT '{}', stage TEXT DEFAULT 'diagnose', improvement_focus TEXT DEFAULT '', pending_suggestions_json TEXT DEFAULT '[]', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_finalized INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS ats_improvement_messages(id SERIAL PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS batch_jobs(id TEXT PRIMARY KEY, job_type TEXT NOT NULL, status TEXT DEFAULT 'pending', user_id INTEGER NOT NULL, params_json TEXT DEFAULT '{}', progress_json TEXT DEFAULT '{}', result_json TEXT DEFAULT '{}', error_message TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, started_at TIMESTAMP, completed_at TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS builder_interview_sessions(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, builder_session_id TEXT NOT NULL, job_text TEXT DEFAULT '', gaps_json TEXT DEFAULT '[]', extracted_json TEXT DEFAULT '[]', stage TEXT DEFAULT 'active', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, cross_source_json TEXT DEFAULT '{}', FOREIGN KEY (user_id) REFERENCES users (id))""",
    """CREATE TABLE IF NOT EXISTS builder_interview_messages(id SERIAL PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (session_id) REFERENCES builder_interview_sessions (id))""",
    """CREATE TABLE IF NOT EXISTS deep_interview_sessions(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, profile_id TEXT, mode TEXT DEFAULT 'comprehensive', job_text TEXT DEFAULT '', working_profile_json TEXT DEFAULT '{}', depth_assessment_json TEXT DEFAULT '{}', is_finalized INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS deep_interview_messages(id SERIAL PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, area TEXT DEFAULT '', profile_updates_json TEXT DEFAULT '[]', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS role_syntheses(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, profile_id TEXT NOT NULL, job_text_hash TEXT NOT NULL, job_title TEXT DEFAULT '', synthesis_json TEXT DEFAULT '{}', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS experience_sessions(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, employer TEXT DEFAULT '', client TEXT DEFAULT '', stage TEXT DEFAULT 'intro', context_json TEXT DEFAULT '{}', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_finalized INTEGER DEFAULT 0, FOREIGN KEY (user_id) REFERENCES users (id))""",
    """CREATE TABLE IF NOT EXISTS experience_messages(id SERIAL PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (session_id) REFERENCES experience_sessions (id))""",
    """CREATE TABLE IF NOT EXISTS extracted_experiences(id SERIAL PRIMARY KEY, session_id TEXT NOT NULL, user_id INTEGER NOT NULL, employer TEXT DEFAULT '', client TEXT DEFAULT '', title TEXT DEFAULT '', duration TEXT DEFAULT '', responsibilities TEXT DEFAULT '[]', technologies TEXT DEFAULT '[]', accomplishments TEXT DEFAULT '[]', challenges TEXT DEFAULT '[]', bullet_points TEXT DEFAULT '[]', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (session_id) REFERENCES experience_sessions (id), FOREIGN KEY (user_id) REFERENCES users (id))""",
    """CREATE TABLE IF NOT EXISTS journey_review_sessions(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, review_type TEXT DEFAULT 'timeline', stage TEXT DEFAULT 'overview', context_json TEXT DEFAULT '{}', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_finalized INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS journey_review_messages(id SERIAL PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS builder_sessions(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, base_version_id TEXT, job_text TEXT DEFAULT '', sources_json TEXT DEFAULT '{}', compiled_text TEXT DEFAULT '', status TEXT DEFAULT 'draft', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users (id))""",
    """CREATE TABLE IF NOT EXISTS resume_corrections(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, resume_id TEXT DEFAULT NULL, old_text TEXT NOT NULL, new_text TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_active INTEGER DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS skills_interview_sessions(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, resume_id TEXT DEFAULT '', skills TEXT DEFAULT '[]', stage TEXT DEFAULT 'context', context_json TEXT DEFAULT '{}', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_finalized INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS skills_interview_messages(id SERIAL PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    # --- Central-schema tables present in models_schema*.py but never ported here ---
    """CREATE TABLE IF NOT EXISTS keyword_equivalencies(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, job_keyword TEXT NOT NULL, equivalent_phrase TEXT NOT NULL, confidence REAL DEFAULT 0.8, status TEXT DEFAULT 'equivalent', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users (id), UNIQUE(user_id, job_keyword))""",
    """CREATE TABLE IF NOT EXISTS resume_recommendations(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, job_description_text TEXT NOT NULL, resume_scores_json TEXT DEFAULT '[]', recommended_resume_id INTEGER, recommended_version_id INTEGER, rationale TEXT, user_chosen_resume_id INTEGER, user_chosen_version_id INTEGER, session_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users (id))""",
    """CREATE TABLE IF NOT EXISTS alignment_analyses(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, resume_id INTEGER NOT NULL, job_id INTEGER, gaps_json TEXT DEFAULT '[]', requirements_json TEXT DEFAULT '[]', candidate_profile_json TEXT DEFAULT '{}', scores_json TEXT DEFAULT '[]', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users (id), UNIQUE(user_id, resume_id, job_id))""",
    """CREATE TABLE IF NOT EXISTS rewrite_suggestions_log(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, resume_id INTEGER, job_id INTEGER, rewrites_json TEXT DEFAULT '[]', resolved_keywords_json TEXT DEFAULT '[]', label TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users (id))""",
    """CREATE TABLE IF NOT EXISTS keyword_ignores(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, keyword TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, keyword), FOREIGN KEY (user_id) REFERENCES users (id))""",
    """CREATE TABLE IF NOT EXISTS audit_events(id SERIAL PRIMARY KEY, user_id INTEGER, event_type TEXT NOT NULL, resource_type TEXT, resource_id TEXT, details_json TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS deep_profiles(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, profile_json TEXT DEFAULT '{}', raw_data_json TEXT DEFAULT '{}', source_summary TEXT DEFAULT '', source_hash TEXT DEFAULT '', is_stale INTEGER DEFAULT 0, stale_reason TEXT DEFAULT '', last_checked_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
]

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_rc_user ON resume_corrections(user_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_audit_events_user ON audit_events(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_resumes_user ON resumes(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_resume_versions_user ON resume_versions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_descriptions_user ON job_descriptions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_postings_user ON job_postings(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_campaigns_user ON campaigns(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_campaign_posts_campaign ON campaign_posts(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_search_criteria_user ON search_criteria(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_agent_runs_user ON agent_runs(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_campaign_sessions_user ON campaign_sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_campaign_msgs_session ON campaign_messages(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_sessions_user ON job_sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_client_projects_user ON client_projects(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_cover_letters_user ON cover_letters(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_coach_sessions_user ON interview_coach_sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_coach_msgs_session" " ON interview_coach_messages(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_project_docs_client ON project_documents(client_id)",
    "CREATE INDEX IF NOT EXISTS idx_journey_sources_user ON journey_sources(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_journey_events_user ON journey_events(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_event_attribution_user ON event_attribution(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_project_docs_user ON project_documents(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_career_analyses_user ON career_analyses(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_resume_templates_user ON resume_templates(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_linkedin_profile_updates_user"
    " ON linkedin_profile_updates(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_application_feedback_user" " ON application_feedback(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_recommendation_drafts_user"
    " ON recommendation_drafts(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_resume_interview_sessions_user"
    " ON resume_interview_sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_resume_interview_msgs_session"
    " ON resume_interview_messages(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_journey_mining_runs_user ON journey_mining_runs(user_id)",
]


def pg_init_db(url: str) -> None:
    """Create all tables and indexes in PostgreSQL.

    Called from models.init_db() when DATABASE_URL is a PostgreSQL URL.
    psycopg2 must be installed (pip install psycopg2-binary).
    """
    import psycopg2

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    conn = psycopg2.connect(url)
    cur = conn.cursor()

    for ddl in _CREATE_TABLES:
        cur.execute(ddl)

    for stmt in _CREATE_INDEXES:
        cur.execute(stmt)

    # Create environment-specific user tables with identical schema
    for table_name in ["users_test", "users_prod"]:
        try:
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (LIKE users INCLUDING ALL)")
        except Exception:
            pass  # Table may already exist

    # Ensure role + status columns exist on ALL user tables (idempotent)
    for table_name in ["users", "users_test", "users_prod"]:
        for col_stmt in [
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user'",
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'",
        ]:
            try:
                cur.execute(col_stmt)
            except Exception:
                pass
        # Activate existing users so they aren't locked out
        try:
            cur.execute(
                f"UPDATE {table_name} SET status='active' "
                f"WHERE status='pending' AND created_at < NOW() - INTERVAL '1 minute'"
            )
        except Exception:
            pass

    # Idempotent column-migration list — this is now the only schema-migration
    # mechanism for this app (Postgres is the sole database backend). Each
    # statement is wrapped so one failure (e.g. a table that doesn't exist yet)
    # can't abort the rest.
    for col_stmt in [
        "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS ftal_f INTEGER",
        "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS ftal_t INTEGER",
        "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS ftal_a INTEGER",
        "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS ftal_gap INTEGER",
        "ALTER TABLE journey_narratives ADD COLUMN IF NOT EXISTS superseded_at TIMESTAMP",
        "ALTER TABLE application_feedback ADD COLUMN IF NOT EXISTS "
        "resume_version_id TEXT DEFAULT ''",
        "ALTER TABLE application_feedback ADD COLUMN IF NOT EXISTS "
        "cover_letter_id TEXT DEFAULT ''",
        "ALTER TABLE application_feedback ADD COLUMN IF NOT EXISTS old_stage TEXT DEFAULT ''",
        "ALTER TABLE application_feedback ADD COLUMN IF NOT EXISTS new_stage TEXT DEFAULT ''",
        "ALTER TABLE application_feedback ADD COLUMN IF NOT EXISTS transitioned_at TIMESTAMP",
        "ALTER TABLE application_feedback ADD COLUMN IF NOT EXISTS ats_score REAL DEFAULT 0",
        "ALTER TABLE application_feedback ADD COLUMN IF NOT EXISTS "
        "cover_letter_score REAL DEFAULT 0",
        "ALTER TABLE application_feedback ADD COLUMN IF NOT EXISTS outcome_type TEXT DEFAULT ''",
        "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS acceptance_passed INTEGER",
        "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS acceptance_details TEXT DEFAULT ''",
        "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS acceptance_attempts INTEGER DEFAULT 1",
        "ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS is_test INTEGER DEFAULT 0",
        "ALTER TABLE journey_events ADD COLUMN IF NOT EXISTS significance_score INTEGER DEFAULT 1",
        "ALTER TABLE journey_events ADD COLUMN IF NOT EXISTS cluster_id TEXT DEFAULT ''",
        "ALTER TABLE journey_events ADD COLUMN IF NOT EXISTS is_cluster_head INTEGER DEFAULT 0",
        "ALTER TABLE job_sessions ADD COLUMN IF NOT EXISTS recommendation_id TEXT",
        "ALTER TABLE job_sessions ADD COLUMN IF NOT EXISTS posting_id TEXT",
    ]:
        try:
            cur.execute(col_stmt)
        except Exception:
            conn.rollback()

    conn.commit()
    cur.close()
    conn.close()
