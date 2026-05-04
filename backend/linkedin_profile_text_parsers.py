"""
Text-based LinkedIn profile parsers (DOCX, PDF, plain text).

Split from linkedin_profile_upload.py to comply with 500-line file limit.
Provides: _parse_docx, _parse_pdf, _parse_text, _extract_profile_from_text,
_empty_profile, _split_into_sections, _parse_experience_section,
_parse_education_section, _parse_skills_section, _parse_recommendations_section,
_extract_profile_via_llm.
"""

import re


def _parse_docx(file_path):
    """Parse DOCX LinkedIn profile export into profile dict."""
    from docx import Document

    doc = Document(file_path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return _extract_profile_from_text(text)


def _parse_pdf(file_path):
    """Parse PDF LinkedIn profile export into profile dict."""
    from pypdf import PdfReader

    text = ""
    with open(file_path, "rb") as f:
        reader = PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return _extract_profile_from_text(text)


def _parse_text(file_path):
    """Parse plain text LinkedIn profile into profile dict."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return _extract_profile_from_text(text)


def _extract_profile_from_text(text):
    """Extract LinkedIn profile fields from unstructured text.

    Uses regex heuristics to identify common LinkedIn profile sections.
    Falls back to LLM extraction for complex cases.
    """
    text = text.strip()
    if not text:
        return _empty_profile()

    profile = _empty_profile()

    # Try to extract name from first non-empty line
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        # First meaningful line is often the name
        first_line = lines[0]
        if len(first_line) < 80 and not any(
            kw in first_line.lower() for kw in ["experience", "education", "skills", "summary"]
        ):
            profile["name"] = first_line

    # Extract sections by common LinkedIn headings
    sections = _split_into_sections(text)

    if "headline" in sections:
        profile["headline"] = sections["headline"].strip()
    if "summary" in sections or "about" in sections:
        profile["summary"] = (sections.get("summary") or sections.get("about", "")).strip()

    # Experience section
    exp_text = sections.get("experience", "")
    if exp_text:
        profile["experience"] = _parse_experience_section(exp_text)

    # Education section
    edu_text = sections.get("education", "")
    if edu_text:
        profile["education"] = _parse_education_section(edu_text)

    # Skills section — also check competencies/expertise resume headings
    skills_text = sections.get("skills") or sections.get("skills & endorsements") or \
        sections.get("competencies") or sections.get("technical skills") or \
        sections.get("expertise") or ""
    if skills_text:
        profile["skills"] = _parse_skills_section(skills_text)

    # Recommendations
    rec_text = sections.get("recommendations", sections.get("recommendations received", ""))
    if rec_text:
        profile["recommendations"] = _parse_recommendations_section(rec_text)

    # If heuristics didn't find much, try LLM extraction
    total_found = len(profile["experience"]) + len(profile["education"]) + len(profile["skills"])
    if total_found == 0 and len(text) > 100:
        llm_profile = _extract_profile_via_llm(text)
        if llm_profile:
            # Merge LLM results into profile, preferring non-empty values
            for key in ("name", "headline", "summary"):
                if llm_profile.get(key) and not profile.get(key):
                    profile[key] = llm_profile[key]
            for key in ("experience", "education", "skills", "recommendations"):
                if llm_profile.get(key) and not profile.get(key):
                    profile[key] = llm_profile[key]

    return profile


def _empty_profile():
    """Return empty profile dict."""
    return {
        "name": "",
        "headline": "",
        "summary": "",
        "contact": {"email": ""},
        "experience": [],
        "education": [],
        "skills": [],
        "recommendations": [],
    }


def _split_into_sections(text):
    """Split text into sections by common LinkedIn headings."""
    heading_pattern = re.compile(
        r"^(?:#+\s*)?(?:professional\s+|key\s+|core\s+|work\s+|additional\s+)?"
        r"("
        r"summary|about|headline|profile|objective|"
        r"experience|work experience|employment|history|"
        r"education|academic|"
        r"skills|competencies|expertise|technical skills|"
        r"skills & endorsements|skills and endorsements|"
        r"recommendations|recommendations received|certifications|"
        r"projects|publications|volunteer|languages|interests|honors|"
        r"accomplishments|achievements"
        r")\s*:?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    sections = {}
    matches = list(heading_pattern.finditer(text))

    for i, match in enumerate(matches):
        section_name = match.group(1).lower().strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[section_name] = text[start:end].strip()

    return sections


def _parse_experience_section(text):
    """Parse experience entries from text section."""
    entries = []
    date_pattern = re.compile(
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{4}|"
        r"\d{4})\s*[-–—to]+\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{4}|"
        r"\d{4}|[Pp]resent|[Cc]urrent)",
        re.IGNORECASE,
    )
    # Detect resume-style "Company - Location - Date Range" header lines
    company_header = re.compile(
        r"^(.+?)\s*[-–—]\s*(.+?)\s*[-–—]\s*(\d{4}\s*(?:to|[-–—])\s*(?:\d{4}|[Pp]resent|[Cc]urrent))\s*$",
        re.IGNORECASE,
    )
    # Prefer splitting on company-header lines when they appear in the text
    company_header_split = re.compile(
        r"(?m)(?=^.+\s*[-–—]\s*.+\s*[-–—]\s*\d{4})",
    )
    if len(company_header_split.findall(text)) >= 1:
        blocks = company_header_split.split(text)
    else:
        # Fall back to "Title at/@ Company" inline pattern
        blocks = re.split(r"\n(?=\S.*(?:at |@ |\| |—|–))", text)

    for block in blocks:
        block = block.strip()
        if not block or len(block) < 10:
            continue

        entry = {
            "title": "",
            "company": "",
            "location": "",
            "start_date": "",
            "end_date": "",
            "description": "",
            "accomplishments": [],
        }

        lines = block.split("\n")
        first_line = lines[0].strip()

        # Check for resume-style "Company - Location - Date Range" first line
        hdr = company_header.match(first_line)
        if hdr:
            entry["company"] = hdr.group(1).strip()
            entry["location"] = hdr.group(2).strip()
            date_str = hdr.group(3)
            dm = re.split(r'\s*(?:to|[-–—])\s*', date_str, maxsplit=1)
            entry["start_date"] = dm[0].strip()
            entry["end_date"] = dm[1].strip() if len(dm) > 1 else ""
            # Title is on the next non-empty line
            remaining_lines = [l.strip() for l in lines[1:] if l.strip()]
            if remaining_lines:
                entry["title"] = remaining_lines[0]
                desc_lines = remaining_lines[1:]
            else:
                desc_lines = []
            entry["description"] = "\n".join(desc_lines)
            if entry["company"] or entry["title"]:
                entries.append(entry)
            continue

        # Try "Title at Company" or "Title | Company" pattern
        for sep in [" at ", " @ ", " | ", " — ", " – "]:
            if sep in first_line:
                parts = first_line.split(sep, 1)
                entry["title"] = parts[0].strip()
                entry["company"] = parts[1].strip()
                break
        else:
            entry["title"] = first_line

        # Look for dates in remaining lines
        date_pattern = re.compile(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{4}|"
            r"\d{4})\s*[-–—to]+\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{4}|"
            r"\d{4}|[Pp]resent|[Cc]urrent)",
            re.IGNORECASE,
        )
        desc_lines = []
        for line in lines[1:]:
            line = line.strip()
            date_match = date_pattern.search(line)
            if date_match and not entry["start_date"]:
                entry["start_date"] = date_match.group(1)
                entry["end_date"] = date_match.group(2)
            elif line:
                desc_lines.append(line)

        entry["description"] = "\n".join(desc_lines)
        if entry["title"] or entry["company"]:
            entries.append(entry)

    return entries


def _parse_education_section(text):
    """Parse education entries from text."""
    entries = []
    blocks = re.split(r"\n(?=\S)", text)

    for block in blocks:
        block = block.strip()
        if not block or len(block) < 5:
            continue

        entry = {
            "school": "",
            "degree": "",
            "field": "",
            "start_date": "",
            "end_date": "",
        }

        lines = block.split("\n")
        entry["school"] = lines[0].strip()

        for line in lines[1:]:
            line = line.strip()
            # Look for degree patterns
            degree_match = re.search(
                r"(Bachelor|Master|MBA|Ph\.?D|Associate|Doctor|B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|"
                r"B\.?Eng|M\.?Eng|JD|LLB|LLM)",
                line,
                re.IGNORECASE,
            )
            if degree_match and not entry["degree"]:
                entry["degree"] = line
            # Look for dates
            date_match = re.search(r"(\d{4})\s*[-–—to]+\s*(\d{4}|[Pp]resent)", line)
            if date_match:
                entry["start_date"] = date_match.group(1)
                entry["end_date"] = date_match.group(2)

        if entry["school"]:
            entries.append(entry)

    return entries


def _parse_skills_section(text):
    """Parse skills from text, looking for skill names and optional endorsement counts."""
    skills = []
    lines = text.strip().split("\n")

    for line in lines:
        line = line.strip().lstrip("- *+")
        if not line or len(line) < 2:
            continue

        # Check for "Skill Name (N endorsements)" or "Skill Name · N"
        endorse_match = re.search(
            r"(.+?)\s*[\(·:]\s*(\d+)\s*(?:endorsement|endorse)?", line, re.IGNORECASE
        )
        if endorse_match:
            skills.append(
                {
                    "name": endorse_match.group(1).strip().rstrip(","),
                    "endorsements": int(endorse_match.group(2)),
                }
            )
        else:
            # Could be comma-separated skills
            for skill in re.split(r"[,;|]", line):
                skill = skill.strip()
                if skill and len(skill) > 1 and len(skill) < 80:
                    skills.append({"name": skill, "endorsements": 0})

    return skills


def _parse_recommendations_section(text):
    """Parse recommendations from text."""
    recs = []
    # Split on patterns like "— Author Name" or "- Author Name, Title"
    blocks = re.split(r"\n{2,}", text)

    for block in blocks:
        block = block.strip()
        if not block or len(block) < 20:
            continue

        rec = {"author": "", "author_title": "", "text": block}

        # Look for attribution at end: "— Name, Title" or "- Name"
        attr_match = re.search(r"\n\s*[-—–]\s*(.+?)(?:,\s*(.+))?\s*$", block)
        if attr_match:
            rec["author"] = attr_match.group(1).strip()
            rec["author_title"] = (attr_match.group(2) or "").strip()
            rec["text"] = block[: attr_match.start()].strip()

        if rec["text"]:
            recs.append(rec)

    return recs


def _extract_profile_via_llm(text):
    """Use LLM to extract structured profile from unstructured text."""
    try:
        from llm_helper import extract_json
        from smart_llm import call_direct

        prompt = (
            "Extract a LinkedIn profile from this text. Return ONLY a JSON object with these fields:\n"
            '{"name": "", "headline": "", "summary": "", '
            '"experience": [{"title": "", "company": "", "location": "", '
            '"start_date": "", "end_date": "", "description": ""}], '
            '"education": [{"school": "", "degree": "", "field": "", '
            '"start_date": "", "end_date": ""}], '
            '"skills": [{"name": "", "endorsements": 0}], '
            '"recommendations": [{"author": "", "author_title": "", "text": ""}]}\n\n'
            f"Text:\n{text[:6000]}"
        )
        raw = call_direct(prompt, max_tokens=2048, temperature=0.1)
        if raw:
            parsed = extract_json(raw)
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass
    return None
