import re as _re
import string
from collections import Counter

import nltk
import spacy
from nltk.corpus import stopwords
from nltk.tag import pos_tag
from nltk.tokenize import word_tokenize

from nlp_vocab import TECH_SKILLS_VOCAB, _AMBIGUOUS_SINGLE_WORDS, _EMPLOYER_KEYWORD_BLOCKLIST

# Download required NLTK data (run once)
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")

try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords")

nlp = None
try:
    nlp = spacy.load("en_core_web_md")
except OSError:
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        print("Please install a spaCy English model: python -m spacy download en_core_web_md")

# Sentence-transformer model for semantic similarity (Phase 16)
_st_model = None


def _get_st_model():
    """Lazy-load sentence-transformer model (all-MiniLM-L6-v2)."""
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        except ImportError:
            pass
    return _st_model


def extract_keywords(text, num_keywords=50):
    """
    Extract keywords from text using NLP techniques.
    Includes unigrams, bigrams, trigrams with lemmatization and frequency weighting.
    POS filter: NN* (nouns), JJ* (adjectives), VB* (verbs).
    """
    if not text or not text.strip():
        return []

    if nlp is None:
        # Fallback: simple whitespace tokenization without spaCy
        stop_words = set(stopwords.words("english"))
        tokens = word_tokenize(text.lower())
        return [t for t in tokens if t.isalpha() and len(t) > 2 and t not in stop_words][
            :num_keywords
        ]

    # Process with spaCy for lemmatization
    doc = nlp(text.lower())
    stop_words = set(stopwords.words("english"))

    # --- Unigrams with lemmatization ---
    lemmatized_tokens = []
    for token in doc:
        if (
            token.is_alpha
            and len(token.text) > 2
            and token.text not in stop_words
            and token.lemma_ not in stop_words
        ):
            lemmatized_tokens.append(token.lemma_)

    # POS-tag the original tokens for filtering
    raw_tokens = word_tokenize(text.lower())
    filtered_raw = [w for w in raw_tokens if w not in stop_words and w not in string.punctuation]
    pos_tags = pos_tag(filtered_raw)

    # Build a set of words that pass POS filter (NN*, JJ*, VB*)
    pos_accepted = set()
    for word, tag in pos_tags:
        if tag.startswith("NN") or tag.startswith("JJ") or tag.startswith("VB"):
            pos_accepted.add(word)

    # Filter lemmatized tokens by POS (match original form)
    pos_filtered = []
    for token in doc:
        if (
            token.is_alpha
            and len(token.text) > 2
            and token.text not in stop_words
            and (token.text in pos_accepted or token.lemma_ in pos_accepted)
        ):
            pos_filtered.append(token.lemma_)

    # Frequency-weighted ranking
    freq = Counter(pos_filtered)
    unigrams = [word for word, _ in freq.most_common(num_keywords * 2)]

    # --- Bigrams and trigrams from spaCy noun chunks ---
    phrases = set()
    for chunk in doc.noun_chunks:
        chunk_text = chunk.text.strip()
        words = chunk_text.split()
        if 2 <= len(words) <= 3:
            # Lemmatize the phrase
            lemma_phrase = " ".join(t.lemma_ for t in nlp(chunk_text))
            if lemma_phrase not in stop_words and len(lemma_phrase) > 4:
                phrases.add(lemma_phrase)

    # Also extract adjacent-word bigrams/trigrams via sliding window
    tokens_list = [t.lemma_ for t in doc if t.is_alpha and t.text not in stop_words]
    for i in range(len(tokens_list) - 1):
        bigram = f"{tokens_list[i]} {tokens_list[i + 1]}"
        if bigram not in stop_words:
            phrases.add(bigram)
    for i in range(len(tokens_list) - 2):
        trigram = f"{tokens_list[i]} {tokens_list[i + 1]} {tokens_list[i + 2]}"
        phrases.add(trigram)

    # Combine unigrams + phrases, deduplicate
    all_keywords = []
    seen = set()
    # Phrases first (more specific)
    for phrase in sorted(phrases, key=len, reverse=True):
        normalized = phrase.lower().strip()
        if normalized not in seen and len(normalized) > 3:
            all_keywords.append(normalized)
            seen.add(normalized)

    # Then unigrams
    for word in unigrams:
        if word not in seen:
            all_keywords.append(word)
            seen.add(word)

    # Strip employer/benefits/culture terms — they describe the company, not the role
    all_keywords = [k for k in all_keywords if k not in _EMPLOYER_KEYWORD_BLOCKLIST]
    return all_keywords[:num_keywords]


