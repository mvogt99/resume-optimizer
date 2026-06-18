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
]

_CREATE_INDEXES = [
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

    conn.commit()
    cur.close()
    conn.close()
