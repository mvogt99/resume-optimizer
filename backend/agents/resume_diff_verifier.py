"""CT-3: Resume output diff verifier.

Catches cosmetic-only tailoring where a resume barely changes relative to
the original. Uses token-level Jaccard similarity, keyword injection count,
quantification detection, and section structure preservation.
"""

import re
from dataclasses import dataclass, field
from typing import List, Set

# Section headers to detect in resume text
_SECTION_PATTERNS = [
    r"EXPERIENCE",
    r"EDUCATION",
    r"SKILLS",
    r"SUMMARY",
    r"OBJECTIVE",
    r"PROJECTS",
    r"CERTIFICATIONS",
    r"AWARDS",
    r"PUBLICATIONS",
    r"REFERENCES",
    r"WORK EXPERIENCE",
    r"PROFESSIONAL EXPERIENCE",
    r"TECHNICAL SKILLS",
]

# Regex matching numbers, percentages, and dollar amounts (quantifications)
_QUANTIFICATION_RE = re.compile(
    r"""
    \$[\d,]+          # dollar amounts ($50,000)
    |\d+\.?\d*\s*%    # percentages (40%, 3.5%)
    |\d+\+?\s*(?:hours?|days?|weeks?|months?|years?|people|users|clients|members|engineers)
    |\b\d{2,}\b       # standalone numbers ≥10 (avoids single digits like "a 5-step")
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class DiffVerificationResult:
    """Result of diff verification between original and tailored resume.

    Attributes:
        meaningful_change: True if the tailoring passes all quality gates.
        jaccard_sim: Token-level Jaccard similarity (0.0–1.0). High = identical.
        new_keywords: Count of JD keywords present in tailored but not original.
        new_quantifications: Count of new quantified lines (numbers/percentages).
        sections_preserved: True if all original sections exist in tailored.
        issues: Human-readable list of flagged problems.
    """

    meaningful_change: bool
    jaccard_sim: float
    new_keywords: int
    new_quantifications: int
    sections_preserved: bool
    issues: List[str] = field(default_factory=list)


class ResumeDiffVerifier:
    """Deterministic diff verifier for resume tailoring quality.

    Applies four checks:
    1. Jaccard similarity — >threshold → cosmetic
    2. Keyword injection — <3 new JD keywords → flag
    3. Quantification — no new numbers/percentages → flag
    4. Section preservation — missing original section → flag

    Args:
        jaccard_threshold: Similarity above which resume is considered cosmetic (default 0.85).
        min_new_keywords: Minimum new JD keywords required (default 3).
    """

    def __init__(self, jaccard_threshold: float = 0.85, min_new_keywords: int = 3):
        self.jaccard_threshold = jaccard_threshold
        self.min_new_keywords = min_new_keywords

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify(
        self,
        original: str,
        tailored: str,
        jd_keywords: List[str],
    ) -> DiffVerificationResult:
        """Run all four diff checks and return a consolidated result.

        Args:
            original: Original resume text.
            tailored: Tailored/optimized resume text.
            jd_keywords: Keywords extracted from the job description.

        Returns:
            DiffVerificationResult with all fields populated.
        """
        issues: List[str] = []

        # 1. Jaccard similarity
        jaccard = self._jaccard_similarity(original, tailored)
        if jaccard >= self.jaccard_threshold:
            issues.append(
                f"cosmetic change only: Jaccard similarity {jaccard:.2f} ≥ {self.jaccard_threshold}"
            )

        # 2. Keyword injection
        new_kw = self._count_new_keywords(original, tailored, jd_keywords)
        if new_kw < self.min_new_keywords:
            issues.append(
                f"keyword injection insufficient: {new_kw} new keywords < {self.min_new_keywords} required"
            )

        # 3. Quantification
        new_quant = self._count_new_quantifications(original, tailored)
        if new_quant == 0:
            issues.append("no new quantifications added (numbers, percentages, metrics)")

        # 4. Section preservation
        sections_ok = self._sections_preserved(original, tailored)
        if not sections_ok:
            missing = self._missing_sections(original, tailored)
            issues.append(f"missing sections in tailored resume: {', '.join(missing)}")

        meaningful = len(issues) == 0

        return DiffVerificationResult(
            meaningful_change=meaningful,
            jaccard_sim=jaccard,
            new_keywords=new_kw,
            new_quantifications=new_quant,
            sections_preserved=sections_ok,
            issues=issues,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """Lowercase word tokens from text."""
        if not text:
            return set()
        return set(re.findall(r"\b[a-z0-9]+\b", text.lower()))

    def _jaccard_similarity(self, a: str, b: str) -> float:
        """Token-level Jaccard similarity between two texts."""
        tokens_a = self._tokenize(a)
        tokens_b = self._tokenize(b)
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)

    @staticmethod
    def _count_new_keywords(original: str, tailored: str, jd_keywords: List[str]) -> int:
        """Count JD keywords present in tailored but absent from original."""
        orig_lower = original.lower()
        tail_lower = tailored.lower()
        count = 0
        for kw in jd_keywords:
            kw_lower = kw.lower()
            if kw_lower not in orig_lower and kw_lower in tail_lower:
                count += 1
        return count

    @staticmethod
    def _count_new_quantifications(original: str, tailored: str) -> int:
        """Count lines in tailored that contain quantifications absent from original."""
        orig_lines = set(original.splitlines())
        new_lines = [ln for ln in tailored.splitlines() if ln not in orig_lines]
        count = 0
        for line in new_lines:
            if _QUANTIFICATION_RE.search(line):
                count += 1
        return count

    def _detect_sections(self, text: str) -> Set[str]:
        """Return set of detected section headers (uppercased) in text.

        Only matches section headers at line start to avoid false positives
        from body text mentioning skills/topics like "projects" in context.
        """
        found: Set[str] = set()
        text_upper = text.upper()
        for pattern in _SECTION_PATTERNS:
            # Require section header at start of line (after optional whitespace)
            if re.search(r"(?:^|\n)\s*" + pattern + r"\b", text_upper):
                found.add(pattern)
        return found

    def _sections_preserved(self, original: str, tailored: str) -> bool:
        """True if every section in original also appears in tailored."""
        orig_sections = self._detect_sections(original)
        if not orig_sections:
            return True  # No detectable sections — nothing to check
        tail_sections = self._detect_sections(tailored)
        return orig_sections.issubset(tail_sections)

    def _missing_sections(self, original: str, tailored: str) -> List[str]:
        """Return section headers present in original but absent from tailored."""
        orig_sections = self._detect_sections(original)
        tail_sections = self._detect_sections(tailored)
        return sorted(orig_sections - tail_sections)
