"""Semantic similarity functions — extracted from nlp_engine.py.

Provides:
  calculate_similarity()      — chunked cosine similarity (fast, local)
  score_semantic_alignment()  — LLM-based qualitative scoring with cosine fallback (Fix C)
  analyze_resume_vs_job()     — keyword overlap analysis
"""

import re

_LLM_SEMANTIC_PROMPT = """You are evaluating how semantically aligned a resume is with a job description.

JOB DESCRIPTION:
{jd}

RESUME:
{resume}

Rate the semantic alignment on a scale of 0-100, where:
- 0-30: Weak — different domain, terminology, or role type
- 31-60: Moderate — same broad field but missing key JD language/context
- 61-75: Good — most themes present but some JD-specific framing missing
- 76-90: Strong — language closely mirrors JD terminology and context
- 91-100: Excellent — resume reads like it was written for this specific JD

Respond with ONLY a JSON object: {{"score": <number>, "gap": "<one sentence describing the main semantic gap>"}}
"""


def _chunk_text(text, max_words=180):
    """Split text into chunks of approximately max_words words."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i: i + max_words])
        if chunk.strip():
            chunks.append(chunk)
    return chunks if chunks else [text]


def _chunked_cosine_similarity(text1: str, text2: str) -> float:
    """Cosine similarity using chunked sentence-transformer embeddings (0.0–1.0)."""
    try:
        from nlp_engine import _get_st_model
        model = _get_st_model()
    except Exception:
        model = None

    if model is not None:
        from numpy import dot, mean, stack
        from numpy.linalg import norm
        chunks1 = _chunk_text(text1)
        chunks2 = _chunk_text(text2)
        emb1 = model.encode(chunks1)
        emb2 = model.encode(chunks2)
        a = mean(stack(emb1), axis=0) if len(emb1) > 1 else emb1[0]
        b = mean(stack(emb2), axis=0) if len(emb2) > 1 else emb2[0]
        return float(max(0.0, dot(a, b) / (norm(a) * norm(b) + 1e-10)))

    try:
        from nlp_engine import nlp
        if nlp is not None:
            return nlp(text1).similarity(nlp(text2))
    except Exception:
        pass

    s1 = set(text1.lower().split())
    s2 = set(text2.lower().split())
    return len(s1 & s2) / len(s1 | s2) if s1 and s2 else 0.0


def calculate_similarity(text1: str, text2: str) -> float:
    """Semantic similarity (0.0–1.0) using chunked sentence-transformer embeddings."""
    if not text1 or not text2:
        return 0.0
    return _chunked_cosine_similarity(text1, text2)


def _call_llm_for_semantic(resume_text: str, jd_text: str) -> float | None:
    """Ask RTX 5090 to rate resume-JD semantic alignment. Returns 0-100 or None on failure."""
    import json
    try:
        from llm_helper import call_llm_quality
        prompt = _LLM_SEMANTIC_PROMPT.format(
            jd=jd_text[:2000],
            resume=resume_text[:3000],
        )
        raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=128)
        if not raw:
            return None
        # Extract JSON from response (LLM may wrap in markdown)
        json_match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            score = float(data.get("score", -1))
            if 0 <= score <= 100:
                return score
    except Exception:
        pass
    return None


def score_semantic_alignment(resume_text: str, jd_text: str) -> float:
    """LLM-based semantic alignment score (0–100) with chunked cosine fallback.

    Uses RTX 5090 for qualitative evaluation when available.
    Falls back to chunked cosine similarity * 100 if LLM unavailable.
    """
    if not resume_text or not jd_text:
        return 0.0
    llm_score = _call_llm_for_semantic(resume_text, jd_text)
    if llm_score is not None:
        return float(max(0.0, min(100.0, llm_score)))
    # Fallback: cosine similarity scaled to 0-100
    cos = _chunked_cosine_similarity(resume_text, jd_text)
    return float(max(0.0, min(100.0, cos * 100)))


def analyze_resume_vs_job(resume_text: str, job_text: str) -> dict:
    """Keyword overlap analysis between resume and job description."""
    from nlp_engine import extract_keywords
    resume_keywords = extract_keywords(resume_text, 50)
    job_keywords = extract_keywords(job_text, 50)
    resume_set = set(resume_keywords)
    job_set = set(job_keywords)
    overlap = resume_set & job_set
    total = resume_set | job_set
    match_score = (len(overlap) / len(total)) * 100 if total else 0
    return {
        "match_score": round(match_score, 2),
        "resume_keywords": resume_keywords,
        "job_keywords": job_keywords,
        "matching_keywords": sorted(overlap),
        "missing_keywords": sorted(job_set - resume_set),
        "additional_keywords": sorted(resume_set - job_set),
    }
