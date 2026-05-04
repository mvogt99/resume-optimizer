"""Parsing helpers for resume interview — extract structured data from free text."""

import re


def extract_name(text):
    """Try to extract a person's name from text."""
    text = re.sub(r"(?i)^(my name is|i'm|i am|call me|it's|its)\s+", "", text.strip())
    words = text.split()
    name_words = []
    for w in words[:4]:
        clean = re.sub(r"[^a-zA-Z\-']", "", w)
        if clean:
            name_words.append(clean.title())
    return " ".join(name_words) if name_words else text.strip()


def extract_email(text):
    m = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", text)
    return m.group(0) if m else ""


def extract_phone(text):
    m = re.search(r"(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", text)
    return m.group(0).strip() if m else ""


def extract_location(text):
    # Matches "City, ST", "City, State", or "City ST" (two-letter state without comma)
    m = re.search(r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)[,\s]+([A-Z]{2})\b", text)
    if m:
        return f"{m.group(1).strip()}, {m.group(2)}"
    # Fallback: any "Word, Word" pattern with comma
    m2 = re.search(r"([A-Z][a-zA-Z\s]+),\s*([A-Z][a-z]+)", text)
    return m2.group(0) if m2 else ""


def extract_dates(text):
    """Return (start_date, end_date) from a date range string."""
    text = text.strip()
    text = re.sub(r"(?i)\b(current|now)\b", "Present", text)

    m = re.search(
        r"([A-Za-z]*\s*\d{4})\s*(?:to|-|–|through|until)\s*([A-Za-z]*\s*\d{4}|[Pp]resent)",
        text,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    m = re.search(r"(\d{4})\s*[-–]\s*(\d{4}|[Pp]resent)", text)
    if m:
        return m.group(1), m.group(2)

    m = re.search(r"(\d{4})", text)
    if m:
        return m.group(1), "Present"

    return text, "Present"


def split_duties(text):
    """Split a blob of text into individual duty bullets.

    Handles: newlines, bullet/dash/asterisk prefixes, numbered lists,
    and 3+ consecutive spaces (users often separate duties with spaces
    instead of line breaks when typing on mobile or in a single line).
    """
    parts = re.split(r"[\n\r]+|(?<!\d)[•\-\*]\s+|\d+[.)]\s+|\s{2,}", text)
    duties = []
    for p in parts:
        p = p.strip().strip("-•*").strip()
        if len(p) > 5:
            duties.append(p)
    if not duties and len(text.strip()) > 5:
        duties = [text.strip()]
    return duties


def extract_honors(text):
    """Look for GPA or honor mentions."""
    text_lower = text.lower()
    if any(
        h in text_lower
        for h in ["cum laude", "summa", "magna", "honors", "honor roll", "dean's list", "phi beta"]
    ):
        m = re.search(
            r"(summa cum laude|magna cum laude|cum laude|honors|honor roll|dean.s list)",
            text,
            re.I,
        )
        return m.group(0) if m else ""
    m = re.search(r"GPA\s*:?\s*([\d.]+)", text, re.I)
    if m:
        return f"GPA {m.group(1)}"
    return ""


def is_affirmative(text):
    """Return True if text looks like a yes."""
    return bool(
        re.search(
            r"\b(yes|yeah|yep|yup|sure|ok|okay|correct|add|more|another|continue|go ahead)\b",
            text.lower(),
        )
    )


def extract_skills(msg, context):
    """Parse skills from free text and bucket into hard/soft/certifications."""
    all_skills = re.split(r"[,;\n•\-]+", msg)
    for skill in all_skills:
        skill = skill.strip()
        if not skill:
            continue
        lower = skill.lower()
        if any(
            w in lower
            for w in [
                "certified",
                "certificate",
                "license",
                "licensed",
                "cpr",
                "cdl",
                "cna",
                "rn",
                "lpn",
            ]
        ):
            if skill not in context["certifications"]:
                context["certifications"].append(skill)
        elif any(
            w in lower
            for w in [
                "communication",
                "leadership",
                "teamwork",
                "organized",
                "patient",
                "creative",
                "detail",
                "problem",
                "bilingual",
                "empathy",
                "collaboration",
            ]
        ):
            if skill not in context["soft_skills"]:
                context["soft_skills"].append(skill)
        else:
            if skill not in context["hard_skills"]:
                context["hard_skills"].append(skill)
    return context
