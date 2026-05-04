"""CT-5: Cross-model resume verifier.

Verifies resume outputs using a different model than the one that generated them.
Primary: LLM-based scoring via gateway /api/harness/run (task_type="review",
         routes to deepseek-r1-32b — best review model, score 0.95).
Fallback: heuristic scoring (Jaccard similarity, keyword overlap, quantification count).
"""

import logging
import re
from typing import Dict, List, Optional, Union

import httpx

logger = logging.getLogger(__name__)

_GATEWAY_URL = "http://localhost:8000/api/harness/run"
_DIMS = ["relevance", "substance", "differentiation", "ats_compliance"]


class CrossModelVerifier:
    """Verifies resume outputs using a different model than the generator."""

    def __init__(self, generator_model: str = "rtx5090", verifier_model: str = "deepseek-r1-32b"):
        if generator_model == verifier_model:
            raise ValueError("Generator and verifier models must be different")
        self.generator_model = generator_model
        self.verifier_model = verifier_model

    def verify(
        self, original: str, tailored: str, job_description: str
    ) -> Dict[str, Union[float, bool, List[str]]]:
        """Score a tailored resume on 4 rubric dimensions.

        Tries LLM scoring first (gateway review task); falls back to heuristics.
        Returns: relevance, substance, differentiation, ats_compliance,
                 average, passed (True if average >= 6.0), issues.
        """
        llm_result = self._verify_with_llm(original, tailored, job_description)
        if llm_result is not None:
            return llm_result
        logger.debug("[CrossModelVerifier] LLM call failed — using heuristic fallback")
        return self._verify_heuristic(original, tailored, job_description)

    def _verify_with_llm(
        self, original: str, tailored: str, job_description: str
    ) -> Optional[Dict[str, Union[float, bool, List[str]]]]:
        """POST to gateway /api/harness/run for LLM-based 4-dimension scoring.

        The gateway routes task_type="review" → deepseek-r1-32b (score 0.95).
        Returns parsed result dict, or None on any error.
        """
        task = (
            "You are evaluating a tailored resume. Score it on each dimension 0-10 (10=best):\n"
            "- relevance: how well keywords and role match the job description\n"
            "- substance: presence of quantified achievements and concrete metrics\n"
            "- differentiation: meaningful improvements over the original resume\n"
            "- ats_compliance: ATS-optimized keywords and formatting\n\n"
            f"Job description:\n{job_description[:800]}\n\n"
            f"Original resume (excerpt):\n{original[:400]}\n\n"
            f"Tailored resume:\n{tailored[:800]}\n\n"
            "Output exactly one line: "
            "relevance:<N> substance:<N> differentiation:<N> ats_compliance:<N>"
        )
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=120.0)) as client:
                resp = client.post(
                    _GATEWAY_URL,
                    json={
                        "task_type": "review",
                        "task": task,
                        "max_tokens": 64,
                        "skip_rag": True,
                    },
                )
            if resp.status_code == 200:
                content = resp.json().get("result") or ""
                return self._parse_llm_scores(content)
        except Exception as exc:
            logger.debug("[CrossModelVerifier] LLM call error: %s", exc)
        return None

    def _parse_llm_scores(
        self, content: str
    ) -> Optional[Dict[str, Union[float, bool, List[str]]]]:
        """Parse 'relevance:N substance:N differentiation:N ats_compliance:N' from LLM output."""
        scores: Dict[str, float] = {}
        for dim in _DIMS:
            m = re.search(rf"{dim}[:\s]+(\d+(?:\.\d+)?)", content, re.IGNORECASE)
            if m:
                scores[dim] = min(10.0, max(0.0, float(m.group(1))))
        if len(scores) < len(_DIMS):
            return None
        average = sum(scores.values()) / len(_DIMS)
        passed = average >= 6.0
        issues = [k for k, v in scores.items() if v < 6.0]
        result: Dict[str, Union[float, bool, List[str]]] = {
            **{k: v for k, v in scores.items()},
            "average": average,
            "passed": passed,
            "issues": issues,
        }
        return result

    def _verify_heuristic(
        self, original: str, tailored: str, job_description: str
    ) -> Dict[str, Union[float, bool, List[str]]]:
        """Heuristic scoring — Jaccard, keyword overlap, quantification count."""
        jd_words = set(re.findall(r"\b\w+\b", job_description.lower()))
        tailored_words = set(re.findall(r"\b\w+\b", tailored.lower()))
        original_words = set(re.findall(r"\b\w+\b", original.lower()))

        relevant = len(jd_words & tailored_words)
        relevance = min(10.0, (relevant / max(len(jd_words), 1)) * 10)

        numbers = len(re.findall(r"\d+(?:\.\d+)?%?", tailored))
        substance = max(1.0, min(10.0, float(numbers) * 2))

        union = len(original_words | tailored_words)
        jaccard = len(original_words & tailored_words) / max(union, 1)
        differentiation = max(1.0, 10.0 - (jaccard * 10))

        ats_compliance = min(10.0, (relevant / max(len(jd_words), 1)) * 10)

        average = (relevance + substance + differentiation + ats_compliance) / 4
        passed = average >= 6.0
        issues = [
            dim
            for dim, score in [
                ("relevance", relevance),
                ("substance", substance),
                ("differentiation", differentiation),
                ("ats_compliance", ats_compliance),
            ]
            if score < 6.0
        ]
        return {
            "relevance": relevance,
            "substance": substance,
            "differentiation": differentiation,
            "ats_compliance": ats_compliance,
            "average": average,
            "passed": passed,
            "issues": issues,
        }

    def get_config(self) -> Dict[str, str]:
        """Return generator/verifier model configuration."""
        return {
            "generator_model": self.generator_model,
            "verifier_model": self.verifier_model,
        }


def verify_resume(
    original: str,
    tailored: str,
    job_description: str,
    generator_model: str = "rtx5090",
    verifier_model: str = "deepseek-r1-32b",
) -> Dict[str, Union[float, bool, List[str]]]:
    """Convenience function: create verifier and run .verify()."""
    return CrossModelVerifier(generator_model, verifier_model).verify(
        original, tailored, job_description
    )
