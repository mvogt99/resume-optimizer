def _init_schema_part1(cursor):
    """Execute CREATE TABLE for core schema tables 1-17: users through agent_runs."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_descriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            source_id TEXT DEFAULT '',
            file_name TEXT NOT NULL,
            file_type TEXT DEFAULT '',
            parsed_text TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS client_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS project_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            mime_type TEXT DEFAULT '',
            file_type TEXT DEFAULT '',
            folder_path TEXT DEFAULT '',
            parsed_text TEXT DEFAULT '',
            text_length INTEGER DEFAULT 0,
            analysis_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            error_message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES client_projects (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS journey_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_path TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            title TEXT DEFAULT '',
            content_preview TEXT DEFAULT '',
            full_text TEXT DEFAULT '',
            classification TEXT DEFAULT '',
            event_date TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS journey_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date TEXT DEFAULT '',
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT '',
            source_ids TEXT DEFAULT '[]',
            technologies TEXT DEFAULT '[]',
            metrics TEXT DEFAULT '{}',
            confidence REAL DEFAULT 0.5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS journey_narratives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            narrative_type TEXT NOT NULL,
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            source_event_ids TEXT DEFAULT '[]',
            approved INTEGER DEFAULT 0,
            approved_at TIMESTAMP,
            superseded_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            stage TEXT DEFAULT 'theme',
            context_json TEXT DEFAULT '{}',
            campaign_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_finalized INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES campaign_sessions (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            session_name TEXT DEFAULT '',
            resume_id INTEGER,
            resume_version_id INTEGER,
            job_description_text TEXT DEFAULT '',
            optimization_result_json TEXT DEFAULT '{}',
            ats_score REAL DEFAULT 0,
            status TEXT DEFAULT 'draft',
            recommendation_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_postings (
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
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS search_criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_runs (
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
            ftal_f INTEGER,
            ftal_t INTEGER,
            ftal_a INTEGER,
            ftal_gap INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )
