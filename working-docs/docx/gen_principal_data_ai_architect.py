#!/usr/bin/env python3
"""Generalized recruiter resume: Principal Data & AI Architect (no JD).
Transforms the generalized base resume (2026-06-05) — AI-forward retitling +
the corrected facts (AHEAD = Azure Databricks lakehouse + AWS HIPAA PBM;
Fabric = SPR POC vs Databricks where Databricks was chosen; Fabric demoted)."""
from copy import deepcopy
from docx import Document
from docx.text.paragraph import Paragraph

SRC = "Mike_Vogt_Principal_Data_Architect_Base_Indeed_2026-06-05.docx"
OUT = "Mike_Vogt_Principal_Data_AI_Architect_2026-06-18.docx"

doc = Document(SRC)
P = doc.paragraphs


def set_text(p, new):
    if not p.runs:
        p.add_run(new); return
    p.runs[0].text = new
    for r in p.runs[1:]:
        r.text = ""


def sub_in(p, old, new):
    for r in p.runs:
        if old in r.text:
            r.text = r.text.replace(old, new); return
    if old in p.text:
        set_text(p, p.text.replace(old, new)); return
    raise SystemExit(f"NOT FOUND: {old[:60]!r}")


def find(substr):
    for idx, p in enumerate(P):
        if substr in p.text:
            return idx
    raise SystemExit(f"PARA NOT FOUND: {substr!r}")


# 1) Title — AI-forward
i = find("PRINCIPAL DATA ARCHITECT")
set_text(P[i], "PRINCIPAL DATA & AI ARCHITECT  —  ENTERPRISE DATA PLATFORMS  ·  AI/ML · GENAI  ·  MULTI-CLOUD")

# 2) Summary opener — elevate AI/ML/GenAI
i = find("Enterprise data architect and consulting leader with 20+ years")
sub_in(P[i],
    "Enterprise data architect and consulting leader with 20+ years defining enterprise data "
    "architectures, governing modern cloud data platforms, and delivering AI-ready data foundations",
    "Enterprise Data & AI architect and consulting leader with 20+ years defining enterprise data and "
    "AI architectures, governing modern cloud data and lakehouse platforms, and delivering AI-ready "
    "data foundations and production ML/GenAI solutions")

# 3) AHEAD PBM bullet — AWS (was cloud-neutral)
i = find("Governed multi-tenant data platform for a PBM client")
sub_in(P[i], "Governed multi-tenant data platform for a PBM client",
              "Governed a multi-tenant HIPAA data platform on AWS for a PBM client")

# 4) AHEAD: replace the (misattributed) Fabric-vs-Databricks eval bullet with the real AHEAD work
i = find("Led Microsoft Fabric vs. Databricks and Snowflake vs. Redshift vendor evaluations")
set_text(P[i],
    "•  Led the design and delivery of an Azure Databricks lakehouse as the enterprise Data & AI "
    "foundation for healthcare and manufacturing clients — Unity Catalog governance, Delta Lake "
    "medallion architecture (bronze/silver/gold), PySpark engineering pipelines, and ML/feature-ready "
    "data products; produced architecture decision records and executive roadmaps, and converted "
    "engagements into funded multi-year platform builds")

# 5) SPR: insert the true Fabric-vs-Databricks POC (Databricks selected) after the practice-build bullet
ref_i = find("Built enterprise data and AI/ML consulting practice from zero to $4.5M")
ref = P[ref_i]
clone = deepcopy(ref._p)
ref._p.addnext(clone)
new_para = Paragraph(clone, ref._parent)
set_text(new_para,
    "•  Ran a hands-on Microsoft Fabric vs. Azure Databricks proof-of-concept for a medical provider "
    "— built and benchmarked both platforms against the client's data-engineering, ML, and "
    "price-performance criteria, then recommended and selected Azure Databricks; produced the "
    "architecture decision record and executive briefing behind the platform decision and the "
    "subsequent lakehouse build")

# 5b) Remove the AWS Cloud Practitioner cert line entirely
for p in list(doc.paragraphs):
    if p.text.strip().endswith("AWS Cloud Practitioner"):
        p._element.getparent().remove(p._element)

# 6) Technical Skills — demote Fabric to POC/evaluation, elevate Azure Databricks
for tab in doc.tables:
    for row in tab.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                if "Microsoft Fabric (OneLake, Fabric Pipelines, Direct Lake)" in p.text:
                    sub_in(p,
                        "Databricks (Unity Catalog, Delta Lake, PySpark), Snowflake, Microsoft Fabric "
                        "(OneLake, Fabric Pipelines, Direct Lake)",
                        "Azure Databricks (Unity Catalog, Delta Lake, PySpark), Snowflake, Microsoft "
                        "Fabric (POC / evaluation: OneLake, Direct Lake)")

doc.save(OUT)
print(f"Saved: {OUT}")
