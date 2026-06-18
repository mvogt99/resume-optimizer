#!/usr/bin/env python3
"""Correct the Data & AI SME cover letter for the same two facts as the resume:
   PBM=AWS (n/a here) and Fabric = SPR POC vs Azure Databricks (Databricks chosen),
   replacing the inaccurate AHEAD 'Fabric POV -> funded multi-year Fabric roadmap'."""
from docx import Document

SRC = "Mike_Vogt_Principal_Architect_Data_AI_SME_cover_letter_2026-06-09.docx"
OUT = "Mike_Vogt_Principal_Architect_Data_AI_SME_cover_letter_2026-06-17.docx"

doc = Document()  # placeholder to satisfy linters; reassigned below
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


# [5] platform-depth list — drop Fabric from deep depth, elevate Azure Databricks
sub_in(P[5],
    "Azure Data Services, Synapse Analytics, Microsoft Fabric, Databricks on Azure, Azure OpenAI "
    "Service, and Azure AI Foundry",
    "Azure Data Services, Synapse Analytics, Azure Databricks, Azure OpenAI Service, and Azure AI "
    "Foundry, plus hands-on competitive evaluation of Microsoft Fabric")

# [6] rewrite the discovery->solution story to the true SPR Fabric-vs-Databricks POC (Databricks chosen)
set_text(P[6],
    "What I have found consistently drives deal closure in Data & AI pre-sales is a disciplined "
    "progression from discovery to solution vision. At SPR, I ran a hands-on Microsoft Fabric vs. "
    "Azure Databricks proof-of-concept for a medical provider — not a generic demo, but a precision "
    "evaluation that mapped the client's business priorities, data-engineering needs, and decision "
    "criteria to each platform, produced an executive briefing with explicit price-performance and "
    "ROI modeling, and closed with a clear recommendation to standardize on Azure Databricks and a "
    "funded lakehouse build. That pattern — technical discovery, POV design, compelling business "
    "value narrative — is the core motion your role describes. I also guide and mentor architects and "
    "data scientists throughout the engagement lifecycle, ensuring solution consistency, technical "
    "excellence, and alignment with Microsoft Data & AI go-to-market strategy.")

doc.save(OUT)
print(f"Saved: {OUT}")
