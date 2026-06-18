#!/usr/bin/env python3
"""One-page 'war room' cheat card for the 3Cloud Principal Architect - Data & AI SME
2nd-round interview. Dense two-column layout, off-camera reference."""
import sys, os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = "Mike_Vogt_3Cloud_Data_AI_SME_cheatcard_2026-06-17.docx"
DB = RGBColor(0x1F, 0x4E, 0x79)
GR = RGBColor(0x44, 0x44, 0x44)
FONT = "Calibri"


def sf(run, size, bold=False, italic=False, color=None):
    run.font.name = FONT; run.font.size = Pt(size)
    run.font.bold = bold; run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color


def no_borders(table):
    tbl = table._tbl; tblPr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}"); e.set(qn("w:val"), "none")
        borders.append(e)
    tblPr.append(borders)


def cell_pad(cell, l=100, r=140):
    tcPr = cell._tc.get_or_add_tcPr(); m = OxmlElement("w:tcMar")
    for side, val in (("top", 30), ("bottom", 30), ("left", l), ("right", r)):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:w"), str(val)); e.set(qn("w:type"), "dxa")
        m.append(e)
    tcPr.append(m)


def mini_hdr(cell, text):
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text); sf(r, 8.5, bold=True, color=DB)
    pPr = p._p.get_or_add_pPr(); pBdr = OxmlElement("w:pBdr")
    bot = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "4"), ("w:space", "1"), ("w:color", "1F4E79")):
        bot.set(qn(k), v)
    pBdr.append(bot); pPr.append(pBdr)
    return p


def line(cell, text, size=7.6, bold=False, italic=False, bullet=False, color=None, after=1):
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.0
    if bullet:
        p.paragraph_format.left_indent = Inches(0.12)
        p.paragraph_format.first_line_indent = Inches(-0.12)
        rb = p.add_run("• "); sf(rb, size, bold=False, color=DB)
    # support a leading **bold lead:** segment split on first ' — ' or ':'
    r = p.add_run(text); sf(r, size, bold=bold, italic=italic, color=color)
    return p


def lead(cell, head, body, size=7.6, bullet=True):
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(1.5)
    p.paragraph_format.line_spacing = 1.0
    if bullet:
        p.paragraph_format.left_indent = Inches(0.12)
        p.paragraph_format.first_line_indent = Inches(-0.12)
        rb = p.add_run("• "); sf(rb, size, color=DB)
    rh = p.add_run(head); sf(rh, size, bold=True, color=DB)
    rb2 = p.add_run(body); sf(rb2, size)
    return p


doc = Document()
s = doc.sections[0]
s.top_margin = Inches(0.35); s.bottom_margin = Inches(0.3)
s.left_margin = Inches(0.4); s.right_margin = Inches(0.4)
doc.styles["Normal"].font.name = FONT
doc.styles["Normal"].font.size = Pt(7.6)

# ---- HEADER ----
h = doc.add_paragraph(); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
h.paragraph_format.space_after = Pt(0)
r = h.add_run("3CLOUD  ·  PRINCIPAL ARCHITECT — DATA & AI SME  ·  2ND ROUND (60 MIN)"); sf(r, 11, bold=True, color=DB)
h2 = doc.add_paragraph(); h2.alignment = WD_ALIGN_PARAGRAPH.CENTER
h2.paragraph_format.space_before = Pt(0); h2.paragraph_format.space_after = Pt(3)
r = h2.add_run("WAR-ROOM CARD — Michael Vogt — keep off-camera"); sf(r, 7.5, italic=True, color=GR)

# THE FACT banner
fb = doc.add_paragraph(); fb.alignment = WD_ALIGN_PARAGRAPH.CENTER
fb.paragraph_format.space_before = Pt(0); fb.paragraph_format.space_after = Pt(4)
r = fb.add_run("⚑ COGNIZANT NOW OWNS 3CLOUD (closed Jan 1, 2026). ")
sf(r, 8, bold=True, color=RGBColor(0xA0, 0x00, 0x00))
r = fb.add_run("Know it. Frame your PwC/Capgemini years as 'deep Azure specialist inside a global SI' = the asset.")
sf(r, 8)

