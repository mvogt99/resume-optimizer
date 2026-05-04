"""Expert AI comparison — compares our optimized resume against an external AI version.

Provides:
  compare_with_expert()       — NLP scoring + LLM analysis of two resume versions
  run_interview_turn()        — single turn of open-ended guided interview
  generate_merged_resume()    — synthesize personalized resume from both versions +
                                interview history + LinkedIn profile + knowledge graph
"""

import json
import logging

from nlp_engine import extract_skill_phrases
from resume_scorer import score_resume

logger = logging.getLogger(__name__)


def _extract_json(text: str, fallback: dict) -> dict:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    if not text:
        return fallback
    cleaned = text.strip()
    for fence in ("```json", "```"):
        if fence in cleaned:
            start = cleaned.find(fence) + len(fence)
            end = cleaned.find("```", start)
            if end > start:
                cleaned = cleaned[start:end].strip()
                break
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        logger.warning("LLM returned non-JSON; using fallback. Preview: %s", text[:200])
        return fallback


def compare_with_expert(our_text: str, expert_text: str, job_text: str) -> dict:
    """Score and compare our optimized resume against an expert AI version."""
    job_keywords = extract_skill_phrases(job_text) or job_text.split()[:20]

    our_result = score_resume(
        {"text": our_text, "skills": [], "experience": [], "education": []},
        job_keywords, job_text,
    )
    expert_result = score_resume(
        {"text": expert_text, "skills": [], "experience": [], "education": []},
        job_keywords, job_text,
    )

    our_ats = our_result["score"]
    expert_ats = expert_result["score"]

    fallback = {
        "agreements": ["Both versions target the job description keywords."],
        "disagreements": [],
        "expert_unique_additions": [],
        "our_unique_additions": [],
        "recommendation": (
            "Review both versions carefully. Choose the phrasing that most accurately "
            "represents your experience while aligning with the job description."
        ),
        "interview_questions": [
            "Which accomplishments does the expert version highlight that feel most accurate to you?",
            "Are there any claims in the expert version that overstate or misrepresent your experience?",
            "Does the expert version use industry terminology you'd be comfortable defending in an interview?",
        ],
    }

    try:
        from llm_helper import call_llm_quality

        prompt = f"""You are an expert resume consultant comparing two AI-optimized versions of the same resume.

JOB DESCRIPTION:
{job_text[:1500]}

--- OUR AI OPTIMIZED VERSION (ATS score: {our_ats}/100) ---
{our_text[:2500]}

--- EXPERT AI VERSION / LinkedIn AI (ATS score: {expert_ats}/100) ---
{expert_text[:2500]}

Compare these two versions and respond with ONLY valid JSON in this exact format:
{{
  "agreements": [
    "<specific thing both versions handle well>"
  ],
  "disagreements": [
    {{
      "topic": "<aspect where they differ>",
      "ours": "<how our version handles it>",
      "expert": "<how the expert version handles it>",
      "expert_rationale": "<why the expert AI likely made that choice>"
    }}
  ],
  "expert_unique_additions": [
    "<something valuable the expert version adds that ours doesn't>"
  ],
  "our_unique_additions": [
    "<something valuable our version adds that the expert's doesn't>"
  ],
  "recommendation": "<Which version is stronger overall and the key reason why — be specific>",
  "interview_questions": [
    "<first open question to understand the user's actual experience and which approach fits better>"
  ]
}}

Rules:
- 2-4 items per list (except disagreements: 1-5 items)
- interview_questions: provide exactly ONE strong opening question
- Focus on substantive content differences: accomplishment framing, keyword density, section structure, tone
- Be direct and actionable"""

        raw = call_llm_quality(prompt, task_type="analysis", max_tokens=2048)
        analysis = _extract_json(raw, fallback)
    except Exception as exc:
        logger.warning("LLM comparison call failed, using fallback: %s", exc)
        analysis = fallback

    # Detect significant length disparity (rough page estimate: ~2500 chars/page)
    our_len = len(our_text)
    expert_len = len(expert_text)
    length_warning = None
    if expert_len < our_len * 0.5:
        our_pages = max(1, round(our_len / 2500))
        expert_pages = max(1, round(expert_len / 2500))
        length_warning = (
            f"The expert version is significantly shorter (~{expert_pages} page) "
            f"than yours (~{our_pages} pages). A shorter resume will naturally score "
            f"lower on keyword coverage — this does not mean it's weaker. Consider "
            f"the depth and relevance of content, not just raw score."
        )

    return {
        "ats_scores": {"ours": our_ats, "expert": expert_ats},
        "our_matching_keywords": our_result.get("matching_keywords", []),
        "expert_matching_keywords": expert_result.get("matching_keywords", []),
        "length_warning": length_warning,
        **analysis,
    }


