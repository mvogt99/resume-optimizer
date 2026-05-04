"""Stage definitions, template questions, and stage-advancement logic for resume interview."""

from resume_interview_parsers import is_affirmative

# Main stages (ordered)
STAGES = [
    "welcome",  # Name / preferred name
    "contact",  # Email, phone, city/state
    "objective",  # Career field, years experience, goal
    "experience",  # Loop: one job at a time
    "education",  # Loop: one degree/diploma at a time
    "skills",  # Hard skills, soft skills, certifications
    "optional",  # Volunteer, awards, languages
    "review",  # Preview and finalize
    "complete",  # Done
]

STAGE_LABELS = [
    "Welcome",
    "Contact",
    "Objective",
    "Experience",
    "Education",
    "Skills",
    "Optional",
    "Review",
]

TEMPLATE_QUESTIONS = {
    "welcome": (
        "Hi! I'm going to help you build your resume step by step — it usually takes "
        "about 10 minutes.\n\nLet's start with your name. What is your full name as "
        "you'd like it to appear on your resume?"
    ),
    "welcome_2": (
        "Nice to meet you, {name}! Do you go by a different name at work, "
        "or should I use {name} throughout your resume?"
    ),
    "contact": (
        "Now let's get your contact information.\n\n"
        "What is your email address and phone number?\n"
        "(Example: jane@email.com, 555-123-4567)"
    ),
    "contact_location": (
        "What city and state are you in?\n"
        "(Example: Austin, TX — no street address needed on a resume.)"
    ),
    "objective": (
        "What type of work are you looking for?\n"
        "For example: elementary school teacher, registered nurse, plumber, retail manager.\n\n"
        "And roughly how many years of experience do you have in this field?"
    ),
    "objective_goal": (
        "What kind of position or next step are you hoping for?\n"
        "For example: 'I'd like to move into school administration' or "
        "'I'm looking for a full-time nursing position.'"
    ),
    "experience_start": (
        "Let's document your work history — we'll go one job at a time, "
        "starting with the most recent.\n\n"
        "What was your most recent job title?\n"
        "(Example: 5th Grade Teacher, Shift Supervisor, Licensed Electrician)"
    ),
    "exp_employer": (
        "Who did you work for? What's the name of the company, school, or organization?"
    ),
    "exp_dates": (
        "When did you start and end this job?\n"
        "(Example: August 2018 to Present, or June 2015 to March 2020)\n"
        "If you're still there, just say 'present'."
    ),
    "exp_duties": (
        "What did you do in this role? Share your main responsibilities — "
        "even one or two is a great start.\n\n"
        "For example, a teacher might say:\n"
        "- Taught reading and math to 28 second-graders\n"
        "- Created weekly lesson plans\n"
        "- Met with parents quarterly to discuss progress\n\n"
        "What were your main responsibilities at {employer}?"
    ),
    "exp_more": (
        "Got it! You can add more responsibilities if you like — "
        "aim for 3-5 total for best results. "
        "Or say **'next'** when you're ready to move on."
    ),
    "exp_another": (
        "Do you have another job to add to your resume?\n\n"
        "Say **yes** to add another job, or **no** if that covers your work history."
    ),
    "education_start": (
        "Now let's add your education.\n\n"
        "What is your highest level of education?\n"
        "(Example: Bachelor's in Education, Associate's in Nursing, "
        "High school diploma, Trade certification)"
    ),
    "edu_school": "What school, college, or training program did you attend?",
    "edu_year": (
        "What year did you graduate or complete the program?\n"
        "(If you didn't finish, that's okay — just tell me and I'll note it appropriately.)"
    ),
    "edu_more": (
        "Do you have any other degrees, diplomas, or certifications to add?\n\n"
        "Say **yes** to add another, or **no** to continue."
    ),
    "skills": (
        "Let's list your skills. What are you good at? Think about:\n\n"
        "- **Technical skills** (software, equipment, tools you use regularly)\n"
        "- **People skills** (communication, leadership, teamwork)\n"
        "- **Certifications or licenses** (teaching certificate, CNA, CDL, etc.)\n\n"
        "Just list them out — for example: 'Google Classroom, parent communication, "
        "CPR certified, bilingual in Spanish'"
    ),
    "optional": (
        "Almost done! Do any of these apply to you?\n\n"
        "- **Volunteer work** (coaching, church, food bank, etc.)\n"
        "- **Awards or recognition** (Employee of the Month, Dean's List, etc.)\n"
        "- **Languages** other than English\n"
        "- **Publications or projects**\n\n"
        "Share what's relevant, or say 'none' to skip."
    ),
    "review": (
        "Your resume is ready for review!\n\n"
        "Take a look at the preview. You can:\n"
        "- Click **Finalize & Save** to save it\n"
        "- Tell me anything you'd like to change\n\n"
        "How does it look?"
    ),
    "complete": (
        "Your resume has been saved! You can now use it in the **Optimize** tab "
        "to tailor it for specific job postings, or download it directly."
    ),
}


