#!/usr/bin/env python3
"""Surgically correct the Data & AI SME resume (2026-06-09) for two facts:
   (1) the PBM platform was on AWS (not Azure/Purview);
   (2) the only Microsoft Fabric work was a SPR POC vs Azure Databricks where
       Databricks was chosen (AHEAD's real work was Azure Databricks lakehouse).
Preserves all formatting; saves a re-dated copy."""
from copy import deepcopy
from docx import Document
from docx.text.paragraph import Paragraph

SRC = "Mike_Vogt_Principal_Architect_Data_AI_SME_2026-06-09.docx"
OUT = "Mike_Vogt_Principal_Architect_Data_AI_SME_2026-06-17.docx"

doc = Document(SRC)
P = doc.paragraphs


def set_text(p, new):
    """Replace a paragraph's text, keeping run[0]'s formatting."""
    if not p.runs:
        p.add_run(new); return
    p.runs[0].text = new
    for r in p.runs[1:]:
        r.text = ""


def sub_in(p, old, new):
    """Replace a substring inside whichever run contains it."""
    for r in p.runs:
        if old in r.text:
            r.text = r.text.replace(old, new)
            return True
    # fall back: collapse to run[0]
    if old in p.text:
        set_text(p, p.text.replace(old, new)); return True
    raise SystemExit(f"NOT FOUND: {old[:60]!r}")


# ---- whole-bullet rewrites (AHEAD) ----
set_text(P[12],
    "•  Led the design and delivery of an Azure Databricks lakehouse as the enterprise Data & AI "
    "foundation — Unity Catalog governance, Delta Lake medallion architecture (bronze/silver/gold), "
    "PySpark engineering pipelines, and ML/feature-ready data products; partnered with client executives "
    "through innovation workshops and proof-of-value engagements to shape the architecture, produced "
    "architecture decision records and an executive roadmap, and converted the engagement into a funded "
    "multi-year platform build")

set_text(P[14],
    "•  Designed data foundations for GenAI and ML initiatives on Azure Databricks — architected "
    "feature-ready data products, RAG-ready semantic data layers, and vector-store integration enabling "
    "governed LLM queries against canonical data; governed the ML data lifecycle including "
    "training/inference data management, model/data lineage, experiment tracking (MLflow), and evaluation "
    "telemetry; established prompt/response logging and safety-control patterns for production GenAI "
    "integration")

set_text(P[15],
    "•  Governed a multi-tenant HIPAA data platform on AWS for a PBM client (3 healthcare "
    "organizations, 20+ source systems, 4 data domains) — designed security-by-design architecture: "
    "attribute-based access control for PHI field-level access, row-level security, consent-aligned "
    "retention controls, encryption governance, and end-to-end audit lineage through an enterprise data "
    "catalog; the governance architecture is platform-portable and maps directly to Azure Purview and "
    "Microsoft Entra")

set_text(P[17],
    "•  Led platform-selection and competitive evaluations for enterprise Data & AI modernization "
    "— produced architecture decision records and executive briefings articulating business value, "
    "ROI, price-performance trade-offs, and competitive positioning across lakehouse and cloud "
    "data-warehouse options; shaped multi-year Data & AI capital investment decisions at CPTO-equivalent "
    "stakeholder level through compelling technical and business value storytelling")

# ---- substring fixes ----
sub_in(P[4],
    "Synapse Analytics, Microsoft Fabric, Databricks on Azure, Azure OpenAI Service, Azure Machine "
    "Learning, and Azure AI Studio",
    "Synapse Analytics, Azure Databricks (Unity Catalog, Delta Lake, PySpark), Azure OpenAI Service, "
    "Azure Machine Learning, and Azure AI Foundry, plus hands-on competitive evaluation of Microsoft Fabric")

sub_in(P[13],
    "Azure Data Factory, Synapse Analytics, Microsoft Fabric, Azure OpenAI Service, and Azure Machine Learning",
    "Azure Databricks, Azure Data Factory, Synapse Analytics, and Azure Machine Learning")

# ---- insert SPR Fabric-vs-Databricks POC bullet after P[30] ----
ref = P[30]
clone = deepcopy(ref._p)
ref._p.addnext(clone)
new_para = Paragraph(clone, ref._parent)
set_text(new_para,
    "•  Ran a hands-on Microsoft Fabric vs. Azure Databricks proof-of-concept for a medical provider "
    "— built and benchmarked both platforms against the client's data-engineering, ML, and "
    "price-performance criteria, then recommended and selected Azure Databricks; produced the architecture "
    "decision record and executive briefing behind the platform decision and the subsequent lakehouse build")

# ---- table cell fixes ----
for tab in doc.tables:
    for row in tab.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                if "Azure Data Services: Synapse Analytics, Fabric, Databricks" in p.text:
                    sub_in(p, "Azure Data Services: Synapse Analytics, Fabric, Databricks",
                              "Azure Data Platform: Synapse, Azure Databricks, ADF")
                if "Microsoft Fabric: OneLake, Fabric Pipelines, Direct Lake" in p.text:
                    sub_in(p,
                        "Microsoft Fabric: OneLake, Fabric Pipelines, Direct Lake, Power BI Premium / "
                        "Embedded, Workspace Governance",
                        "Microsoft Fabric (POC / evaluation): OneLake, Direct Lake, Power BI Premium")

doc.save(OUT)
print(f"Saved: {OUT}")
