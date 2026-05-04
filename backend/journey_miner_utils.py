"""Standalone helper functions for journey_miner.py.

These are module-level functions (not methods) shared across all mixin classes.
"""

import re


def _extract_date(text):
    """Extract date from text (YYYYMMDD, YYYY-MM-DD, YYYY_MM_DD patterns).

    Validates year (2000-2099), month (1-12), day (1-31) to reject
    non-date digit sequences like phone numbers or IDs.
    """
    patterns = [
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{4}_\d{2}_\d{2})",
        r"(\d{8})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1)
            if len(raw) == 8:
                date_str = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
            else:
                date_str = raw.replace("_", "-")
            parts = date_str.split("-")
            if len(parts) != 3:
                continue
            try:
                yyyy, mm, dd = int(parts[0]), int(parts[1]), int(parts[2])
            except ValueError:
                continue
            if not (2000 <= yyyy <= 2099 and 1 <= mm <= 12 and 1 <= dd <= 31):
                continue
            return date_str
    return None


def _classify_event(item):
    """Classify a source item into an event category."""
    classification = item.get("classification", "")
    title = (item.get("title") or "").lower()

    if "complete" in title or "proof" in title or "pass" in title:
        return "milestone"
    if "fix" in title or "bug" in title:
        return "fix"
    if "teaching" in classification or "learning" in classification:
        return "learning"
    if classification == "report":
        return "milestone"
    if classification == "commit":
        if any(w in title for w in ["feat", "add", "implement"]):
            return "achievement"
        if any(w in title for w in ["fix", "bug"]):
            return "fix"
        return "development"
    if classification in ("task_spec", "specification"):
        return "planning"
    return "development"


def _extract_technologies(text):
    """Extract technology names from text using keyword matching."""
    tech_keywords = {
        "python",
        "flask",
        "fastapi",
        "react",
        "javascript",
        "typescript",
        "docker",
        "kubernetes",
        "vllm",
        "pytorch",
        "tensorflow",
        "qdrant",
        "arangodb",
        "surrealdb",
        "sqlite",
        "postgresql",
        "redis",
        "openai",
        "anthropic",
        "llama",
        "qwen",
        "deepseek",
        "mistral",
        "git",
        "github",
        "gitlab",
        "ci/cd",
        "nginx",
        "uvicorn",
        "aws",
        "azure",
        "gcp",
        "tensorrt",
        "cuda",
        "nvidia",
        "spacy",
        "nltk",
        "transformers",
        "langchain",
        "crewai",
        "artemis",
        "activemq",
        "websocket",
        "rest",
        "graphql",
    }

    text_lower = text.lower()
    found = []
    for tech in tech_keywords:
        if tech in text_lower:
            found.append(tech)
    return sorted(found)
