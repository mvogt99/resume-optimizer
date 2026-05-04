"""
Generate personalized interview preparation guides based on
real resume data, job description, and LinkedIn profile.
"""

from nlp_engine import extract_entities, extract_keywords


def generate_interview_guide(resume_data, job_text, linkedin_profile=None):
    """
    Build a dynamic interview guide with role-specific personas,
    tailored questions, and STAR method examples from real experience.
    """
    job_keywords = extract_keywords(job_text, 15)
    job_entities = extract_entities(job_text)
    org_names = [ent[0] for ent in job_entities if ent[1] == "ORG"]

    resume_skills = resume_data.get("skills", [])
    experience = resume_data.get("experience", [])

    # Extract key skills overlap
    resume_skills_lower = {s.lower() for s in resume_skills}
    matching_skills = [kw for kw in job_keywords if kw.lower() in resume_skills_lower]
    missing_skills = [kw for kw in job_keywords if kw.lower() not in resume_skills_lower]

    # Build personas based on the actual job description
    personas = _build_personas(job_text, job_keywords, matching_skills, missing_skills)

    # Build STAR examples from real experience
    star_examples = _build_star_examples(experience, linkedin_profile)

    # Key talking points
    talking_points = _build_talking_points(matching_skills, missing_skills, experience, org_names)

    return {
        "interview_personas": personas,
        "star_examples": star_examples,
        "talking_points": talking_points,
        "key_skills_to_highlight": matching_skills[:10],
        "skills_gaps_to_address": missing_skills[:5],
        "response_framework": {
            "star_method": {
                "situation": "Describe the context and challenge",
                "task": "Explain your specific role and responsibility",
                "action": "Detail the steps you took",
                "result": "Share measurable outcomes and impact",
            }
        },
    }


def _build_personas(job_text, job_keywords, matching_skills, missing_skills):
    """Generate interviewer personas tailored to the job."""
    job_lower = job_text.lower()

    # Detect job level/type for persona customization
    is_senior = any(
        kw in job_lower
        for kw in ["senior", "lead", "principal", "director", "manager", "architect"]
    )
    is_technical = any(
        kw in job_lower
        for kw in ["engineer", "developer", "architect", "technical", "software", "data"]
    )

    personas = [
        {
            "persona": "HR / Recruiter",
            "focus": "Culture fit, communication, career trajectory",
            "questions": [
                "Tell me about yourself and your career journey.",
                "Why are you interested in this role?",
                "How do you handle disagreements with team members?",
                "What's your ideal work environment?",
                "Where do you see yourself in 3-5 years?",
            ],
            "tips": [
                "Connect your experience to the company's mission",
                (
                    f"Highlight these matching skills naturally: {', '.join(matching_skills[:5])}"
                    if matching_skills
                    else "Research the company's values and connect your experience to them"
                ),
                "Show enthusiasm for the specific role, not just any job",
                "Prepare a concise 2-minute career narrative",
            ],
        },
        {
            "persona": "Hiring Manager",
            "focus": (
                "Leadership, impact, team dynamics"
                if is_senior
                else "Problem-solving, growth potential, team contribution"
            ),
            "questions": [
                "Walk me through your most impactful project.",
                "How do you prioritize when you have competing deadlines?",
                (
                    "Tell me about a time you had to influence without authority."
                    if is_senior
                    else "Tell me about a time you went above and beyond."
                ),
                "What would your first 90 days look like in this role?",
                "How do you stay current in your field?",
            ],
            "tips": [
                "Quantify achievements (percentages, dollar amounts, team sizes)",
                (
                    "Show strategic thinking, not just task execution"
                    if is_senior
                    else "Show initiative and eagerness to learn"
                ),
                "Have specific examples ready for each skill area",
                f"Be ready to discuss: {', '.join(job_keywords[:5])}",
            ],
        },
    ]

    if is_technical:
        tech_keywords = [
            kw
            for kw in job_keywords
            if kw.lower() not in {"team", "communication", "leadership", "management"}
        ]
        personas.append(
            {
                "persona": "Technical Interviewer",
                "focus": "Technical depth, problem-solving approach, system design",
                "questions": [
                    (
                        f"Describe your experience with {tech_keywords[0]}."
                        if tech_keywords
                        else "Describe a complex technical challenge you solved."
                    ),
                    "How do you approach debugging a production issue?",
                    "Walk me through how you would design a system for [relevant scenario].",
                    "What's your testing philosophy?",
                    "Tell me about a technical decision you made that you'd do differently now.",
                ],
                "tips": [
                    (
                        f"Prepare deep-dive examples for: {', '.join(tech_keywords[:5])}"
                        if tech_keywords
                        else "Prepare detailed technical examples"
                    ),
                    "Explain your thought process, not just the solution",
                    "Be honest about what you don't know — show how you'd learn it",
                    (
                        f"Address skill gaps proactively: {', '.join(missing_skills[:3])}"
                        if missing_skills
                        else "Show breadth across the technical stack mentioned"
                    ),
                ],
            }
        )

    return personas


def _build_star_examples(experience, linkedin_profile=None):
    """Build STAR method example frameworks from real experience."""
    examples = []

    # Combine resume experience with LinkedIn experience
    all_experience = list(experience)
    if linkedin_profile:
        for exp in linkedin_profile.get("experience", []):
            all_experience.append(exp)

    seen_titles = set()
    for exp in all_experience:
        title = exp.get("title", "")
        company = exp.get("company", "")
        key = f"{title}@{company}"
        if key in seen_titles or not title:
            continue
        seen_titles.add(key)

        desc = exp.get("description", "")
        accomplishments = exp.get("accomplishments", [])

        # Pick the most quantified accomplishment if available
        best_accomplishment = ""
        for acc in accomplishments:
            if any(c.isdigit() for c in acc):
                best_accomplishment = acc
                break
        if not best_accomplishment and accomplishments:
            best_accomplishment = accomplishments[0]

        example = {
            "role": f"{title} at {company}" if company else title,
            "situation": (
                f"In my role as {title} at {company}..." if company else f"In my role as {title}..."
            ),
            "suggested_focus": (
                best_accomplishment
                if best_accomplishment
                else desc[:200] if desc else "Describe a key challenge or project"
            ),
        }
        examples.append(example)

        if len(examples) >= 5:
            break

    return examples


def _build_talking_points(matching_skills, missing_skills, experience, org_names):
    """Generate key talking points for the interview."""
    points = []

    if matching_skills:
        points.append(
            {
                "topic": "Skill Alignment",
                "point": (
                    f"You match {len(matching_skills)} key requirements:"
                    f" {', '.join(matching_skills[:8])}"
                ),
                "advice": "Weave these into your answers naturally with specific examples",
            }
        )

    if missing_skills:
        points.append(
            {
                "topic": "Addressing Gaps",
                "point": f"You may be asked about: {', '.join(missing_skills[:5])}",
                "advice": "Frame as areas of active learning or adjacent experience",
            }
        )

    if experience:
        years_count = len(experience)
        points.append(
            {
                "topic": "Experience Depth",
                "point": f"You have {years_count} role(s) to draw from for examples",
                "advice": "Prepare 2-3 STAR stories from your most relevant roles",
            }
        )

    if org_names:
        points.append(
            {
                "topic": "Company Research",
                "point": f"Companies mentioned: {', '.join(org_names[:3])}",
                "advice": (
                    "Research these organizations and their" " relationship to the hiring company"
                ),
            }
        )

    return points
