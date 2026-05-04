"""Seed client projects (PwC, SPR, NVISIA, PSC Group) for resume builder testing."""

import json

USER_ID = 1  # test@test.com


def seed_client_projects(cursor):
    """Seed approved client projects from LinkedIn work history."""

    projects = [
        {
            "client_name": "PwC — Data as a Product",
            "folder_id": "seed_pwc",
            "folder_name": "PwC Advisory Projects",
            "document_count": 3,
            "analysis_status": "complete",
            "technical_analysis_json": json.dumps(
                {
                    "technologies": [
                        {"name": "Azure", "category": "Cloud Platform"},
                        {"name": "GCP", "category": "Cloud Platform"},
                        {"name": "SAP", "category": "ERP"},
                        {"name": "Oracle", "category": "ERP"},
                        {"name": "Salesforce", "category": "CRM"},
                        {"name": "Databricks", "category": "Data Platform"},
                        {"name": "Data Governance", "category": "Methodology"},
                        {"name": "DataOps", "category": "Methodology"},
                    ],
                    "outcomes": [
                        "Directed team of 50 and oversaw $5M budget for enterprise cloud-native data platforms",  # noqa: E501
                        "Designed operating model and activation for multiple clients end-to-end",
                        "Built pre-built mappings from ERP/CRM into source-agnostic canonical models",  # noqa: E501
                        "Led accelerator initiative across Azure, AWS, and GCP with reusable Analytics assets",  # noqa: E501
                    ],
                }
            ),
            "governance_analysis_json": json.dumps(
                {
                    "compliance_frameworks": ["SOX", "Data Privacy"],
                    "data_classification": "Enterprise",
                }
            ),
            "role_analysis_json": json.dumps(
                {
                    "contributions": [
                        "Guided design and architecture of complex data governance solutions",
                        "Led data monetization strategy — Data as a Product framework",
                        "Oversaw $5M budget with full P&L responsibility for data platform delivery",  # noqa: E501
                        "Created accelerators reducing implementation time by 40% across cloud providers",  # noqa: E501
                    ],
                    "outcomes": [
                        "Delivered enterprise cloud-native data platforms for multiple Fortune 500 clients",  # noqa: E501
                        "Established reusable canonical data models adopted across 6+ engagements",
                    ],
                }
            ),
            "approved": 1,
        },
        {
            "client_name": "SPR — Data, Analytics & ML Practice",
            "folder_id": "seed_spr",
            "folder_name": "SPR Practice Materials",
            "document_count": 2,
            "analysis_status": "complete",
            "technical_analysis_json": json.dumps(
                {
                    "technologies": [
                        {"name": "Azure", "category": "Cloud Platform"},
                        {"name": "AWS", "category": "Cloud Platform"},
                        {"name": "Machine Learning", "category": "AI/ML"},
                        {"name": "Python", "category": "Language"},
                        {"name": "Business Intelligence", "category": "Analytics"},
                        {"name": "Data Engineering", "category": "Data"},
                    ],
                    "outcomes": [
                        "Increased practice profitability by 40% and capacity by 300% in under 1 year",  # noqa: E501
                        "Increased revenue by $4.5M through modern technologies and service offerings",  # noqa: E501
                        "Grew service offering portfolio by 400% emphasizing cloud, AI, and ML solutions",  # noqa: E501
                    ],
                }
            ),
            "governance_analysis_json": json.dumps({}),
            "role_analysis_json": json.dumps(
                {
                    "contributions": [
                        "Turnaround of Data, Analytics, and ML practice from underperforming to profitable",  # noqa: E501
                        "Provided executive advisory on data strategy and analytics maturity roadmaps",  # noqa: E501
                        "Improved revenue predictability by 40% through long-term pipeline development",  # noqa: E501
                        "Supervised team of full-time and contract consultants across multi-million dollar engagements",  # noqa: E501
                    ],
                    "outcomes": [
                        "Practice revenue grew $4.5M within first year of leadership",
                        "Service portfolio expanded 400% with cloud, AI, and ML focus",
                    ],
                }
            ),
            "approved": 1,
        },
        {
            "client_name": "NVISIA — Data Analytics Practice",
            "folder_id": "seed_nvisia",
            "folder_name": "NVISIA Projects",
            "document_count": 2,
            "analysis_status": "complete",
            "technical_analysis_json": json.dumps(
                {
                    "technologies": [
                        {"name": "Data Architecture", "category": "Architecture"},
                        {"name": "Data Engineering", "category": "Data"},
                        {"name": "Data Management", "category": "Governance"},
                        {"name": "Risk Assessment Engines", "category": "Domain"},
                        {"name": "Enterprise Data Management", "category": "Data"},
                    ],
                    "outcomes": [
                        "Reduced engagement costs by 15% through reusable assets and accelerators",
                        "Increased annual revenue $1.5M through service delivery and new capabilities",  # noqa: E501
                        "Grew Data Analytics practice from zero to $3M with 40% profit margin",
                    ],
                }
            ),
            "governance_analysis_json": json.dumps({}),
            "role_analysis_json": json.dumps(
                {
                    "contributions": [
                        "Created new Data Analytics Practice from scratch — strategy, service catalog, team",  # noqa: E501
                        "Led delivery of risk assessment engine for healthcare payor's underwriting unit",  # noqa: E501
                        "Established first Enterprise Data Management capability at major benefits company",  # noqa: E501
                        "Led teams of PMs, BAs, consultants, and architects on custom app dev projects",  # noqa: E501
                    ],
                    "outcomes": [
                        "Data Analytics practice grew from zero to $3M revenue with 40% margins",
                        "Established reusable asset library reducing engagement costs 15%",
                    ],
                }
            ),
            "approved": 1,
        },
        {
            "client_name": "PSC Group — Enterprise Data & Open Source",
            "folder_id": "seed_psc",
            "folder_name": "PSC Group Projects",
            "document_count": 1,
            "analysis_status": "complete",
            "technical_analysis_json": json.dumps(
                {
                    "technologies": [
                        {"name": "Java", "category": "Language"},
                        {"name": "J2EE", "category": "Framework"},
                        {"name": "Open Source", "category": "Methodology"},
                        {"name": "Data Warehousing", "category": "Data"},
                        {"name": "ODS", "category": "Data"},
                        {"name": "Event-Driven Integration", "category": "Architecture"},
                        {"name": "SOA", "category": "Architecture"},
                    ],
                    "outcomes": [
                        "Launched Open-source Application Development practice, growing revenue from zero to $2M",  # noqa: E501
                        "Exceeded margin targets by 5% within first year with minimal investment",
                        "Managed 4-year enterprise data management project at global Futures Clearing Merchant",  # noqa: E501
                    ],
                }
            ),
            "governance_analysis_json": json.dumps({}),
            "role_analysis_json": json.dumps(
                {
                    "contributions": [
                        "Established Open-source Application Development practice including pursuits and marketing",  # noqa: E501
                        "Directed enterprise data management at global Futures Clearing Merchant for 4 years",  # noqa: E501
                        "Managed all logical/physical data modeling for global ODS and data warehouse",  # noqa: E501
                        "Designed event-driven integration platform feeding ODS and data warehouse",
                    ],
                    "outcomes": [
                        "Open-source practice grew from zero to $2M revenue exceeding margin targets",  # noqa: E501
                        "Enterprise data platform supported global futures clearing operations",
                    ],
                }
            ),
            "approved": 1,
        },
    ]

    for proj in projects:
        cursor.execute(
            "INSERT INTO client_projects "
            "(user_id, client_name, folder_id, folder_name, document_count, "
            "analysis_status, technical_analysis_json, governance_analysis_json, "
            "role_analysis_json, approved) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                USER_ID,
                proj["client_name"],
                proj["folder_id"],
                proj["folder_name"],
                proj["document_count"],
                proj["analysis_status"],
                proj["technical_analysis_json"],
                proj["governance_analysis_json"],
                proj["role_analysis_json"],
                proj["approved"],
            ),
        )

    print(f"  Inserted {len(projects)} client projects (approved)")
