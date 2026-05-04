"""Seed journey narratives (STAR entries, skills, career arcs) for resume builder testing."""

USER_ID = 1  # test@test.com


def seed_journey_narratives(cursor):
    """Seed approved journey narratives — STAR entries, skills, and career narratives."""

    narratives = [
        # STAR entries
        {
            "narrative_type": "star_entry",
            "title": "Cloud Data Platform Transformation at PwC",
            "content": (
                "SITUATION: Multiple Fortune 500 clients needed to modernize legacy data warehouses "  # noqa: E501
                "to cloud-native platforms. TASK: As Director of Advisory, led a team of 50 to design "  # noqa: E501
                "and deliver enterprise data platforms on Azure and GCP. ACTION: Created accelerators "  # noqa: E501
                "with pre-built mappings from SAP, Oracle, and Salesforce into source-agnostic canonical "  # noqa: E501
                "models. Established operating model design and activation framework. RESULT: Delivered "  # noqa: E501
                "cloud-native data platforms for multiple clients. Accelerators reduced implementation "  # noqa: E501
                "time by 40% and were adopted across 6+ subsequent engagements."
            ),
            "source_event_ids": "[]",
        },
        {
            "narrative_type": "star_entry",
            "title": "Data Practice Turnaround at SPR",
            "content": (
                "SITUATION: SPR's Data, Analytics, and ML practice was underperforming with declining "  # noqa: E501
                "revenue. TASK: Hired as Executive Director to reverse the trend and modernize the "
                "practice. ACTION: Introduced modern cloud, AI, and ML service offerings. Grew the "
                "portfolio by 400%. Developed long-term pipeline strategy improving revenue "
                "predictability by 40%. Supervised full-time and contract consultants on multi-million "  # noqa: E501
                "dollar engagements. RESULT: Increased practice profitability by 40%, capacity by 300%, "  # noqa: E501
                "and revenue by $4.5M — all within less than 1 year."
            ),
            "source_event_ids": "[]",
        },
        {
            "narrative_type": "star_entry",
            "title": "New Practice Launch at NVISIA",
            "content": (
                "SITUATION: NVISIA had no Data Analytics offering despite growing market demand. "
                "TASK: Promoted to create a new practice from scratch. ACTION: Defined practice strategy "  # noqa: E501
                "and catalog of Data Architecture, Engineering, and Management services. Led pursuit "  # noqa: E501
                "activities and contract creation. Delivered risk assessment engine for healthcare "
                "underwriting. RESULT: Grew practice from zero to $3M revenue with 40% profit margin. "  # noqa: E501
                "Established reusable assets reducing engagement costs by 15%."
            ),
            "source_event_ids": "[]",
        },
        {
            "narrative_type": "star_entry",
            "title": "Enterprise Data Management at Global Futures Firm",
            "content": (
                "SITUATION: Global Futures Clearing Merchant needed comprehensive enterprise data "
                "management covering ODS, data warehouse, and integration. TASK: Directed the 4-year "  # noqa: E501
                "initiative as VP at PSC Group. ACTION: Managed all logical and physical data modeling. "  # noqa: E501
                "Designed and implemented event-driven integration platform feeding the ODS and data "  # noqa: E501
                "warehouse. Built and mentored team of architects and engineers. RESULT: Delivered "
                "enterprise data platform supporting global futures clearing operations with high "
                "reliability and performance."
            ),
            "source_event_ids": "[]",
        },
        # Skills
        {
            "narrative_type": "skill",
            "title": "Enterprise Architecture",
            "content": (
                "20+ years of enterprise architecture experience across financial services, healthcare, "  # noqa: E501
                "and technology sectors. 117 LinkedIn endorsements. Expertise spans application architecture, "  # noqa: E501
                "integration architecture, data architecture, and solution architecture."
            ),
            "source_event_ids": "[]",
        },
        {
            "narrative_type": "skill",
            "title": "Cloud Data Platforms",
            "content": (
                "Deep expertise in Azure, AWS, and GCP cloud data platforms. Led design and delivery "  # noqa: E501
                "of cloud-native data solutions at PwC and SPR. Created cross-cloud accelerators with "  # noqa: E501
                "pre-built ERP/CRM mappings."
            ),
            "source_event_ids": "[]",
        },
        {
            "narrative_type": "skill",
            "title": "Practice Leadership & P&L Management",
            "content": (
                "Proven track record building and scaling consulting practices from zero. PwC: $5M "
                "budget team of 50. SPR: $4.5M revenue growth in <1 year. NVISIA: zero to $3M, 40% "
                "margins. PSC: zero to $2M, exceeding targets."
            ),
            "source_event_ids": "[]",
        },
        {
            "narrative_type": "skill",
            "title": "Data Strategy & Advisory",
            "content": (
                "Provided advisory services to C-suite executives on data strategy, analytics maturity "  # noqa: E501
                "roadmaps, and data platform transformation (people, process, technology). Guided clients "  # noqa: E501
                "to monetize data assets through Data as a Product framework."
            ),
            "source_event_ids": "[]",
        },
        # Career narratives
        {
            "narrative_type": "career_arc",
            "title": "From Hands-On Engineer to Practice Builder",
            "content": (
                "Career trajectory from hands-on Java/J2EE development and data architecture at PSC Group "  # noqa: E501
                "through progressively senior leadership roles: Director at NVISIA, Executive Director at "  # noqa: E501
                "SPR, Director of Advisory at PwC, and currently Principal Technical Consultant at AHEAD. "  # noqa: E501
                "Consistent theme: building consulting practices from zero and scaling them to multi-million "  # noqa: E501
                "dollar revenue while maintaining technical credibility."
            ),
            "source_event_ids": "[]",
        },
        {
            "narrative_type": "leadership",
            "title": "Team Building & Revenue Growth Pattern",
            "content": (
                "Repeated pattern of entering organizations, identifying gaps, and creating new practice "  # noqa: E501
                "areas. PSC: Open-source dev practice zero to $2M. NVISIA: Data Analytics practice zero "  # noqa: E501
                "to $3M. SPR: Turnaround of existing practice, revenue +$4.5M. PwC: Led team of 50 on "  # noqa: E501
                "$5M budget. Each role combined technical vision with business acumen — growing teams, "  # noqa: E501
                "defining service catalogs, and delivering measurable revenue impact."
            ),
            "source_event_ids": "[]",
        },
    ]

    for n in narratives:
        cursor.execute(
            "INSERT INTO journey_narratives "
            "(user_id, narrative_type, title, content, source_event_ids, approved) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (USER_ID, n["narrative_type"], n["title"], n["content"], n["source_event_ids"]),
        )

    print(f"  Inserted {len(narratives)} journey narratives (approved)")
