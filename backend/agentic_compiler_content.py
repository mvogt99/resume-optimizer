"""
AgenticCompilerContentMixin — content gathering and strategic selection methods.

Split from agentic_compiler.py to comply with 500-line file limit.
Inherited by AgenticCompiler.
"""

from llm_helper import call_llm_quality, extract_json
from nlp_engine import calculate_similarity, extract_keywords


class AgenticCompilerContentMixin:
    """Mixin providing content-gathering pipeline steps for AgenticCompiler."""

    def _gather_all_content(self, base_text, sources, interview_bullets):
        """Flatten all sources into a list of content items with metadata."""
        items = []

        # Base resume
        if base_text.strip():
            items.append(
                {
                    "text": base_text,
                    "source": "original_resume",
                    "section": "summary",
                    "type": "base",
                }
            )

        # LinkedIn
        linkedin = sources.get("linkedin", {})
        if linkedin:
            for skill in linkedin.get("skills", []):
                name = skill if isinstance(skill, str) else skill.get("name", "")
                endorsements = 0 if isinstance(skill, str) else skill.get("endorsements", 0)
                if name:
                    items.append(
                        {
                            "text": name,
                            "source": "linkedin",
                            "section": "skills",
                            "type": "skill",
                            "endorsements": endorsements,
                        }
                    )

            for exp in linkedin.get("experience", []):
                title = exp.get("title", "")
                company = exp.get("company", "")
                desc = exp.get("description", "")
                header = f"{title} at {company}" if company else title
                if desc:
                    items.append(
                        {
                            "text": header,
                            "detail": desc,
                            "source": "linkedin",
                            "section": "experience",
                            "type": "experience",
                            "company": company,
                        }
                    )
                for acc in exp.get("accomplishments", []):
                    if acc.strip():
                        items.append(
                            {
                                "text": acc,
                                "source": "linkedin",
                                "section": "accomplishments",
                                "type": "accomplishment",
                                "company": company,
                            }
                        )

            for rec in linkedin.get("recommendations", []):
                rec_text = rec.get("text", "") or rec.get("recommendation_text", "")
                if rec_text:
                    items.append(
                        {
                            "text": rec_text[:200],
                            "source": "linkedin_recommendation",
                            "section": "accomplishments",
                            "type": "recommendation",
                        }
                    )

        # Projects
        for proj in sources.get("projects", []):
            client = proj.get("client_name", "Unknown")
            for tech in proj.get("technologies", []):
                t = tech if isinstance(tech, str) else tech.get("name", "")
                if t:
                    items.append(
                        {
                            "text": t,
                            "source": f"project:{client}",
                            "section": "skills",
                            "type": "skill",
                        }
                    )
            for outcome in proj.get("outcomes", []):
                o = outcome if isinstance(outcome, str) else outcome.get("description", "")
                if o:
                    items.append(
                        {
                            "text": f"{o} ({client})",
                            "source": f"project:{client}",
                            "section": "accomplishments",
                            "type": "accomplishment",
                            "company": client,
                        }
                    )
            for contrib in proj.get("role_contributions", []):
                c = contrib if isinstance(contrib, str) else contrib.get("description", "")
                if c:
                    items.append(
                        {
                            "text": f"{c} — {client}",
                            "source": f"project:{client}",
                            "section": "experience",
                            "type": "contribution",
                            "company": client,
                        }
                    )

            # Business outcomes (Phase 13) — structured outcomes with real metrics
            for bo in proj.get("business_outcomes", []):
                if not isinstance(bo, dict):
                    continue
                title = bo.get("outcome_title", "")
                desc = bo.get("description", "")
                metric = bo.get("metric_value", "")
                text = title or desc
                if not text:
                    continue
                # Include metric in the text if not already present
                if metric and metric not in text:
                    text = f"{text} ({metric})"
                items.append(
                    {
                        "text": f"{text} — {client}",
                        "source": f"project:{client}",
                        "section": "accomplishments",
                        "type": "business_outcome",
                        "company": client,
                        "has_metrics": bool(metric),
                        "confidence": bo.get("confidence", 0.5),
                        "outcome_type": bo.get("outcome_type", ""),
                    }
                )

        # Journey
        journey = sources.get("journey", {})
        if journey:
            for entry in journey.get("star_entries", []):
                content = entry.get("content", "")
                if content:
                    items.append(
                        {
                            "text": content,
                            "source": "journey",
                            "section": "accomplishments",
                            "type": "star_entry",
                        }
                    )
            for skill in journey.get("skills", []):
                name = skill.get("name", "")
                if name:
                    items.append(
                        {
                            "text": name,
                            "source": "journey",
                            "section": "skills",
                            "type": "skill",
                        }
                    )

        # Experiences
        for exp in sources.get("experiences", []):
            title = exp.get("title", "")
            employer = exp.get("employer", "")
            client = exp.get("client", "")
            header = f"{title} at {employer}"
            if client:
                header += f" ({client})"

            bullets = exp.get("bullet_points", [])
            if bullets:
                detail = "\n".join(f"- {b}" for b in bullets)
                items.append(
                    {
                        "text": header,
                        "detail": detail,
                        "source": "experience_interview",
                        "section": "experience",
                        "type": "experience",
                        "company": employer,
                    }
                )
            for tech in exp.get("technologies", []):
                items.append(
                    {
                        "text": tech,
                        "source": "experience_interview",
                        "section": "skills",
                        "type": "skill",
                    }
                )

        # Interview bullets
        for bullet in interview_bullets:
            items.append(
                {
                    "text": bullet.get("text", ""),
                    "source": "builder_interview",
                    "section": "experience",
                    "type": "interview_bullet",
                    "related_skills": bullet.get("related_skills", []),
                    "has_metrics": bullet.get("has_metrics", False),
                    "star_complete": bullet.get("star_complete", False),
                }
            )

        return items

    def _strategic_selection(self, job_text, all_content):
        """Step 1: Analyze job description and score content items."""
        # LLM analysis of job requirements
        prompt = (
            "Analyze this job description and extract structured requirements.\n\n"
            f"Job description:\n{job_text[:3000]}\n\n"
            "Return a JSON object with:\n"
            '- "must_have": list of absolutely required skills/experiences\n'
            '- "nice_to_have": list of preferred but optional skills\n'
            '- "emphasis_pattern": what the job emphasizes most '
            "(e.g., 'leadership', 'technical depth', 'cross-functional')\n"
            '- "ats_keywords": list of 20-30 keywords an ATS system would scan for\n'
            '- "seniority_signals": list of seniority indicators in the posting\n'
        )

        raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=2048)
        job_analysis = extract_json(raw) if raw else None
        if not isinstance(job_analysis, dict):
            # Fallback to NLP extraction
            keywords = list(extract_keywords(job_text, 30))
            job_analysis = {
                "must_have": keywords[:10],
                "nice_to_have": keywords[10:20],
                "emphasis_pattern": "general",
                "ats_keywords": keywords,
                "seniority_signals": [],
            }

        # Score each content item
        must_have = {k.lower() for k in job_analysis.get("must_have", [])}
        ats_kw = {k.lower() for k in job_analysis.get("ats_keywords", [])}

        for item in all_content:
            text = (item.get("text", "") + " " + item.get("detail", "")).lower()

            # NLP similarity (50%)
            sim_score = calculate_similarity(text, job_text) if len(text) > 10 else 0

            # Must-have matches (30%)
            must_matches = sum(1 for kw in must_have if kw in text)
            must_score = min(must_matches / max(len(must_have), 1), 1.0)

            # ATS keyword matches (20%)
            ats_matches = sum(1 for kw in ats_kw if kw in text)
            ats_score = min(ats_matches / max(len(ats_kw), 1), 1.0)

            score = sim_score * 50 + must_score * 30 + ats_score * 20

            # Boost business outcomes with real metrics (+20% bonus)
            if item.get("type") == "business_outcome" and item.get("has_metrics"):
                score = min(score + 20, 100)

            item["strategic_score"] = round(score, 1)

        return job_analysis

    def _assemble_sections(self, all_content, job_analysis, interview_bullets):
        """Step 2: Organize content into sections, weaving interview bullets."""
        sections = {
            "summary": [],
            "experience": [],
            "skills": [],
            "accomplishments": [],
            "education": [],
        }

        # Sort all content by strategic score
        scored_content = sorted(
            all_content, key=lambda x: x.get("strategic_score", 0), reverse=True
        )

        # Separate interview bullets for weaving
        interview_items = [
            item for item in scored_content if item.get("type") == "interview_bullet"
        ]
        non_interview = [item for item in scored_content if item.get("type") != "interview_bullet"]

        # Place non-interview items into sections
        for item in non_interview:
            section = item.get("section", "accomplishments")
            if section in sections:
                sections[section].append(item)

        # Weave interview bullets into matching experience entries
        unmatched_bullets = []
        for bullet in interview_items:
            matched = False
            bullet_skills = {s.lower() for s in bullet.get("related_skills", [])}
            bullet_text = bullet.get("text", "").lower()

            for exp in sections["experience"]:
                exp_company = (exp.get("company", "") or "").lower()
                exp_text = (exp.get("text", "") + " " + exp.get("detail", "")).lower()

                # Match by company/employer overlap or skill overlap
                company_match = exp_company and exp_company in bullet_text
                skill_overlap = any(s in exp_text for s in bullet_skills if s != "general")
                similarity = calculate_similarity(bullet.get("text", ""), exp.get("text", "")) > 0.3

                if company_match or skill_overlap or similarity:
                    detail = exp.get("detail", "")
                    exp["detail"] = (detail + "\n" if detail else "") + f"- {bullet['text']}"
                    matched = True
                    break

            if not matched:
                unmatched_bullets.append(bullet)

        # Only unmatched bullets go to accomplishments
        for bullet in unmatched_bullets:
            sections["accomplishments"].append(bullet)

        # Deduplicate skills
        seen_skills = set()
        unique_skills = []
        must_have = {k.lower() for k in job_analysis.get("must_have", [])}

        for s in sections["skills"]:
            key = s["text"].lower().strip()
            if key not in seen_skills and len(key) > 1:
                seen_skills.add(key)
                s["is_must_have"] = key in must_have
                unique_skills.append(s)

        # Sort skills: must-have first, then by strategic score
        unique_skills.sort(
            key=lambda x: (not x.get("is_must_have", False), -x.get("strategic_score", 0))
        )
        sections["skills"] = unique_skills

        return sections
