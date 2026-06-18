#!/usr/bin/env python3
"""Generic Markdown -> DOCX renderer. Handles headings, tables, bullets,
numbered/checkbox lists, blockquotes, horizontal rules, and inline **bold** /
*italic* / `code`. Usage: python md_to_docx.py input.md output.docx [Title]"""
import sys, os, re
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

DARK_BLUE = RGBColor(0x1F, 0x4E, 0x79)
LIGHT_BLUE = RGBColor(0xDD, 0xE7, 0xF2)
GREY = RGBColor(0x55, 0x55, 0x55)
FONT = "Calibri"


def setfont(run, size, bold=False, italic=False, color=None):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color


INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*|`[^`]+?`)")


def add_inline(p, text, size=10, base_bold=False, color=None):
    """Render text with inline **bold**, *italic*, `code` into runs on p."""
    for tok in INLINE.split(text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            r = p.add_run(tok[2:-2]); setfont(r, size, bold=True, color=color)
        elif tok.startswith("*") and tok.endswith("*"):
            r = p.add_run(tok[1:-1]); setfont(r, size, bold=base_bold, italic=True, color=color)
        elif tok.startswith("`") and tok.endswith("`"):
            r = p.add_run(tok[1:-1]); setfont(r, size - 0.5, bold=base_bold, color=GREY)
            r.font.name = "Consolas"
        else:
            r = p.add_run(tok); setfont(r, size, bold=base_bold, color=color)


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:fill"), hex_color)
    tcPr.append(sh)


def hrule(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
    pPr = p._p.get_or_add_pPr(); pBdr = OxmlElement("w:pBdr")
    bot = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "1F4E79")):
        bot.set(qn(k), v)
    pBdr.append(bot); pPr.append(pBdr)


def heading(doc, text, level):
    p = doc.add_paragraph()
    sizes = {1: 15, 2: 12.5, 3: 11}
    p.paragraph_format.space_before = Pt(12 if level <= 2 else 8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    add_inline(p, text, size=sizes.get(level, 11), base_bold=True, color=DARK_BLUE)
    if level <= 2:
        pPr = p._p.get_or_add_pPr(); pBdr = OxmlElement("w:pBdr")
        bot = OxmlElement("w:bottom")
        for k, v in (("w:val", "single"), ("w:sz", "4"), ("w:space", "2"), ("w:color", "BBBBBB")):
            bot.set(qn(k), v)
        pBdr.append(bot); pPr.append(pBdr)


def render_table(doc, rows):
    cols = len(rows[0])
    t = doc.add_table(rows=0, cols=cols)
    t.style = "Table Grid"
    t.allow_autofit = True
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for ci, val in enumerate(row):
            if ci >= cols:
                break
            cell = cells[ci]
            cell.paragraphs[0].text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1); p.paragraph_format.space_after = Pt(1)
            add_inline(p, val.strip(), size=8.5, base_bold=(ri == 0))
            if ri == 0:
                shade(cell, "1F4E79")
                for run in p.runs:
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            elif ri % 2 == 0:
                shade(cell, "EEF2F8")


def split_row(line):
    return [c for c in line.strip().strip("|").split("|")]


def add_image(doc, base_dir, alt, rel_path):
    """Embed an image scaled to fit the page (width/height capped), centered, with a caption."""
    path = rel_path if os.path.isabs(rel_path) else os.path.join(base_dir, rel_path)
    if not os.path.exists(path):
        p = doc.add_paragraph()
        add_inline(p, f"[missing image: {rel_path}]", size=9, color=RGBColor(0xC0, 0x00, 0x00))
        return
    MAXW, MAXH = 6.9, 8.4  # inches (fits 0.7in margins / ~9.8in text height)
    w_in = MAXW
    try:
        from PIL import Image
        with Image.open(path) as im:
            pw, ph = im.size
        if pw and ph:
            w_in = min(MAXW, MAXH * pw / ph)
    except Exception:
        pass
    doc.add_picture(path, width=Inches(w_in))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if alt:
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_before = Pt(1)
        cap.paragraph_format.space_after = Pt(8)
        r = cap.add_run(alt); setfont(r, 8, italic=True, color=GREY)


def convert(md_path, out_path, title=None):
    base_dir = os.path.dirname(os.path.abspath(md_path))
    with open(md_path) as f:
        lines = f.read().split("\n")
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(0.6); s.bottom_margin = Inches(0.6)
        s.left_margin = Inches(0.7); s.right_margin = Inches(0.7)
    norm = doc.styles["Normal"]; norm.font.name = FONT; norm.font.size = Pt(10)

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1; continue

        # horizontal rule
        if re.fullmatch(r"-{3,}", stripped):
            hrule(doc); i += 1; continue

        # fenced code block / ASCII diagram -> preformatted monospace
        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1  # skip closing fence
            for code_line in (buf or [""]):
                cp = doc.add_paragraph()
                cp.paragraph_format.space_before = Pt(0)
                cp.paragraph_format.space_after = Pt(0)
                cp.paragraph_format.line_spacing = 1.0
                pf_pPr = cp._p.get_or_add_pPr()
                sh = OxmlElement("w:shd")
                sh.set(qn("w:val"), "clear"); sh.set(qn("w:fill"), "F2F4F7")
                pf_pPr.append(sh)
                r = cp.add_run(code_line if code_line else " ")
                r.font.name = "Consolas"; r.font.size = Pt(7)
                r.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
            continue

        # standalone image: ![caption](path)
        mimg = re.match(r"^!\[(.*?)\]\((.*?)\)\s*$", stripped)
        if mimg:
            add_image(doc, base_dir, mimg.group(1), mimg.group(2)); i += 1; continue

        # headings
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            heading(doc, m.group(2), len(m.group(1))); i += 1; continue

        # table: a line with | and the next line a separator row
        if stripped.startswith("|") and i + 1 < len(lines) and re.search(r"\|?\s*:?-{2,}", lines[i + 1]):
            rows = []
            rows.append(split_row(stripped))
            i += 2  # skip header + separator
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i].strip())); i += 1
            render_table(doc, rows); continue

        # blockquote (collect consecutive > lines)
        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip()); i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(6)
            pPr = p._p.get_or_add_pPr(); pBdr = OxmlElement("w:pBdr")
            left = OxmlElement("w:left")
            for k, v in (("w:val", "single"), ("w:sz", "18"), ("w:space", "8"), ("w:color", "1F4E79")):
                left.set(qn(k), v)
            pBdr.append(left); pPr.append(pBdr)
            add_inline(p, " ".join(buf), size=10, base_bold=False, color=DARK_BLUE)
            continue

        # checkbox / bullet / numbered list
        mb = re.match(r"^(\s*)([-*])\s+(\[[ xX]\]\s+)?(.*)$", raw)
        mn = re.match(r"^(\s*)(\d+)\.\s+(.*)$", raw)
        if mb:
            indent = len(mb.group(1))
            box = mb.group(3)
            txt = mb.group(4)
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.left_indent = Inches(0.25 + (0.25 if indent >= 2 else 0))
            p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(2)
            if box:
                r = p.add_run("☐  "); setfont(r, 10)
            add_inline(p, txt, size=9.5)
            i += 1; continue
        if mn:
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(2)
            add_inline(p, mn.group(3), size=9.5)
            i += 1; continue

        # plain paragraph
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(4)
        add_inline(p, stripped, size=10)
        i += 1

    doc.save(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    md, out = sys.argv[1], sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else None
    convert(md, out, title)
