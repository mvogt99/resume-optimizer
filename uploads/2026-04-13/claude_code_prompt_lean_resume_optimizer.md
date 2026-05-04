Enhance the existing local resume optimizer application rather than replacing it.

Goal: improve relevance and quality of matching between job descriptions and the candidate's actual experience, LinkedIn profile, and local resumes so the output is more ATS-safe, recruiter-friendly, and truthful.

Use the local Qdrant instance as a retrieval layer, but do not rely on vector similarity alone. Add a hybrid matching model that combines:
- semantic similarity
- exact and synonym keyword alignment
- evidence strength
- seniority alignment
- leadership alignment
- domain alignment
- recency alignment

Required upgrades:
1. normalize candidate artifacts into a canonical JSON model
2. parse job descriptions into atomic normalized requirements
3. enrich Qdrant payload metadata
4. retrieve evidence per requirement
5. compute blended match scores
6. classify gaps as one of:
   - missing experience
   - weak wording
   - missing explicit ATS keyword
   - insufficient leadership signal
   - seniority mismatch
   - domain gap
   - unsupported claim risk
7. create rewrite targets before generating a tailored resume
8. audit generated content for unsupported claims

Preserve the current app where practical. Favor incremental enhancement over rewrite.

Use these local reference artifacts:
- `resume_optimizer_schema.production.json`
- `resume_optimizer_enhancement_guide.md`

Generate, per job description:
- normalized_candidate_profile.json
- normalized_job_requirements.json
- matching_results.json
- ats_gap_report.md
- resume_rewrite_plan.md
- tailored_resume.md
- interview_story_bank.json

Important:
- do not invent experience or overstate claims
- use exact ATS keywords where truthful
- keep senior architect / principal positioning where evidence supports it
- optimize for recruiter scanability and standard ATS formatting

If anything materially affects correctness or completeness, ask clarifying questions first so you can do a complete, thorough, and no-excuses job.
