"""
Multi-format LinkedIn profile parser.
Accepts JSON, XML, DOCX, PDF, or plain text and normalizes
into the same dict structure as linkedin_parser.parse_linkedin_json().
"""

import json
import os
import re
import xml.etree.ElementTree as ET

# Text/DOCX/PDF parsers delegated to linkedin_profile_text_parsers.py (500-line split).
from linkedin_profile_text_parsers import (
    _empty_profile,
    _extract_profile_from_text,
    _extract_profile_via_llm,
    _parse_docx,
    _parse_education_section,
    _parse_experience_section,
    _parse_pdf,
    _parse_recommendations_section,
    _parse_skills_section,
    _parse_text,
    _split_into_sections,
)


def parse_linkedin_upload(file_path):
    """Parse an uploaded LinkedIn profile file into normalized profile dict.

    Supports: .json, .xml, .docx, .pdf, .txt
    Returns: dict compatible with linkedin_parser.parse_linkedin_json() output.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".json":
        return _parse_json(file_path)
    elif ext == ".xml":
        return _parse_xml(file_path)
    elif ext in (".docx", ".doc"):
        return _parse_docx(file_path)
    elif ext == ".pdf":
        return _parse_pdf(file_path)
    elif ext == ".txt":
        return _parse_text(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Accepted: .json, .xml, .docx, .pdf, .txt")


def _parse_json(file_path):
    """Parse JSON — delegates to existing linkedin_parser."""
    from linkedin_parser import parse_linkedin_json

    return parse_linkedin_json(file_path)


def _parse_xml(file_path):
    """Parse XML LinkedIn export into normalized profile dict.

    Handles both LinkedIn data export XML and generic XML with profile fields.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Build a flat dict from XML elements for flexible parsing
    flat = _xml_to_flat_dict(root)

    profile = {
        "name": flat.get("full_name", flat.get("name", flat.get("fullName", ""))),
        "headline": flat.get("headline", flat.get("title", "")),
        "summary": flat.get("summary", flat.get("about", flat.get("description", ""))),
        "contact": {"email": flat.get("email", flat.get("emailAddress", ""))},
        "experience": [],
        "education": [],
        "skills": [],
        "recommendations": [],
    }

    # Extract experience from XML
    for elem in _find_elements(root, ["position", "experience", "job", "work"]):
        profile["experience"].append(
            {
                "title": _get_child_text(elem, ["title", "role", "jobTitle"]),
                "company": _get_child_text(
                    elem, ["company", "companyName", "organization", "employer"]
                ),
                "location": _get_child_text(elem, ["location", "locationName"]),
                "start_date": _get_child_text(elem, ["startDate", "started_on", "start"]),
                "end_date": _get_child_text(elem, ["endDate", "finished_on", "end"]),
                "description": _get_child_text(elem, ["description", "summary", "details"]),
                "accomplishments": [],
            }
        )

    # Extract education
    for elem in _find_elements(root, ["education", "school"]):
        profile["education"].append(
            {
                "school": _get_child_text(elem, ["schoolName", "school", "institution", "name"]),
                "degree": _get_child_text(elem, ["degree", "degreeName"]),
                "field": _get_child_text(elem, ["fieldOfStudy", "field", "major"]),
                "start_date": _get_child_text(elem, ["startDate", "started_on", "start"]),
                "end_date": _get_child_text(elem, ["endDate", "finished_on", "end"]),
            }
        )

    # Extract skills
    for elem in _find_elements(root, ["skill"]):
        name = _get_child_text(elem, ["name", "skillName"]) or (elem.text or "").strip()
        endorsements = _get_child_text(
            elem, ["endorsements", "endorsementCount", "endorsements_count"]
        )
        if name:
            profile["skills"].append(
                {
                    "name": name,
                    "endorsements": (
                        int(endorsements) if endorsements and endorsements.isdigit() else 0
                    ),
                }
            )

    # Extract recommendations
    for elem in _find_elements(root, ["recommendation"]):
        profile["recommendations"].append(
            {
                "author": _get_child_text(elem, ["author", "recommenderName", "name"]),
                "author_title": _get_child_text(elem, ["authorTitle", "recommenderTitle", "title"]),
                "text": _get_child_text(elem, ["text", "body", "content"]),
            }
        )

    return profile


# --- XML helpers ---


def _xml_to_flat_dict(element, prefix=""):
    """Flatten XML tree into a simple key-value dict."""
    result = {}
    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
    key = f"{prefix}.{tag}" if prefix else tag

    text = (element.text or "").strip()
    if text:
        result[tag] = text
        if prefix:
            result[key] = text

    for child in element:
        result.update(_xml_to_flat_dict(child, key))

    return result


def _find_elements(root, tag_names):
    """Find all elements matching any of the given tag names (case-insensitive)."""
    results = []
    tag_lower = {t.lower() for t in tag_names}

    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag.lower() in tag_lower:
            results.append(elem)

    return results


def _get_child_text(element, child_names):
    """Get text from first matching child element."""
    for child in element:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag.lower() in [n.lower() for n in child_names]:
            return (child.text or "").strip()
    return ""