def _exp_more_feedback(context, exp_idx):
    """Dynamic feedback for exp_more: confirms duties recorded, gives strength signal."""
    duties = []
    if exp_idx < len(context.get("experiences", [])):
        duties = context["experiences"][exp_idx].get("duties", [])
    count = len(duties)
    noun = "responsibility" if count == 1 else "responsibilities"

    # Duty preview (first 3, truncated)
    preview_lines = []
    for d in duties[:3]:
        preview_lines.append(f"  ✓ {d[:70]}{'...' if len(d) > 70 else ''}")
    if count > 3:
        preview_lines.append(f"  ✓ ...and {count - 3} more")
    preview = "\n".join(preview_lines)

    # Strength signal
    if count <= 2:
        level = "Getting started"
        guidance = (
            "Adding 2-3 more will make this section significantly stronger — "
            "the more specific you are, the better your resume stands out."
        )
    elif count <= 4:
        level = "Good"
        guidance = (
            "One or two more would round this out nicely, "
            "but you're in good shape to move on if you prefer."
        )
    else:
        level = "Strong"
        guidance = "You have excellent coverage for this role!"

    return (
        f"Here's what I've recorded ({count} {noun}):\n{preview}\n\n"
        f"**Strength: {level}** — {guidance}\n\n"
        f"Share another responsibility to add it, or say **'next'** to move on."
    )


def get_template_response(stage, sub_stage, context, exp_idx):
    """Return the template question for the current stage/sub-stage."""
    name = context.get("preferred_name") or context.get("name") or "there"
    employer = ""
    if exp_idx < len(context.get("experiences", [])):
        employer = context["experiences"][exp_idx].get("employer", "")

    if stage == "welcome":
        if not context.get("name"):
            return TEMPLATE_QUESTIONS["welcome"]
        return TEMPLATE_QUESTIONS["welcome_2"].format(name=name)

    elif stage == "contact":
        if sub_stage == "location":
            return TEMPLATE_QUESTIONS["contact_location"]
        return TEMPLATE_QUESTIONS["contact"]

    elif stage == "objective":
        if sub_stage == "goal":
            return TEMPLATE_QUESTIONS["objective_goal"]
        return TEMPLATE_QUESTIONS["objective"]

    elif stage == "experience":
        if sub_stage == "exp_more":
            return _exp_more_feedback(context, exp_idx)
        mapping = {
            "": TEMPLATE_QUESTIONS["experience_start"],
            "exp_title": TEMPLATE_QUESTIONS["experience_start"],
            "exp_employer": TEMPLATE_QUESTIONS["exp_employer"],
            "exp_dates": TEMPLATE_QUESTIONS["exp_dates"],
            "exp_duties": TEMPLATE_QUESTIONS["exp_duties"].format(employer=employer or "this role"),
            "exp_another": TEMPLATE_QUESTIONS["exp_another"],
        }
        return mapping.get(sub_stage, TEMPLATE_QUESTIONS["experience_start"])

    elif stage == "education":
        mapping = {
            "": TEMPLATE_QUESTIONS["education_start"],
            "edu_degree": TEMPLATE_QUESTIONS["education_start"],
            "edu_school": TEMPLATE_QUESTIONS["edu_school"],
            "edu_year": TEMPLATE_QUESTIONS["edu_year"],
            "edu_more": TEMPLATE_QUESTIONS["edu_more"],
        }
        return mapping.get(sub_stage, TEMPLATE_QUESTIONS["education_start"])

    return {
        "skills": TEMPLATE_QUESTIONS["skills"],
        "optional": TEMPLATE_QUESTIONS["optional"],
        "review": TEMPLATE_QUESTIONS["review"],
        "complete": TEMPLATE_QUESTIONS["complete"],
    }.get(stage, "Please continue — I'm listening.")


