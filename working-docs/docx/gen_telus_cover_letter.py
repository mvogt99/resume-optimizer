#!/usr/bin/env python3
"""TELUS Senior Manager, Solutions Architecture - Data & AI cover letter DOCX generator."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from resume_docx_helpers import rf, section_hdr, setup_page
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUTPUT = "Mike_Vogt_TELUS_Solutions_Architect_Data_AI_cover_letter_2026-06-11.docx"
DARK_BLUE = RGBColor(0x1F, 0x4E, 0x79)

doc = Document()
setup_page(doc)

# ── LETTERHEAD ──────────────────────────────────────────────────────────────
p_name = doc.add_paragraph()
p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_name.paragraph_format.space_before = Pt(0)
p_name.paragraph_format.space_after = Pt(2)
r = p_name.add_run("MICHAEL VOGT")
rf(r, 14, bold=True)
r.font.color.rgb = DARK_BLUE

p_contact = doc.add_paragraph()
p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_contact.paragraph_format.space_before = Pt(0)
p_contact.paragraph_format.space_after = Pt(2)
rc = p_contact.add_run(
    "Sugar Grove, IL 60554  •  312-772-4762  •  mvogt99@gmail.com  •  linkedin.com/in/mike-vogt-analytics"
)
rf(rc, 9.5)

# divider
p_div = doc.add_paragraph()
p_div.paragraph_format.space_before = Pt(2)
p_div.paragraph_format.space_after = Pt(8)
pPr = p_div._p.get_or_add_pPr()
pBdr = OxmlElement('w:pBdr')
bot = OxmlElement('w:bottom')
bot.set(qn('w:val'), 'single')
bot.set(qn('w:sz'), '6')
bot.set(qn('w:space'), '1')
bot.set(qn('w:color'), '1F4E79')
pBdr.append(bot)
pPr.append(pBdr)

# ── DATE & SALUTATION ───────────────────────────────────────────────────────
def body_para(doc, text, space_before=4, space_after=10):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    r = p.add_run(text)
    rf(r, 10)
    return p

body_para(doc, "June 11, 2026", space_before=0, space_after=12)
body_para(doc, "Dear Hiring Manager,", space_before=0, space_after=12)

# ── PARAGRAPH 1: HOOK ───────────────────────────────────────────────────────
body_para(doc,
    "The most valuable consulting I've done wasn't in the presale room or in the delivery stand-up in isolation — "
    "it was the work that connected both. Whether I'm architecting a solution on a discovery whiteboard, leading a "
    "proof-of-value engagement, or coaching a delivery team through a production release, I bring the same "
    "orientation: understand what the client actually needs, design something that can realistically get there, and "
    "make sure the path from architecture to delivery doesn't get lost in translation. The Senior Manager, "
    "Solutions Architecture — Data and AI role at TELUS is that profile exactly: someone who can bridge presale "
    "strategy and project delivery, own a technology vertical, and catalyze both new engagements and in-flight "
    "teams equally well."
)

# ── PARAGRAPH 2: PROOF ──────────────────────────────────────────────────────
body_para(doc,
    "In 20+ years across PwC, AHEAD, SPR, and NVISIA — exclusively in agency and client-service environments — "
    "I've built the track record this role requires on both sides of the engagement lifecycle. At SPR, I built the "
    "data and analytics consulting practice from zero to $4.5M, closing individual engagements exceeding $500K "
    "through executive discovery conversations, repeatable estimation frameworks, and compelling solution proposals "
    "on Azure and AWS. At PwC, I governed a $5M+ multi-cloud Data & AI program across a team of 50+, leading the "
    "commercial conversations — budgets, fees, phased investment planning — and resolving C-level misalignments in "
    "real time. The multi-platform depth TELUS requires is something I've built through real delivery: Databricks "
    "lakehouse and competitive evaluations at AHEAD; Snowflake and Redshift platform selection work; Azure Data "
    "Services, Synapse Analytics, and Microsoft Fabric POVs; AWS-native data platforms at SPR; and GCP as the "
    "third-cloud layer at PwC. That breadth — winning the work, estimating it, staffing it, and delivering it "
    "across Databricks, Snowflake, Azure, and AWS — is what I'd bring to TELUS engagements from day one."
)

# ── PARAGRAPH 3: ROVING CATALYST ────────────────────────────────────────────
body_para(doc,
    "The Roving Catalyst responsibility resonates with me in particular. At SPR and NVISIA, some of my most "
    "impactful work was parachuting into in-flight projects — resolving architectural misalignments, accelerating "
    "stalled builds, and identifying adjacent Data & AI opportunities that expanded account scope beyond the "
    "original engagement. At AHEAD, I led a Microsoft Fabric proof-of-value for a healthcare analytics provider "
    "that began as a presale discovery whiteboard session and ended with a funded multi-year platform roadmap and "
    "implementation contract — because I could carry the architecture from initial conversation through executive "
    "briefing and into delivery plan. That presale-to-delivery continuity is precisely what TELUS describes, and "
    "it reflects how I approach every engagement: qualify the opportunity, shape the solution, estimate "
    "realistically, and stay present through delivery to ensure what was sold is what gets built."
)

# ── PARAGRAPH 4: INNOVATION + CLOSE ─────────────────────────────────────────
body_para(doc,
    "I'm actively building hands-on depth in the platforms TELUS is winning with — MLOps frameworks for CI/CD of "
    "machine learning models in containerized (Docker/Kubernetes) environments, agentic AI system design, RAG "
    "pipelines, and emerging platforms including AWS Bedrock, Azure AI Foundry, Google Vertex AI, and Databricks "
    "Model Serving. I operate multi-agent AI orchestration and local GPU inference daily in a production context, "
    "which gives me genuine technical credibility on the agentic AI and LLM side of the TELUS portfolio. The "
    "combination of multi-cloud data platform delivery depth, presale-to-delivery continuity, roving architectural "
    "catalyst experience, and current MLOps / AI depth feels well-matched to what TELUS is building in this "
    "practice. I'd welcome the opportunity to discuss how I can contribute.",
    space_after=20
)

# ── SIGN-OFF ─────────────────────────────────────────────────────────────────
body_para(doc, "Sincerely,", space_before=0, space_after=36)
body_para(doc, "Michael Vogt", space_before=0, space_after=4)

doc.save(OUTPUT)
print(f"Saved: {OUTPUT}")