def run_interview_turn(
    history: list,
    current_question: str,
    user_answer: str,
    context: dict,
    user_finished: bool = False,
) -> dict:
    """Process one turn of the open-ended comparison interview.

    Args:
        history:          List of {question, answer} dicts from previous turns.
        current_question: The question just answered.
        user_answer:      User's answer to the current question.
        context:          {job_text, disagreements, recommendation, our_text, expert_text}
        user_finished:    True when the user clicks 'Finish' — no next question needed.

    Returns:
        {
          insight: str,          — AI response to this specific answer
          next_question: str,    — follow-up question (None when user_finished=True)
          suggested_done: bool,  — hint after 4+ turns that enough context exists
          is_complete: bool,     — True when user_finished=True
        }
    """
    disagreements = context.get("disagreements", [])
    recommendation = context.get("recommendation", "")
    job_text = context.get("job_text", "")[:800]
    turn_count = len(history) + 1  # including current

    prior = "\n".join(
        f"Q: {h['question']}\nA: {h['answer']}" for h in history
    )

    fallback_insight = (
        "That's helpful context. Your lived experience is the most important factor — "
        "choose the version that most accurately represents what you actually did and can "
        "confidently discuss in an interview."
    )
    fallback_next_q = (
        "Looking at the key differences between the two versions — which specific changes "
        "in the expert version feel most true to your actual contributions?"
    )

    try:
        from llm_helper import call_llm_quality

        # ── Insight: response to this specific answer ─────────────────────────
        insight_prompt = f"""You are a career coach helping a user choose between two AI-generated resume versions.

Job description context: {job_text}
Initial AI recommendation: {recommendation}

Prior Q&A:
{prior if prior else '(This is the first question)'}

Current question: {current_question}
User answer: {user_answer}

Write 2-3 sentences: acknowledge what the user said, explain what it reveals about \
which resume version fits them better, and give one concrete action item. Be direct. \
Do not repeat the question. Do not use bullet points."""

        raw_insight = call_llm_quality(insight_prompt, task_type="reasoning", max_tokens=350)
        insight = (raw_insight or "").strip() or fallback_insight

        # ── Next question (only when user has not finished) ────────────────────
        next_question = None
        if not user_finished:
            covered_topics = [h["question"] for h in history] + [current_question]
            disagreement_topics = [d.get("topic", "") for d in disagreements[:4]]

            nq_prompt = f"""You are a career coach conducting an open-ended interview to \
help a user decide which resume version best represents their real experience.

Job description context: {job_text}
Key differences to explore: {json.dumps(disagreement_topics)}

Q&A so far (most recent last):
{prior if prior else '(none yet)'}
Q: {current_question}
A: {user_answer}

Topics already covered: {covered_topics}

Ask ONE focused follow-up question that:
1. Digs deeper into what the user just said OR pivots to an important uncovered difference
2. Is specific — reference actual content from the resumes or the user's answer
3. Helps clarify whether the expert version's changes accurately reflect their experience
4. Is conversational, not clinical

Reply with ONLY the question. No preamble, no numbering."""

            raw_nq = call_llm_quality(nq_prompt, task_type="reasoning", max_tokens=150)
            next_question = (raw_nq or "").strip() or fallback_next_q

        suggested_done = (not user_finished) and (turn_count >= 4)

        return {
            "insight": insight,
            "next_question": next_question,
            "suggested_done": suggested_done,
            "is_complete": user_finished,
        }

    except Exception as exc:
        logger.warning("Interview turn LLM call failed: %s", exc)
        return {
            "insight": fallback_insight,
            "next_question": None if user_finished else fallback_next_q,
            "suggested_done": (not user_finished) and (turn_count >= 4),
            "is_complete": user_finished,
        }