def advance_stage(stage, sub_stage, message, context, exp_idx, edu_idx):
    """Determine the next (stage, sub_stage, exp_idx, edu_idx)."""
    msg_lower = message.lower().strip()

    if stage == "welcome":
        if not context.get("name"):
            return "welcome", "", exp_idx, edu_idx
        if not context.get("_welcome_done"):
            return "welcome", "_pref", exp_idx, edu_idx
        return "contact", "", exp_idx, edu_idx

    elif stage == "contact":
        has_email = bool(context.get("email"))
        has_phone = bool(context.get("phone"))
        has_location = bool(context.get("location"))
        if not (has_email and has_phone):
            return "contact", "", exp_idx, edu_idx
        if not has_location:
            return "contact", "location", exp_idx, edu_idx
        return "objective", "", exp_idx, edu_idx

    elif stage == "objective":
        if not context.get("career_field"):
            return "objective", "", exp_idx, edu_idx
        if not context.get("objective"):
            return "objective", "goal", exp_idx, edu_idx
        return "experience", "exp_title", exp_idx, edu_idx

    elif stage == "experience":
        return _advance_experience(sub_stage, msg_lower, context, exp_idx, edu_idx)

    elif stage == "education":
        return _advance_education(sub_stage, msg_lower, context, exp_idx, edu_idx)

    elif stage == "skills":
        skills_count = (
            len(context.get("hard_skills", []))
            + len(context.get("soft_skills", []))
            + len(context.get("certifications", []))
        )
        if skills_count >= 2:
            return "optional", "", exp_idx, edu_idx
        return "skills", "", exp_idx, edu_idx

    elif stage == "optional":
        return "review", "", exp_idx, edu_idx

    elif stage == "review":
        if any(
            w in msg_lower
            for w in ["looks good", "perfect", "great", "save", "finalize", "done", "ready", "yes"]
        ):
            return "complete", "", exp_idx, edu_idx
        return "review", "", exp_idx, edu_idx

    return stage, sub_stage, exp_idx, edu_idx


def _advance_experience(sub_stage, msg_lower, context, exp_idx, edu_idx):
    exp = context["experiences"][exp_idx] if exp_idx < len(context["experiences"]) else {}

    if sub_stage in ("", "exp_title"):
        if exp.get("title"):
            return "experience", "exp_employer", exp_idx, edu_idx
        return "experience", "exp_title", exp_idx, edu_idx

    elif sub_stage == "exp_employer":
        if exp.get("employer"):
            return "experience", "exp_dates", exp_idx, edu_idx
        return "experience", "exp_employer", exp_idx, edu_idx

    elif sub_stage == "exp_dates":
        if exp.get("start_date"):
            return "experience", "exp_duties", exp_idx, edu_idx
        return "experience", "exp_dates", exp_idx, edu_idx

    elif sub_stage == "exp_duties":
        # Advance to exp_more as soon as any duty is recorded — exp_more handles
        # "add more or say next", so the user is always prompted clearly.
        if exp.get("duties"):
            return "experience", "exp_more", exp_idx, edu_idx
        return "experience", "exp_duties", exp_idx, edu_idx

    elif sub_stage == "exp_more":
        if any(
            w in msg_lower
            for w in [
                "next",
                "done",
                "that's all",
                "thats all",
                "no more",
                "move on",
                "continue",
                "move",
            ]
        ):
            return "experience", "exp_another", exp_idx, edu_idx
        # If user added more duties, stay in exp_more to allow further additions
        return "experience", "exp_more", exp_idx, edu_idx

    elif sub_stage == "exp_another":
        if is_affirmative(msg_lower):
            return "experience", "exp_title", exp_idx + 1, edu_idx
        return "education", "edu_degree", exp_idx, edu_idx

    return "experience", sub_stage, exp_idx, edu_idx


def _advance_education(sub_stage, msg_lower, context, exp_idx, edu_idx):
    edu = context["education"][edu_idx] if edu_idx < len(context["education"]) else {}

    if sub_stage in ("", "edu_degree"):
        if edu.get("degree"):
            return "education", "edu_school", exp_idx, edu_idx
        return "education", "edu_degree", exp_idx, edu_idx

    elif sub_stage == "edu_school":
        if edu.get("school"):
            return "education", "edu_year", exp_idx, edu_idx
        return "education", "edu_school", exp_idx, edu_idx

    elif sub_stage == "edu_year":
        if edu.get("year"):
            return "education", "edu_more", exp_idx, edu_idx
        return "education", "edu_year", exp_idx, edu_idx

    elif sub_stage == "edu_more":
        if is_affirmative(msg_lower):
            return "education", "edu_degree", exp_idx, edu_idx + 1
        return "skills", "", exp_idx, edu_idx

    return "education", sub_stage, exp_idx, edu_idx


def progress_info(stage):
    """Return progress data for the frontend progress bar."""
    display_stages = STAGES[:-1]  # exclude "complete"
    try:
        idx = display_stages.index(stage)
    except ValueError:
        idx = len(display_stages) - 1
    return {
        "stage_index": idx,
        "total_stages": len(display_stages),
        "percent": int((idx / len(display_stages)) * 100),
        "stage_labels": STAGE_LABELS,
    }
