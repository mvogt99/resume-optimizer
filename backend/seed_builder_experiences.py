"""Seed extracted experiences (AHEAD, PwC, SPR) for resume builder testing."""

import json
import uuid

USER_ID = 1  # test@test.com


def seed_extracted_experiences(cursor):
    """Seed extracted experiences from 'interview' sessions."""

    # Create the tables first (experience_chat.py normally does this on init)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS experience_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            employer TEXT DEFAULT '',
            client TEXT DEFAULT '',
            stage TEXT DEFAULT 'intro',
            context_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_finalized INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS experience_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES experience_sessions (id)
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS extracted_experiences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            employer TEXT DEFAULT '',
            client TEXT DEFAULT '',
            title TEXT DEFAULT '',
            duration TEXT DEFAULT '',
            responsibilities TEXT DEFAULT '[]',
            technologies TEXT DEFAULT '[]',
            accomplishments TEXT DEFAULT '[]',
            challenges TEXT DEFAULT '[]',
            bullet_points TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES experience_sessions (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    experiences = [
        {
            "employer": "AHEAD",
            "client": "Multiple Enterprise Clients",
            "title": "Principal Technical Consultant",
            "duration": "Jun 2023 – Present",
            "responsibilities": [
                "Lead data architecture and platform modernization engagements",
                "Provide technical advisory to enterprise clients on cloud data strategy",
                "Design integration architectures connecting legacy systems to cloud platforms",
            ],
            "technologies": [
                "Azure",
                "AWS",
                "GCP",
                "Databricks",
                "Snowflake",
                "Python",
                "Data Architecture",
                "Enterprise Architecture",
            ],
            "accomplishments": [
                "Led cloud data platform migration for Fortune 500 healthcare client",
                "Designed hybrid AI inference pipeline combining local GPU (RTX 5090) with cloud APIs",  # noqa: E501
                "Built autonomous AI gateway orchestrating multi-model workflows on local hardware",
            ],
            "challenges": [
                "Integrating legacy on-premise data warehouses with cloud-native architectures",
                "Balancing cost optimization with performance for AI inference workloads",
            ],
            "bullet_points": [
                "Lead data architecture and cloud platform modernization engagements for enterprise clients across healthcare, finance, and technology sectors",  # noqa: E501
                "Designed hybrid AI inference pipeline combining local GPU acceleration (RTX 5090) with cloud API orchestration, reducing inference costs by 95%",  # noqa: E501
                "Built autonomous AI gateway with multi-model routing, FTAL scoring, and knowledge graph grounding for production workflows",  # noqa: E501
                "Provide technical advisory on data strategy, cloud migration, and enterprise architecture transformation",  # noqa: E501
            ],
        },
        {
            "employer": "PwC",
            "client": "Fortune 500 Financial Services & Manufacturing",
            "title": "Director, Advisory",
            "duration": "Apr 2020 – Jun 2023",
            "responsibilities": [
                "Led Data as a Product strategy for enterprise clients",
                "Oversaw design and architecture of cloud-native data platforms",
                "Managed team of 50 consultants and $5M budget",
            ],
            "technologies": [
                "Azure",
                "GCP",
                "SAP",
                "Oracle",
                "Salesforce",
                "Data Governance",
                "DataOps",
                "Databricks",
                "Power BI",
            ],
            "accomplishments": [
                "Directed team of 50 and oversaw $5M budget driving enterprise cloud-native data platform delivery",  # noqa: E501
                "Created cross-cloud accelerators with pre-built ERP/CRM mappings reducing implementation time 40%",  # noqa: E501
                "Delivered data platform modernization for multiple Fortune 500 clients from ingestion through consumption",  # noqa: E501
            ],
            "challenges": [
                "Coordinating data governance across multiple cloud providers",
                "Standardizing canonical data models across diverse ERP and CRM systems",
            ],
            "bullet_points": [
                "Directed team of 50 and oversaw $5M budget, driving design and delivery of enterprise cloud-native (Azure/GCP) data platforms with operating model design and activation",  # noqa: E501
                "Led accelerator initiative across Azure, AWS, and GCP with pre-built ERP/CRM mappings into source-agnostic canonical models, reducing implementation time by 40%",  # noqa: E501
                "Guided clients to monetize data assets through Data as a Product framework, covering data governance, architecture, and DataOps",  # noqa: E501
                "Delivered end-to-end data platforms from ingestion through consumption including BI and predictive analytics for Fortune 500 clients",  # noqa: E501
            ],
        },
        {
            "employer": "SPR",
            "client": "Enterprise Clients — Healthcare, Finance, Technology",
            "title": "Executive Director - Data, Analytics and Machine Learning",
            "duration": "Jan 2018 – Apr 2020",
            "responsibilities": [
                "Led practice to sell and deliver analytics, BI, AI, and data platform offerings",
                "Supervised team of consultants on multi-million dollar engagements",
                "Provided executive advisory on data strategy and analytics maturity",
            ],
            "technologies": [
                "Azure",
                "AWS",
                "Python",
                "Machine Learning",
                "Business Intelligence",
                "Data Engineering",
                "Tableau",
                "Power BI",
            ],
            "accomplishments": [
                "Turnaround of Data, Analytics, and ML practice — profitability +40%, capacity +300% in <1 year",  # noqa: E501
                "Grew service portfolio by 400% with cloud, AI, and ML focus",
                "Increased revenue by $4.5M through modern technologies and service offerings",
                "Improved revenue predictability by 40% through long-term pipeline development",
            ],
            "challenges": [
                "Reversing declining practice revenue while maintaining client satisfaction",
                "Recruiting and retaining ML/AI talent in competitive market",
            ],
            "bullet_points": [
                "Drove turnaround of Data, Analytics, and ML practice, increasing profitability by 40% and capacity by 300% in less than 1 year, growing revenue by $4.5M",  # noqa: E501
                "Grew service offering portfolio by 400% emphasizing cloud, AI, and ML solutions with improved revenue predictability of 40%",  # noqa: E501
                "Provided advisory services to client executives including data strategy, analytics maturity, and data platform roadmaps",  # noqa: E501
                "Supervised multi-million dollar engagements delivering analytics, BI, AI, and data platform solutions",  # noqa: E501
            ],
        },
    ]

    for exp in experiences:
        session_id = str(uuid.uuid4())

        # Create finalized session
        cursor.execute(
            "INSERT INTO experience_sessions "
            "(id, user_id, employer, client, stage, context_json, is_finalized) "
            "VALUES (?, ?, ?, ?, 'complete', '{}', 1)",
            (session_id, USER_ID, exp["employer"], exp["client"]),
        )

        # Create extracted experience
        cursor.execute(
            "INSERT INTO extracted_experiences "
            "(session_id, user_id, employer, client, title, duration, "
            "responsibilities, technologies, accomplishments, challenges, bullet_points) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                USER_ID,
                exp["employer"],
                exp["client"],
                exp["title"],
                exp["duration"],
                json.dumps(exp["responsibilities"]),
                json.dumps(exp["technologies"]),
                json.dumps(exp["accomplishments"]),
                json.dumps(exp["challenges"]),
                json.dumps(exp["bullet_points"]),
            ),
        )

    print(f"  Inserted {len(experiences)} extracted experiences (with sessions)")
