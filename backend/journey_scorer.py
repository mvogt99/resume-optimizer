"""Phase 3: Significance scoring for journey events.

Provides rule-based significance scoring and classification.
Replaces broken _classify_event() with multi-signal approach.
"""

import logging

_logger = logging.getLogger(__name__)


def score_event(source: dict, event: dict = None) -> int:
    """Calculate significance score (1-5) for a journey event.

    Args:
        source: dict with source_type, title, full_text, classification, etc.
        event: dict with technologies list (optional)

    Returns:
        int: significance score 1-5
    """
    score = 1  # baseline

    # Source type signals (handle None values)
    source_type = (source.get("source_type") or "").lower()
    classification = (source.get("classification") or "").lower()
    title = (source.get("title") or "").lower()

    if source_type == "git_commit":
        if title.startswith("feat"):
            score += 2  # new feature
        elif title.startswith("fix"):
            score += 1  # bug fix
        elif title.startswith("refactor"):
            score += 1  # refactoring
        # docs, test, chore → +0 (stay at baseline)

    elif source_type == "arango":
        score += 1  # curated knowledge

    elif source_type == "governance":
        score += 2  # governance achievement

    elif classification == "report":
        if "CHECKPOINT" in source.get("title", "").upper():
            score += 2  # session checkpoint = phase completion
        else:
            score += 1

    # Content signals
    text = (source.get("full_text") or "").lower()
    completion_keywords = ["complete", "deployed", "production", "shipped", "launched"]
    if any(w in text for w in completion_keywords):
        score += 1

    impact_keywords = ["critical", "breakthrough", "first time", "milestone"]
    if any(w in text for w in impact_keywords):
        score += 1

    # Technology breadth bonus
    if event:
        techs = event.get("technologies") or []
        if len(techs) >= 5:
            score += 1

    score = min(score, 5)
    _logger.debug(
        "score_event: title=%r score=%d",
        (source.get("title") or "")[:80],
        score,
    )
    return score


def classify_event(source: dict) -> str:
    """Classify event type using source metadata.

    Replaces the broken keyword-matching approach.

    Args:
        source: dict with source_type, classification, title

    Returns:
        str: event classification (achievement, fix, learning, governance, etc.)
    """
    source_type = (source.get("source_type") or "").lower()
    classification = (source.get("classification") or "").lower()
    title = (source.get("title") or "").lower()

    # Git commit classification
    if source_type == "git_commit":
        if title.startswith("feat"):
            result = "achievement"
        elif title.startswith("fix"):
            result = "fix"
        elif title.startswith("test"):
            result = "development"
        elif title.startswith("docs"):
            result = "documentation"
        elif title.startswith("refactor"):
            result = "development"
        else:
            result = "development"
    elif source_type == "governance":
        result = "governance"
    elif classification == "teaching":
        result = "learning"
    elif classification == "learning":
        result = "learning"
    elif classification == "report":
        result = "milestone"
    elif classification == "coordinator":
        result = "development"
    elif classification == "task_spec":
        result = "planning"
    else:
        result = "development"

    _logger.debug(
        "classify_event: title=%r → %s",
        (source.get("title") or "")[:80],
        result,
    )
    return result