def generate_merged_resume(
    our_text: str,
    expert_text: str,
    interview_history: list,
    job_text: str,
    linkedin_summary: str = "",
    knowledge_context: str = "",
) -> dict:
    """Synthesize a personalized resume from both versions guided by interview answers.

    Uses the interview Q&A to decide section-by-section which version's approach
    is most accurate, then writes a merged resume incorporating those decisions.

    Args:
        our_text:          Our AI-optimized resume text.
        expert_text:       LinkedIn AI / expert version.
        interview_history: List of {question, answer} dicts from the interview.
        job_text:          Job description.
        linkedin_summary:  Processed LinkedIn profile summary (optional).
        knowledge_context: ArangoDB / deep profile context (optional).

    Returns:
        {
          merged_text: str,
          decisions: list[{section, choice, reason}],
        }
    """
    qa_text = "\n".join(
        f"Q: {h['question']}\nA: {h['answer']}" for h in interview_history
    ) or "(no interview Q&A available)"

    fallback_merged = our_text
    fallback_decisions = [
        {
            "section": "Overall",
            "choice": "ours",
            "reason": "Defaulting to our AI version — merge generation unavailable.",
        }
    ]

    try:
        from llm_helper import call_llm_quality

        # ── Step 1: Generate section decisions as JSON ────────────────────────
        decisions_prompt = f"""You are a resume editor. Based on a user's interview answers, \
decide which version of each resume section to use.

JOB DESCRIPTION (abbreviated):
{job_text[:800]}

USER'S INTERVIEW ANSWERS (these reveal what is true about their experience):
{qa_text}

OUR AI VERSION (first 1500 chars):
{our_text[:1500]}

EXPERT AI VERSION (first 1500 chars):
{expert_text[:1500]}

For each major section (Summary, Experience entries, Skills, Education, etc.), \
decide: use "ours", "expert", or "hybrid" (best of both). Base decisions on \
what the user's interview answers confirm about their actual experience.

Respond with ONLY valid JSON:
{{
  "decisions": [
    {{"section": "<section name>", "choice": "ours|expert|hybrid", "reason": "<1 sentence — cite interview answer if relevant>"}}
  ]
}}"""

        raw_decisions = call_llm_quality(
            decisions_prompt, task_type="analysis", max_tokens=600
        )
        parsed = _extract_json(raw_decisions, {"decisions": fallback_decisions})
        decisions = parsed.get("decisions", fallback_decisions)

        # ── Step 2: Generate the merged resume text ────────────────────────────
        linkedin_block = f"\nLINKEDIN PROFILE CONTEXT:\n{linkedin_summary[:800]}\n" if linkedin_summary else ""
        knowledge_block = f"\nADDITIONAL CAREER CONTEXT:\n{knowledge_context[:600]}\n" if knowledge_context else ""

        decisions_summary = "\n".join(
            f"- {d['section']}: use {d['choice']} — {d['reason']}"
            for d in decisions
        )

        merge_prompt = f"""You are an expert resume writer. Synthesize a single, polished, \
personalized resume for this candidate using the decisions below.

JOB DESCRIPTION:
{job_text[:1200]}

USER'S INTERVIEW ANSWERS (ground truth about their experience):
{qa_text}
{linkedin_block}{knowledge_block}
SECTION DECISIONS:
{decisions_summary}

OUR AI VERSION:
{our_text[:2000]}

EXPERT AI VERSION:
{expert_text[:2000]}

Write the complete merged resume. Rules:
- Follow the section decisions above — use the designated version for each section
- Where decision is "hybrid": take the structure/keywords from whichever scores higher for the job, \
  but replace any claims the user's interview answers indicated were inaccurate
- Use strong action verbs and quantify achievements where the source material does so
- Align keyword density to the job description
- Do NOT add fabricated details — only use content from the two source versions and \
  what the user confirmed in their interview
- Output the full resume text only — no preamble, no JSON, no commentary"""

        raw_merged = call_llm_quality(
            merge_prompt, task_type="generation", max_tokens=2500
        )
        merged_text = (raw_merged or "").strip() or fallback_merged

        return {"merged_text": merged_text, "decisions": decisions}

    except Exception as exc:
        logger.warning("Merge resume generation failed: %s", exc)
        return {"merged_text": fallback_merged, "decisions": fallback_decisions}