def extract_skill_phrases(text, use_llm_fallback=False):
    """
    Extract skill phrases from text using spaCy noun chunks + curated tech vocabulary.
    Returns list of matched skill phrases.

    If use_llm_fallback=True and vocab yields < 8 skills, calls FTAL harness
    for LLM-based extraction.
    """
    if not text:
        return []

    text_lower = text.lower()
    if nlp is None:
        # Fallback: vocab-only matching without spaCy
        found = set()
        for skill in TECH_SKILLS_VOCAB:
            if skill in text_lower:
                found.add(skill)
        return sorted(found)

    doc = nlp(text_lower)
    found_skills = set()

    # Check curated vocabulary against text
    for skill in TECH_SKILLS_VOCAB:
        # Skip ambiguous single words — require word boundary match
        if skill in _AMBIGUOUS_SINGLE_WORDS:
            # Only match if surrounded by non-alpha chars (word boundary)
            if _re.search(r"\b" + _re.escape(skill) + r"\b", text_lower):
                # For truly ambiguous terms, only include if context suggests tech usage
                context_window = 40
                idx = text_lower.find(skill)
                if idx >= 0:
                    surrounding = text_lower[
                        max(0, idx - context_window): idx + len(skill) + context_window
                    ]
                    tech_context = any(
                        w in surrounding
                        for w in [
                            "programming", "language", "developer", "engineer",
                            "golang", "goroutine", "rstudio", "cran",
                            "lean manufacturing", "lean six sigma", "lean methodology",
                        ]
                    )
                    if tech_context:
                        found_skills.add(skill)
            continue

        if skill in text_lower:
            found_skills.add(skill)

    # Also extract from noun chunks
    for chunk in doc.noun_chunks:
        chunk_text = chunk.text.strip()
        chunk_lower = chunk_text.lower()
        if chunk_lower in TECH_SKILLS_VOCAB:
            found_skills.add(chunk_lower)
        for skill in TECH_SKILLS_VOCAB:
            if len(skill.split()) > 1 and skill in chunk_lower:
                found_skills.add(skill)

    # LLM fallback when vocab yields too few results
    if use_llm_fallback and len(found_skills) < 8:
        llm_skills = _extract_skills_via_llm(text)
        found_skills.update(llm_skills)

    return sorted(found_skills)


def _extract_skills_via_llm(text):
    """
    Use FTAL harness to extract skill phrases from text via LLM.
    Returns set of skill strings. Falls back to empty set if harness unavailable.
    """
    import json

    import httpx

    prompt = (
        "Extract professional skills, technologies, and competencies from the following text. "
        "Return ONLY a JSON array of skill phrases (2-4 words each, lowercase). "
        "Focus on: technologies, methodologies, tools, frameworks, certifications, "
        "and domain expertise. Do NOT include generic words like 'experience' or 'team'. "
        "Return at most 20 items.\n\nText:\n" + text[:3000]
    )

    try:
        resp = httpx.post(
            os.environ.get("HARNESS_URL", "http://localhost:8000/api/harness/run"),
            json={"task": prompt, "task_type": "analysis", "max_tokens": 512},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            output = data.get("output", "") or data.get("result", "")
            try:
                match = _re.search(r"\[.*\]", output, _re.DOTALL)
                if match:
                    skills = json.loads(match.group(0))
                    return {
                        s.lower().strip()
                        for s in skills
                        if isinstance(s, str) and 2 < len(s.strip()) < 60
                    }
            except (json.JSONDecodeError, TypeError):
                pass
    except (httpx.RequestError, httpx.HTTPError, Exception):
        pass

    return set()


def extract_entities(text):
    """Extract named entities from text."""
    if nlp is None:
        return []
    doc = nlp(text)
    return [(ent.text, ent.label_) for ent in doc.ents]


# ---------------------------------------------------------------------------
# Re-exports from nlp_similarity for backward compatibility.
# Callers that do `from nlp_engine import calculate_similarity` continue to
# work unchanged. score_semantic_alignment and _call_llm_for_semantic are
# also re-exported so test patches targeting nlp_engine.* resolve correctly.
# ---------------------------------------------------------------------------
from nlp_similarity import (  # noqa: E402, F401
    _call_llm_for_semantic,
    _chunk_text,
    analyze_resume_vs_job,
    calculate_similarity,
    score_semantic_alignment,
)