# ---- TWO COLUMN BODY ----
table = doc.add_table(rows=1, cols=2)
no_borders(table)
table.allow_autofit = False
L, R = table.rows[0].cells
L.width = Inches(3.75); R.width = Inches(3.75)
cell_pad(L, l=0, r=160); cell_pad(R, l=160, r=0)
L.paragraphs[0].text = ""; R.paragraphs[0].text = ""

# ===== LEFT COLUMN =====
mini_hdr(L, "60-SEC PITCH")
line(L, "MS Azure Data & AI technical evangelist + trusted advisor, 20+ yrs consulting. Turn early client "
        "conversations into winning Azure architectures and partner with sales to close.", size=7.6, after=1)
line(L, "Depth: Azure Data Svcs, Synapse, ADF, Azure OpenAI/AI Foundry, Azure Databricks (PwC, AHEAD, SPR). "
        "Built 2 practices from zero; closed $500K+ deals; ran $5M+ / 50-person program; competitive POCs "
        "(Fabric vs Databricks) + Databricks lakehouse delivery driving multi-yr roadmaps. 2024 Data & AI PoY "
        "bench is where I want to be.", size=7.6, after=2)

mini_hdr(L, "3 PILLARS — KEEP RETURNING")
line(L, "Azure Data & AI technical depth", bullet=True)
line(L, "Pre-sales: discovery→whiteboard→POV→close, WITH sellers", bullet=True)
line(L, "Credibility: I've delivered what I sell ($500K+, multi-yr roadmaps)", bullet=True, after=2)

mini_hdr(L, "PRE-SALES MOTION (say it out loud)")
line(L, "Discovery FIRST — priorities, decision criteria, value drivers; tie KPIs to each objective", bullet=True)
line(L, "Qualify — budget, sponsor, timeline, data readiness; qualify honestly", bullet=True)
line(L, "Options not one answer — phased: govern+land lakehouse → prove use case → expand", bullet=True)
line(L, "Prove value fast — time-boxed POV, stakeholder gate, 'value early & often'", bullet=True)
line(L, "Estimate + staff realistically (repeatable frameworks)", bullet=True)
line(L, "Tell the exec value story — outcomes, feasibility, ROI", bullet=True, after=1)
line(L, "Meta: \"I slow down at discovery so the solution's right, then move fast on a value-proving POV.\"",
     italic=True, after=2)

mini_hdr(L, "GAP REFRAMES (don't volunteer)")
lead(L, "Azure certs: ", "AWS CP only. \"Formalizing with AZ-305 / DP-600 — sitting it [DATE].\" SCHEDULE ONE.")
lead(L, "Azure OpenAI/Foundry: ", "\"I run RAG + multi-agent + local GPU inference hands-on — same patterns, "
        "built at the metal.\" Turns gap into depth gain.")
lead(L, "Pre-sales vs practice-builder: ", "\"I've done the whole BD motion solo — partnering WITH a seller is "
        "the easier version; I bring the credibility that converts.\"")

# ===== RIGHT COLUMN =====
mini_hdr(R, "STORY BANK (90 sec each)")
lead(R, "A · Fabric-vs-Databricks POC (SPR, medical provider): ", "Built/tested both; recommended DATABRICKS; ADR+exec briefing. Objective + dual-platform fluency. (Your true Fabric story.)")
lead(R, "B · $4.5M practice / zero (SPR): ", "$500K+ deals, estimation frameworks, accelerator cut go-live 40%.")
lead(R, "C · $5M+ program, 50+ (PwC): ", "Data-as-Product CDM firm-wide; resolved C-level MVP-vs-prod in real time.")
lead(R, "D · HIPAA multi-tenant on AWS (AHEAD): ", "PBM, 20+ sources; ABAC/RLS for PHI, lineage+audit. Regulated cred; arch ports to Azure/Purview. (NOT Azure.)")
lead(R, "E · Platform-selection ADRs: ", "e.g. Snowflake vs Redshift; defend recommendations to a skeptical CFO → capital decisions.")
lead(R, "F · Roving catalyst (SPR/NVISIA): ", "Parachute into in-flight projects; expand accounts; player-coach.")

