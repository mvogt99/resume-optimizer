"""
Stage 3: Agentic Resume Compilation — 6-step pipeline.
Strategically selects, weaves, rewrites, scores, and strengthens resume content.
Falls back to ResumeBuilder.build_enriched_resume() on failure.
"""

import json

from agentic_compiler_content import AgenticCompilerContentMixin
from llm_helper import call_llm, call_llm_quality, extract_json
from nlp_engine import calculate_similarity, extract_keywords, extract_skill_phrases  # noqa: F401

HARNESS_URL = "http://localhost:8000/api/harness/run"
HARNESS_TIMEOUT = 120

OUTCOME_TYPE_RANK = {
    "revenue_growth": 11,
    "cost_reduction": 10,
    "efficiency_improvement": 9,
    "scale_achievement": 8,
    "quality_improvement": 7,
    "customer_satisfaction": 6,
    "risk_reduction": 5,
    "team_org_impact": 4,
    "process_automation": 3,
    "capability_enablement": 2,
    "time_savings": 1,
}


class AgenticCompiler(AgenticCompilerContentMixin):
    """6-step agentic resume compilation pipeline."""

    def compile_agentic(self, job_text, base_text, sources, interview_bullets=None):
        """Full pipeline with fallback to mechanical compilation.

        Args:
            job_text: Full job description text.
            base_text: Base resume text.
            sources: Dict with keys: linkedin, projects, journey, experiences.
            interview_bullets: List of bullet dicts from builder interview.

        Returns:
            Dict with text, sources_used, ats_score, compilation_method, weaknesses.
        """
        try:
            return self._run_pipeline(job_text, base_text, sources, interview_bullets)
        except Exception as e:
            print(f"[agentic_compiler] Pipeline failed, falling back: {e}")
            from resume_builder import get_resume_builder

            builder = get_resume_builder()
            result = builder.build_enriched_resume(job_text, base_text, sources)
            result["compilation_method"] = "mechanical_fallback"
            result["ats_score"] = 0
            return result

    def _run_pipeline(self, job_text, base_text, sources, interview_bullets):
        """Execute the 6-step pipeline."""
        sources = sources or {}
        interview_bullets = interview_bullets or []

        # Gather all content into a flat structure
        all_content = self._gather_all_content(base_text, sources, interview_bullets)

        # Step 1: Strategic selection
        job_analysis = self._strategic_selection(job_text, all_content)

        # Step 2: Assemble sections
        sections = self._assemble_sections(all_content, job_analysis, interview_bullets)

        # Step 3: Rewrite bullets
        sections = self._rewrite_bullets(sections, job_text, job_analysis.get("ats_keywords", []))

        # Step 4: Compile initial text
        compiled_text = self._compile_section_text(sections, job_analysis)

        # Step 4b: Score and identify weaknesses
        score_result = self._score_and_identify_weaknesses(compiled_text, job_text)

        # Step 5: Strengthen if score < 80
        ats_score = score_result.get("ats_score", 0)
        if ats_score < 80 and score_result.get("weaknesses"):
            sections = self._strengthen_weak_sections(sections, score_result, job_text, all_content)
            compiled_text = self._compile_section_text(sections, job_analysis)
            # Re-score
            score_result = self._score_and_identify_weaknesses(compiled_text, job_text)
            ats_score = score_result.get("ats_score", ats_score)

        # Build sources_used list
        sources_used = []
        if sources.get("linkedin"):
            sources_used.append("linkedin")
        if sources.get("projects"):
            sources_used.append("projects")
        if sources.get("journey"):
            sources_used.append("journey")
        if sources.get("experiences"):
            sources_used.append("experiences")
        if interview_bullets:
            sources_used.append("interview")

        return {
            "text": compiled_text,
            "sources_used": sources_used,
            "ats_score": ats_score,
            "compilation_method": "agentic",
            "weaknesses": score_result.get("weaknesses", []),
            "missing_keywords": score_result.get("missing_keywords", []),
            "strongest_section": score_result.get("strongest_section", ""),
            "weakest_section": score_result.get("weakest_section", ""),
            "job_analysis": {
                "must_have": job_analysis.get("must_have", []),
                "nice_to_have": job_analysis.get("nice_to_have", []),
                "ats_keywords": job_analysis.get("ats_keywords", []),
            },
        }

    # Steps 1-2 (_gather_all_content, _strategic_selection, _assemble_sections)
    # are in AgenticCompilerContentMixin (agentic_compiler_content.py).

    def _rewrite_bullets(self, sections, job_text, ats_keywords):
        """Step 3: Batch rewrite experience/accomplishment bullets for ATS optimization."""
        for section_key in ("experience", "accomplishments"):
            items = sections[section_key]
            if not items:
                continue

            # Collect bullets to rewrite (batch of 10)
            bullets_to_rewrite = []
            for item in items:
                text = item.get("detail", "") or item.get("text", "")
                if text and len(text) > 20 and item.get("type") != "base":
                    bullets_to_rewrite.append(
                        {
                            "original": text[:500],
                            "source": item.get("source", ""),
                        }
                    )

            if not bullets_to_rewrite:
                continue

            # Process in batches of 10
            for batch_start in range(0, len(bullets_to_rewrite), 10):
                batch = bullets_to_rewrite[batch_start : batch_start + 10]
                originals_json = json.dumps([b["original"] for b in batch])
                kw_str = ", ".join(ats_keywords[:20])

                prompt = (
                    "Rewrite these resume bullet points for maximum ATS impact.\n\n"
                    f"ATS keywords to incorporate naturally: {kw_str}\n"
                    f"Job context (first 300 chars): {job_text[:300]}\n\n"
                    f"Original bullets:\n{originals_json}\n\n"
                    "Rules:\n"
                    "- LEAD WITH METRICS — if a quantified result exists, "
                    "it should appear in the first half of the bullet\n"
                    "- Use measurable-result action verbs when metrics exist: "
                    "Reduced, Increased, Delivered, Achieved, Saved, Accelerated\n"
                    "- Start each bullet with a strong action verb "
                    "(Led, Designed, Implemented, Orchestrated, Reduced, etc.)\n"
                    "- Preserve ALL real metrics and numbers EXACTLY — do NOT "
                    "invent, round, or change any dollar amounts, percentages, "
                    "counts, or time values\n"
                    "- Incorporate ATS keywords naturally where relevant\n"
                    "- Keep each bullet to 1-2 sentences\n"
                    "- Do NOT add facts that weren't in the original\n\n"
                    "Return a JSON array of rewritten strings, same order as input."
                )

                raw = call_llm(prompt, task_type="coding", max_tokens=4096)
                rewritten = extract_json(raw) if raw else None

                if isinstance(rewritten, list) and len(rewritten) == len(batch):
                    for j, new_text in enumerate(rewritten):
                        idx = batch_start + j
                        if idx < len(items) and isinstance(new_text, str) and len(new_text) > 10:
                            if items[idx].get("detail"):
                                items[idx]["detail"] = new_text
                            else:
                                items[idx]["text"] = new_text

        return sections

    def _score_and_identify_weaknesses(self, compiled_text, job_text):
        """Step 4: LLM scores the draft resume against the job description."""
        prompt = (
            "Score this resume against the job description.\n\n"
            f"Resume:\n{compiled_text[:4000]}\n\n"
            f"Job description:\n{job_text[:2000]}\n\n"
            "Return a JSON object with:\n"
            '- "ats_score": 0-100 ATS compatibility score\n'
            '- "weaknesses": list of specific weaknesses (max 5)\n'
            '- "missing_keywords": list of important job keywords not in resume\n'
            '- "strongest_section": which section is best aligned\n'
            '- "weakest_section": which section needs most improvement\n'
        )

        raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=1024)
        result = extract_json(raw) if raw else None
        if not isinstance(result, dict):
            # Fallback: compute basic score via NLP
            score = round(calculate_similarity(compiled_text, job_text) * 100, 1)
            result = {
                "ats_score": score,
                "weaknesses": [],
                "missing_keywords": [],
                "strongest_section": "",
                "weakest_section": "",
            }
        return result

    def _strengthen_weak_sections(self, sections, score_result, job_text, all_content):
        """Step 5: Find unused content relevant to weak sections, generate additional bullets."""
        weakest = score_result.get("weakest_section", "").lower()
        missing_kw = score_result.get("missing_keywords", [])

        if not weakest or weakest not in sections:
            return sections

        # Find content items not yet used that match missing keywords
        used_texts = set()
        for section_items in sections.values():
            for item in section_items:
                used_texts.add(item.get("text", "")[:100])

        unused = [item for item in all_content if item.get("text", "")[:100] not in used_texts]

        # Score unused items against missing keywords
        missing_text = " ".join(missing_kw)
        relevant_unused = []
        for item in unused:
            text = item.get("text", "") + " " + item.get("detail", "")
            if (
                any(kw.lower() in text.lower() for kw in missing_kw)
                or calculate_similarity(text, missing_text) > 0.3
            ):  # noqa: E501, SIM114
                relevant_unused.append(item)

        # Add top relevant unused items to the weak section
        for item in relevant_unused[:5]:
            item["section"] = weakest
            sections[weakest].append(item)

        return sections

    def _compile_section_text(self, sections, job_analysis):
        """Step 6: Compile final text from sections."""
        text_parts = []

        if sections.get("summary"):
            text_parts.append("SUMMARY")
            for item in sections["summary"]:
                text_parts.append(item.get("text", ""))
            text_parts.append("")

        if sections.get("experience"):
            text_parts.append("EXPERIENCE")
            # Sort by strategic score
            sorted_exp = sorted(
                sections["experience"],
                key=lambda x: x.get("strategic_score", 0),
                reverse=True,
            )
            for item in sorted_exp:
                text_parts.append(item.get("text", ""))
                if item.get("detail"):
                    text_parts.append(item["detail"])
                text_parts.append("")

        if sections.get("skills"):
            text_parts.append("SKILLS")
            skill_names = [s["text"] for s in sections["skills"]]
            text_parts.append(", ".join(skill_names))
            text_parts.append("")

        if sections.get("accomplishments"):
            text_parts.append("KEY ACCOMPLISHMENTS")
            # Sort: business outcomes with metrics first (by impact type rank,
            # then confidence), then remaining by strategic score.
            # Top-5 outcomes + fill to 10 with others.
            sorted_acc = sorted(
                sections["accomplishments"],
                key=lambda x: (
                    x.get("type") == "business_outcome" and x.get("has_metrics", False),
                    OUTCOME_TYPE_RANK.get(x.get("outcome_type", ""), 0),
                    x.get("confidence", 0) if x.get("type") == "business_outcome" else 0,
                    x.get("strategic_score", 0),
                ),
                reverse=True,
            )
            bo_items = [x for x in sorted_acc if x.get("type") == "business_outcome"][:5]
            other_items = [x for x in sorted_acc if x.get("type") != "business_outcome"]
            final_acc = (bo_items + other_items)[:10]
            for item in final_acc:
                text_parts.append(f"- {item.get('text', '')}")
            text_parts.append("")

        if sections.get("education"):
            text_parts.append("EDUCATION")
            for item in sections["education"]:
                text_parts.append(item.get("text", ""))

        return "\n".join(text_parts)


# Module-level singleton
_compiler = None


def get_agentic_compiler():
    """Get singleton AgenticCompiler instance."""
    global _compiler
    if _compiler is None:
        _compiler = AgenticCompiler()
    return _compiler
