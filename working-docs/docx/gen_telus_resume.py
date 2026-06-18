#!/usr/bin/env python3
"""TELUS Senior Manager, Solutions Architecture - Data & AI resume DOCX generator."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from resume_docx_helpers import (
    rf, set_no_borders, set_cell_margins, section_hdr, add_bullet,
    employer_hdr, job_title, job_desc, setup_page, letterhead
)
from docx import Document
from docx.shared import Pt, Inches

OUTPUT = "Mike_Vogt_TELUS_Solutions_Architect_Data_AI_2026-06-11.docx"

doc = Document()
setup_page(doc)

letterhead(
    doc,
    "MICHAEL VOGT",
    "Sugar Grove, IL 60554  •  312-772-4762  •  mvogt99@gmail.com  •  linkedin.com/in/mike-vogt-analytics",
    "DATA & AI SOLUTIONS ARCHITECT — CONSULTING LEADER  |  DATABRICKS · SNOWFLAKE · MULTI-CLOUD · PRE-SALES & DELIVERY"
)

# SUMMARY
section_hdr(doc, "Professional Summary")
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(2)
p.paragraph_format.space_after = Pt(4)
r = p.add_run(
    "Multi-cloud Data & AI solutions architect and consulting leader with 20+ years bridging presale strategy and "
    "project delivery across enterprise data platform transformations at PwC ($5M+ program), AHEAD, SPR ($4.5M "
    "practice from zero), and NVISIA ($3M practice from zero) — exclusively in agency and client-service "
    "environments. Deep, hands-on solutions architecture expertise across the full data and AI spectrum — cloud "
    "data lakehouses (Databricks, Snowflake, Azure Synapse/Fabric), real-time streaming analytics, MLOps "
    "frameworks, and agentic AI systems — with equal production depth across Azure, AWS, and GCP. Recognized for "
    "leading presale scoping and technical design, delivering winning solution architectures, and producing accurate "
    "estimates for team composition, build scope, and resource planning — ensuring data and AI projects are "
    "realistically scoped and staffed for success within time and cost constraints. Equally effective as technical "
    "lead on architecture and discovery engagements and as a roving architectural catalyst parachuting into "
    "in-flight projects to accelerate delivery with platform-specific SME guidance, account-level architectural "
    "direction, or subject matter expertise in data engineering, machine learning, or AI. Track record owning "
    "technology verticals — cloud data platforms, MLOps, and agentic AI — while expanding client accounts through "
    "holistic, outcome-aligned advisory that sees beyond the single data initiative. Fluent in commercial "
    "conversations: budgets, fees, staffing models, and data ROI. Proven ability to translate complex Data & AI "
    "concepts and apply repeatable frameworks and best practices to incorporate new data technologies into "
    "compelling solutions for both engineering teams and C-suite executive stakeholders."
)
rf(r, 9.5)

# CORE COMPETENCIES
section_hdr(doc, "Core Competencies")
core_comps = [
    ("Pre-Sales Scoping, Technical Design & Work Planning",
     "Cloud Data Platforms: Databricks, Snowflake, Azure, AWS, GCP",
     "MLOps Frameworks, CI/CD for ML & Containerized Deployments"),
    ("Technical Discovery, Solution Architecture & Delivery Lead",
     "Data Engineering: Pipelines, Lakehouse & Real-Time Analytics",
     "Agentic AI, LLMs & Machine Learning Model Architectures"),
    ("Executive Advisory, Estimation & Commercial Conversations",
     "Data Governance, Data Products & Domain-Driven Design",
     "Docker, Kubernetes & Scalable ML Infrastructure"),
    ("Roving Catalyst: Cross-Team SME & Architectural Guidance",
     "AWS Bedrock, SageMaker, Azure ML & Vertex AI Platforms",
     "Agile, Continuous Delivery & Rapid Iteration Methodologies"),
    ("Account Expansion, Holistic Client Advisory & Thought Leader",
     "Data Warehousing, Data Lakes, ETL/ELT & Streaming Design",
     "Consulting Methods, Platform Selection & Technology Verticals"),
    ("Mentoring Architects, Engineers & Data Scientists",
     "Architecture Governance, ADRs & Design Authority",
     "Practice Building, Repeatable Frameworks & Delivery Standards"),
]
cc_tbl = doc.add_table(rows=6, cols=3)
cc_tbl.style = 'Table Grid'
set_no_borders(cc_tbl)
for i, row_data in enumerate(core_comps):
    for j, text in enumerate(row_data):
        cell = cc_tbl.rows[i].cells[j]
        set_cell_margins(cell, top=20, bottom=20, left=40, right=40)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run("•  " + text)
        rf(run, 9)
doc.add_paragraph().paragraph_format.space_after = Pt(2)

# EXPERIENCE
section_hdr(doc, "Professional Experience")

employer_hdr(doc, "AHEAD", "Chicago, IL", "2023 – April 2026")
job_title(doc, "Senior Consulting Solutions Architect — Data & AI")
job_desc(doc,
    "Senior multi-cloud Data & AI solutions architect — leading presale discovery, technical architecture, and "
    "delivery governance for enterprise Data & AI engagements across healthcare, PBM, and manufacturing clients "
    "on Azure, Databricks, and modern cloud data platforms."
)
for b in [
    "Led technical discovery engagements using consulting methods to understand client business priorities, "
    "decision criteria, and value drivers — introduced structured intake frameworks tying measurable KPIs to "
    "each business objective and Data & AI use case; translated complex data and AI capabilities into compelling "
    "business value narratives for CDO, CTO, and C-suite audiences; guided executive stakeholders through phased "
    "use case activation to deliver value early and often, validated by stakeholder gate approval with illustrative "
    "results, building pipeline momentum for multi-year Data & AI investment decisions",

    "Led cloud data platform POV engagements and innovation workshops to convert early-stage Data & AI conversations "
    "into winning solution architectures — led Microsoft Fabric POV for a healthcare analytics provider, designing "
    "workspace topology, OneLake storage strategy, Fabric Pipeline orchestration, Power BI Premium Direct Lake "
    "semantic model delivery, and dev/test/prod governance framework; produced architecture decision record and "
    "executive roadmap defining the client's multi-year cloud data platform adoption path and expanding the account "
    "into funded implementation work",

    "Designed end-to-end Data & AI solutions articulating business outcomes, technical feasibility, and ROI — "
    "led whiteboarding sessions, architecture reviews, and executive proposals spanning Azure Data Factory, Synapse "
    "Analytics, Databricks, Microsoft Fabric, and Azure Machine Learning; designed scalable data pipelines and "
    "machine learning model architectures; provided accurate software estimation for team composition, build scope, "
    "and work planning using repeatable frameworks; served as architectural authority using Architecture Decision "
    "Records and Architecture Review Boards, resolving design risks and aligning solutions to security standards "
    "and regulatory requirements",

    "Designed MLOps and LLM data foundations — architected feature-ready data products, RAG-enabled semantic "
    "data layers, and vector database integration enabling governed LLM queries against canonical data; governed "
    "ML data lifecycle including training/inference data management, model/data versioning, experiment tracking, "
    "and evaluation telemetry; applied MLOps CI/CD patterns for continuous delivery of machine learning models "
    "in containerized environments using Docker-based deployment pipelines",

    "Governed multi-tenant data platform for a PBM client (3 healthcare organizations, 20+ source systems, "
    "4 data domains) — designed HIPAA-compliant security-by-design architecture: ABAC for PHI field-level access "
    "control, row-level security, consent-aligned retention controls, encryption governance, and end-to-end audit "
    "lineage; column and row-level lineage ensuring only trusted, governed data available through enterprise data catalogs",

    "Guided and mentored architects and data scientists to ensure solution consistency and technical excellence — "
    "player-coach providing technical coaching at each engagement phase; looked for creative ways to leverage each "
    "team member's strengths to contribute to delivery; modeled agile-inspired workflows including rapid iteration "
    "and continuous delivery for data pipelines",

    "Led Databricks vs. Microsoft Fabric and Snowflake vs. Redshift competitive evaluations — produced architecture "
    "decision records and executive briefings articulating business value, ROI, price-performance trade-offs, and "
    "competitive positioning across cloud data platform options; shaped multi-year capital investment decisions "
    "at CPTO-equivalent stakeholder level",
]:
    add_bullet(doc, b)

employer_hdr(doc, "PRICEWATERHOUSECOOPERS (PwC)", "Chicago, IL", "2020 – 2023")
job_title(doc, "Director, Advisory — Data & Analytics")
job_desc(doc,
    "Director-level solutions architect and consulting leader. Governed Data as a Product capability across a "
    "distributed global team of 50+ with $5M+ budget — leading architecture, delivery, and commercial conversations "
    "across Azure, AWS, and GCP multi-cloud enterprise engagements."
)
for b in [
    "Partnered with senior account and practice leadership to qualify Data & AI opportunities, shape solution "
    "strategy, and drive pipeline progression to deal closure — shaped and led executive proposals articulating "
    "business outcomes, technical feasibility, and ROI; grew Data & AI program to $5M+ scale; led commercial "
    "conversations with clients on budgets, fees, and phased investment planning; actively expanded accounts by "
    "identifying adjacent services beyond the initial data initiative, growing single engagements into multi-year "
    "platform programs",

    "Originated domain-driven canonical data model and Data as a Product framework for a global manufacturing "
    "client — led technical discovery using consulting methods to translate business priorities and decision "
    "criteria into a winning Data & AI architecture; modeled enterprise data domains against SAP HANA and Oracle "
    "Financials; provided reusability for core data products across source systems, enabling reuse across the "
    "wider client enterprise; CDM framework adopted as PwC's firm-wide Data as a Product platform foundation "
    "spanning Azure, AWS, and GCP",

    "Established enterprise data governance — data catalog, metadata management, end-to-end lineage, RBAC/ABAC "
    "access controls, expectation-based data quality validation, data stewardship workflows, encryption key "
    "management, and privacy-by-design retention governance; operationalized governance operating models with "
    "intake frameworks tying investments to measurable business outcomes",

    "Extended enterprise data platform from Azure to AWS and GCP under a single canonical configuration metadata "
    "model — prevented architectural fragmentation; produced architecture decision records, maintained "
    "Architectural Review Board governance, and presented unified multi-cloud architecture to C-suite clients; "
    "applied consistent platform selection criteria and estimation frameworks across providers",

    "Directed DataOps and CI/CD governance for data pipeline releases — environment promotion standards, automated "
    "validation gates, rollback procedures, and production readiness reviews; governed continuous delivery "
    "practices across distributed teams using repeatable frameworks and agile-inspired delivery methods",

    "Directed full-stack Data & AI program ($5M+ budget, team of 50+) — owned capital planning, resource "
    "strategy, and architecture governance; provided software estimation for team composition and build scope; "
    "demonstrated commercial acumen and executive presence resolving C-level misalignment in real time",
]:
    add_bullet(doc, b)

employer_hdr(doc, "SPR CONSULTING", "Chicago, IL", "2018 – 2020")
job_title(doc, "Executive Director — Data, Analytics and Machine Learning")
job_desc(doc,
    "Practice owner with full P&L responsibility. Built data and analytics consulting practice from zero — "
    "establishing technology verticals, repeatable delivery frameworks, and agile-inspired delivery governance "
    "for enterprise data platforms on Azure and AWS."
)
for b in [
    "Built data and analytics consulting practice from zero to $4.5M revenue in under 3 years — established Cloud "
    "Data Platform Accelerator (reusable pipeline templates, dimensional modeling frameworks, data governance "
    "scaffolding, and ADR templates) reducing client go-live timelines 40%; led commercial conversations on data "
    "platform investments, closing individual engagements exceeding $500K; applied repeatable estimation and work "
    "planning frameworks to ensure all data and AI projects were scoped and staffed within time and cost constraints",

    "Delivered Azure-native and AWS-native enterprise data platforms for global clients — led end-to-end from "
    "technical discovery through production delivery; designed event-driven, real-time analytics ecosystems with "
    "streaming ingestion, exactly-once delivery semantics, and end-to-end lineage; applied agile delivery methods "
    "and continuous delivery practices for data pipelines with rapid iteration",

    "Established AI/ML data infrastructure capability — designed feature-ready data pipelines, model-ready data "
    "product patterns, MLOps frameworks; developed technology vertical depth in cloud data platforms and ML, "
    "bringing thought leadership and repeatable frameworks and best practices to incorporate new data technologies "
    "into every presale and delivery engagement",

    "Roving catalyst across client engagements — parachuted into in-flight projects to provide architectural "
    "guidance, platform-specific subject matter expertise, or delivery course-correction; expanded account scope "
    "by identifying adjacent Data & AI opportunities aligned to each client's wider enterprise needs",
]:
    add_bullet(doc, b)

employer_hdr(doc, "CAPGEMINI (SOGETI)", "Westchester, IL", "2017 – 2018")
job_title(doc, "Senior Manager — Data & Analytics")
job_desc(doc,
    "Directed enterprise data integration platform modernization — designed cloud-agnostic architecture with "
    "open-source technologies and containerized deployment patterns (Docker); governed onshore/offshore delivery "
    "team with budgets up to $4M, applying agile delivery methods, continuous delivery governance, and production "
    "readiness standards for regulated environments."
)

employer_hdr(doc, "NVISIA", "Chicago, IL", "2012 – 2017")
job_title(doc, "Director, Data Architecture Management")
job_desc(doc,
    "Created company's first Data and Analytics practice — built technology verticals in data warehousing, "
    "cloud modernization, and data governance across healthcare, financial services, insurance, and manufacturing."
)
for b in [
    "Launched Data and Analytics practice from zero to $3M with 40% profit margin — led commercial conversations "
    "on budgets, fees, and data ROI; expanded accounts by identifying adjacent services beyond initial project "
    "scope; built confidence in executive stakeholders through a data operating model emphasizing shared "
    "accountability, team upskilling, and consistent business value",

    "Delivered Power BI and analytics platform solutions, data governance programs, and data warehouse "
    "modernization services — grew annual revenue $1.5M; guided and mentored architects, engineers, and data "
    "scientists ensuring solution consistency and technical excellence; built reusable reference architectures "
    "reducing costs 15%",

    "Roving architectural catalyst across client engagements — provided account-level architecture guidance and "
    "subject matter expertise in data engineering and ML to in-flight project teams; applied agile-inspired "
    "delivery methods and rapid iteration; expanded client engagements holistically by identifying wider "
    "enterprise data and AI needs beyond the initial project scope",
]:
    add_bullet(doc, b)

employer_hdr(doc, "PSC GROUP", "Schaumburg, IL", "2005 – 2012")
job_title(doc, "Vice President, Senior Enterprise Architect")
job_desc(doc,
    "Directed 4-year enterprise data management engagement at a Global Futures Clearing Merchant — designed "
    "canonical data models for financial instruments, contracts, and trading events supporting millions of daily "
    "transactions with 15-minute latency SLAs; established real-time data pipeline architecture and dimensional "
    "schemas for trading analytics. Built Open-Source Application Development practice from zero to $2M. "
    "Developed senior architect talent pipeline through coaching and professional development programs."
)

p_cn = doc.add_paragraph()
p_cn.paragraph_format.space_before = Pt(3)
p_cn.paragraph_format.space_after = Pt(2)
r1 = p_cn.add_run("CAREER NOTES: ")
rf(r1, 9, bold=True)
rf(p_cn.add_run(
    "Senior Technical Architect at HCSC (Illinois Blue Cross Blue Shield) — enterprise data and integration "
    "architecture across regulated multi-state healthcare markets. Senior Rules Engine Architect at Kemper "
    "Insurance — data architecture for P&C regulated policy, rating, and claims workloads."
), 9)

# DATA & AI INNOVATION
section_hdr(doc, "Data & AI Innovation")
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(2)
p.paragraph_format.space_after = Pt(4)
rf(p.add_run(
    "Building production Data & AI platform integrating local GPU inference (vLLM), knowledge graphs (ArangoDB), "
    "RAG-enabled data pipelines, multi-agent AI orchestration, and vector databases (Qdrant) — applying the same "
    "architectural patterns used in Databricks ML, AWS Bedrock, and Azure AI Foundry, built and operated hands-on. "
    "Governing MLOps/LLMOps practices daily: model/data versioning, experiment tracking, evaluation telemetry, "
    "prompt/response logging, safety controls, and human-in-the-loop review gates. Governing continuous delivery "
    "for machine learning models — CI/CD pipelines, Docker-based model packaging, and Kubernetes-orchestrated "
    "deployment governance. Tracking and applying emerging AI platforms — AWS Bedrock, Azure AI Foundry, Google "
    "Vertex AI, and Databricks Model Serving — to deepen technology vertical expertise. Staying current on machine "
    "learning trends (supervised/unsupervised, deep learning, LLMs, agentic AI systems) and proactively "
    "identifying how emerging capabilities can be incorporated into client Data & AI architectures through "
    "repeatable frameworks and best practices."
), 9.5)

# EDUCATION
section_hdr(doc, "Education & Professional Development")
for item in [
    "ME, Concurrent Design Management — Stevens Institute of Technology, Hoboken, NJ",
    "BS, Marine Engineering Systems — United States Merchant Marine Academy, Kings Point, NY",
    "Essentials of Executive Leadership — Booth School of Business, University of Chicago",
    "AWS Cloud Practitioner",
]:
    add_bullet(doc, item, size=9.5, indent=0.15)

# TECHNICAL SKILLS
section_hdr(doc, "Technical Skills")
ts_data = [
    ("Cloud Data Platforms",
     "Databricks: Unity Catalog, Delta Lake, PySpark, Databricks ML, Model Serving\n"
     "Snowflake: data warehousing, data sharing, Snowpark, Snowflake ML\n"
     "Azure: ADF, Synapse Analytics, ADLS Gen2, Microsoft Fabric (OneLake, Fabric Pipelines, Direct Lake), "
     "Azure Purview, Event Hub, Power BI Premium\n"
     "AWS: Glue, S3, Athena, Redshift, Kinesis, Lake Formation, EMR, Step Functions, EventBridge\n"
     "GCP: BigQuery, Dataplex, Pub/Sub, Cloud Storage, Vertex AI, Looker\n"
     "Apache Iceberg, Apache Spark / PySpark, Apache Kafka / Azure Event Hubs"),
    ("Data Platform & Engineering",
     "Python, SQL, PySpark, Apache Airflow, Azure Data Factory\n"
     "Batch and streaming ELT/ETL, metadata-driven pipeline design, real-time analytics\n"
     "Dimensional modeling (star schema, SCDs), data vault, 3NF, semantic modeling\n"
     "Canonical data models, data products, data mesh domain design\n"
     "APIs / data services, enterprise integration patterns"),
    ("Architecture & Delivery",
     "End-to-end solutions architecture: presale discovery → scoping → blueprint → delivery\n"
     "Software estimation, work planning, team composition, project planning within constraints\n"
     "Consulting methods, technical discovery, whiteboarding, architecture reviews\n"
     "Executive proposals, business value narratives, ROI, commercial conversations\n"
     "Agile delivery, rapid iteration, continuous delivery for data and ML\n"
     "Architecture Decision Records, Architecture Review Boards, design authority"),
    ("MLOps / LLMOps & AI Platforms",
     "AWS Bedrock / SageMaker (inference, pipelines, MLflow), Azure ML, Azure OpenAI Service, Azure AI Foundry\n"
     "Google Vertex AI, Databricks Model Serving\n"
     "RAG pipelines, vector databases (Qdrant), feature stores, embedding stores\n"
     "MLOps CI/CD: model versioning, experiment tracking, evaluation telemetry, prompt/response logging\n"
     "Agentic AI orchestration, multi-agent AI frameworks, local GPU inference (vLLM)\n"
     "Human-in-the-loop review gates, Responsible AI governance"),
    ("Data Governance & Security",
     "Azure Purview, AWS Lake Formation / Glue Catalog, Collibra DQ\n"
     "RBAC/ABAC access models, PHI/PII masking, encryption / key management\n"
     "Expectation-based data quality, data stewardship, data classification, auditability\n"
     "Regulated: HIPAA, financial services (capital markets, P&C insurance, CMS), SOC 2 awareness"),
    ("Infrastructure & DevOps",
     "Docker (containerization), Kubernetes (orchestration for scalable ML deployments)\n"
     "CI/CD for data and ML pipelines, Terraform IaC, AWS CloudFormation\n"
     "Git-based pipeline governance, environment promotion (dev/UAT/prod), automated testing\n"
     "Observability, monitoring, production readiness reviews\n"
     "Languages: Python, PySpark, SQL, Java"),
]
ts_tbl = doc.add_table(rows=2, cols=3)
ts_tbl.style = 'Table Grid'
set_no_borders(ts_tbl)
for idx, (category, content) in enumerate(ts_data):
    cell = ts_tbl.rows[idx // 3].cells[idx % 3]
    set_cell_margins(cell, top=30, bottom=30, left=60, right=60)
    p_cat = cell.paragraphs[0]
    p_cat.paragraph_format.space_before = Pt(0)
    p_cat.paragraph_format.space_after = Pt(2)
    rf(p_cat.add_run(category), 9, bold=True)
    for line in content.strip().split("\n"):
        p_line = cell.add_paragraph()
        p_line.paragraph_format.space_before = Pt(0)
        p_line.paragraph_format.space_after = Pt(0)
        rf(p_line.add_run(line.strip()), 8.5)

doc.add_paragraph().paragraph_format.space_after = Pt(2)

# ADDITIONAL INFORMATION
section_hdr(doc, "Additional Information")
add_bullet(doc, "Military: Merchant Marine Engineering Officer, US Navy Reserve", size=9.5, indent=0.15)
add_bullet(doc,
    "Community: Volunteer Marine Engineer for MANATRA — 15+ years mentoring 100+ NROTC students "
    "in marine engineering on active training vessels",
    size=9.5, indent=0.15
)

doc.save(OUTPUT)
print(f"Saved: {OUTPUT}")