mini_hdr(R, "TECH ONE-LINERS")
lead(R, "Fabric vs Databricks: ", "BI-led + SaaS-simple → Fabric; engineering/ML + scale → Databricks; often BOTH over one OneLake/Delta. My hands-on Fabric = the POC; deep lakehouse = Databricks.")
lead(R, "RAG on Azure: ", "ingest→chunk→embed→vector (AI Search)→retrieve→Azure OpenAI→orchestrate→ground on canonical data→eval+logging+safety+HITL.")
lead(R, "Governance: ", "Unity Catalog (Databricks) + Purview (estate-wide); medallion bronze→silver→gold.")

mini_hdr(R, "ASK THEM (pick 3-4)")
line(R, "Post-Cognizant: how does the practice / this role operate now?", bullet=True)
line(R, "How is SME success measured — pipeline, POVs, win rate, deals?", bullet=True)
line(R, "Where's demand — Fabric migrations, Databricks, or GenAI/agentic?", bullet=True)
line(R, "How do you use accelerators/IP in pursuits? (I built one, -40% go-live)", bullet=True)
line(R, "First 90 days; what does 'this hire is working' look like at 6 mo?", bullet=True, after=2)

mini_hdr(R, "CLOSE (last 2 min)")
line(R, "\"This is the role I do best — deep Azure Data & AI, evangelist + close, on the best MS bench.\"",
     italic=True)
line(R, "Ask next steps + timeline. \"Anything you want me sharper on? I'll come back on it.\" Same-day thank-you.",
     after=1)

# footer note
f = doc.add_paragraph(); f.alignment = WD_ALIGN_PARAGRAPH.CENTER
f.paragraph_format.space_before = Pt(3); f.paragraph_format.space_after = Pt(0)
r = f.add_run("Posting expires Mon Jun 22 · virtual-first · ⚑FIX RESUME: Fabric=SPR POC (DBX won), PBM=AWS · "
              "Discovery-first · trade-offs · candor · player-coach.")
sf(r, 7, italic=True, color=GR)

# ============================ PAGE 2 — FABRIC & DATABRICKS COMPONENTS ============================
doc.add_page_break()

ph = doc.add_paragraph(); ph.alignment = WD_ALIGN_PARAGRAPH.CENTER
ph.paragraph_format.space_after = Pt(1)
r = ph.add_run("FABRIC & DATABRICKS — TECH COMPONENT MAP (know the building blocks)"); sf(r, 11, bold=True, color=DB)
ph2 = doc.add_paragraph(); ph2.alignment = WD_ALIGN_PARAGRAPH.CENTER
ph2.paragraph_format.space_before = Pt(0); ph2.paragraph_format.space_after = Pt(4)
r = ph2.add_run("Both run on Azure over Delta/OneLake — name the right component per layer."); sf(r, 7.5, italic=True, color=GR)


def shade_cell(cell, hexc):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:fill"), hexc); tcPr.append(sh)


ROWS = [
    ("Layer", "Microsoft Fabric", "Azure Databricks"),
    ("Storage / lake", "OneLake (one logical lake; Delta/Parquet); Shortcuts; Mirroring", "ADLS Gen2 + Delta Lake (UC managed/external); Delta Sharing"),
    ("Table format", "Delta; Iceberg (preview)", "Delta Lake; UniForm (read as Iceberg/Hudi); Iceberg"),
    ("Compute / engine", "Spark (Fabric runtime); SQL analytics endpoint; Warehouse (T-SQL)", "Spark clusters (job/all-purpose); Photon; Serverless SQL warehouses"),
    ("Ingestion", "Data Factory pipelines; Dataflows Gen2; Copy job; Mirroring", "Lakeflow Connect; Auto Loader; Structured Streaming; partner connectors"),
    ("ELT / transform", "Notebooks (PySpark/SQL); Dataflows Gen2; T-SQL", "Notebooks; Lakeflow Declarative Pipelines (was DLT); dbt"),
    ("Orchestration", "Fabric Data Factory pipelines + scheduler", "Lakeflow Jobs (was Workflows); Asset Bundles (DABs)"),
    ("Catalog / govern", "OneLake catalog; Domains; Purview; workspace roles; sensitivity labels", "Unity Catalog (catalog→schema→table); lineage; ABAC, row/column masks"),
    ("Semantic / BI", "Power BI: Direct Lake / Import / DirectQuery; semantic models; Copilot", "Databricks SQL; AI/BI Dashboards; Genie (NL→SQL); Power BI connector"),
    ("Real-time", "Real-Time Intelligence: Eventstream, Eventhouse (KQL), Activator", "Structured Streaming; streaming tables; Kafka / Event Hubs connectors"),
    ("ML", "Data Science: MLflow, SynapseML, AutoML", "Mosaic AI: Feature Store, AutoML, MLflow, Model Registry, Model Serving"),
    ("GenAI / LLM", "Azure OpenAI integration; AI Skills; Fabric Copilot; Copilot Studio", "Mosaic AI: Vector Search, Agent Framework, Foundation Model APIs, AI Gateway"),
    ("DevOps / CI-CD", "Git integration; deployment pipelines (dev/test/prod)", "Asset Bundles (DABs); Terraform provider; Repos"),
    ("Security", "Entra ID; workspace roles; Purview labels; private link", "Unity Catalog perms; Entra/SCIM; secrets; cluster policies; private link"),
    ("Capacity / cost", "Capacity SKU (F-SKU; F64 = Copilot threshold); pause non-prod", "DBUs (job/all-purpose/SQL); serverless; Photon; spot; autoscale"),
]

ct = doc.add_table(rows=0, cols=3); ct.style = "Table Grid"; ct.allow_autofit = False
widths = (Inches(1.15), Inches(3.15), Inches(3.2))
for ri, row in enumerate(ROWS):
    cells = ct.add_row().cells
    for ci, val in enumerate(row):
        cell = cells[ci]; cell.width = widths[ci]
        cell_pad(cell, l=60, r=60)
        p = cell.paragraphs[0]; p.paragraph_format.space_before = Pt(0.5); p.paragraph_format.space_after = Pt(0.5)
        p.paragraph_format.line_spacing = 1.0
        run = p.add_run(val)
        if ri == 0:
            sf(run, 7.4, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF)); shade_cell(cell, "1F4E79")
        else:
            sf(run, 6.7, bold=(ci == 0), color=DB if ci == 0 else None)
            if ri % 2 == 0:
                shade_cell(cell, "EEF2F8")

pf = doc.add_paragraph(); pf.paragraph_format.space_before = Pt(4); pf.paragraph_format.space_after = Pt(0)
r = pf.add_run("Naming gotchas: ")
sf(r, 7, bold=True, color=DB)
r = pf.add_run("Databricks 'Lakeflow' = Connect (ingest) + Declarative Pipelines (was DLT) + Jobs (was Workflows).  "
               "Fabric Direct Lake = query OneLake Delta with no import/refresh.  UniForm = Delta readable as Iceberg.  "
               "Both: medallion bronze→silver→gold.  Pick by center of gravity — BI/SaaS → Fabric; engineering/ML/scale → Databricks; often both over one Delta copy.")
sf(r, 7)

doc.save(OUT)
print(f"Saved: {OUT}")
