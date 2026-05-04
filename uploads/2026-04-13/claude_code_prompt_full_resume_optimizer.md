# Claude Code Prompt — Full Resume Optimizer Enhancement

You are enhancing an existing local resume optimizer application.

The application already exists. Your task is **not** to replace it from scratch. Your task is to enhance it so it produces more relevant, more accurate, more ATS-safe, and more recruiter-useful results.

The application uses local artifacts and a local Qdrant instance. It must better match job requirements to the candidate's actual experience journey, LinkedIn profile, and local resumes.

Your output must be thorough, evidence-based, implementation-oriented, and compatible with the current application structure wherever practical.

If anything is unclear and would materially affect correctness, completeness, or implementation quality, you should ask clarifying questions first so you can do a complete, thorough, and no-excuses job.

## Primary goal
Enhance the existing application so it can:
1. parse job descriptions into atomic, normalized requirements
2. normalize candidate artifacts into a shared skill and evidence model
3. retrieve better evidence from Qdrant
4. score requirement-to-evidence matches using a hybrid model, not vector similarity alone
5. identify true experience gaps versus weak wording or ATS-keyword gaps
6. generate stronger targeted resume rewrites without inventing unsupported claims
7. produce machine-readable JSON outputs and human-readable markdown summaries

## Constraints
- Preserve the existing application where reasonable.
- Favor incremental enhancement over rewrite.
- Do not invent experience, seniority, tools, outcomes, or leadership claims.
- You may infer equivalent terminology, but inferred items must not be presented as hard facts unless supported by evidence.
- Optimize for ATS compatibility and recruiter readability.
- Maintain senior architect / principal-level positioning where the evidence supports it.

## Local environment assumptions
- candidate artifacts exist locally, including LinkedIn profile, experience journey, and one or more resumes
- job descriptions exist locally
- Qdrant is available locally
- the current application already ingests and/or retrieves content, but needs better relevance and better matching logic

## Required enhancement approach

### 1. Add a normalization layer
Build or improve a normalization layer that produces:
- normalized candidate profile JSON
- normalized job requirements JSON
- canonical skill inventory
- synonym and alias mapping
- role-family mappings such as architect, principal architect, solution architect, enterprise architect, data architect

Normalization should cover:
- skills
- tools and platforms
- architecture concepts
- leadership signals
- business outcomes
- domain context
- acronyms and synonyms

### 2. Improve chunking strategy
Do not rely only on fixed token chunks.

Candidate artifacts should be chunked by semantic units such as:
- summary
- each experience block
- project blocks
- achievement bullets
- architecture initiatives

Job descriptions should be chunked into atomic requirement objects such as:
- must-have
- preferred
- leadership
- domain
- certification
- education

### 3. Improve Qdrant usage
Use Qdrant as a retrieval layer with richer payload metadata.

Recommended payload fields include:
- doc_type
- artifact_id
- chunk_id
- section
- company
- title
- date_range
- skills
- canonical_skills
- domains
- seniority_signals
- leadership_signals
- tools_platforms
- business_outcomes
- architecture_scope
- evidence_strength
- source_path

Use metadata-aware retrieval where useful.

### 4. Replace simple matching with hybrid scoring
For each job requirement, retrieve candidate evidence and compute a weighted blended score.

Use a model similar to:
- semantic_similarity: 0.35
- keyword_alignment: 0.20
- evidence_strength: 0.20
- seniority_alignment: 0.10
- domain_alignment: 0.05
- leadership_alignment: 0.05
- recency_alignment: 0.05

Each match should produce:
- requirement id
- match type
- overall score
- subscores
- supporting evidence
- recommended resume action

### 5. Add gap classification
Classify gaps into:
- missing experience
- weak wording
- missing explicit ATS keyword
- insufficient leadership signal
- seniority mismatch
- domain gap
- unsupported claim risk

This distinction matters and must be explicit in the outputs.

### 6. Add a rewrite-target stage before generation
Before generating a tailored resume, create rewrite targets for:
- summary
- headline
- key skills
- selected experience bullets
- optional selected project bullets

Each rewrite target should include:
- reason for rewrite
- supporting evidence refs
- recommended keywords
- risk warnings if evidence is weak

### 7. Add an unsupported-claim audit
Before finalizing output, audit the generated resume and flag any claims that are not sufficiently supported by evidence.

## Required outputs
For each processed job description, generate the following:
1. normalized_candidate_profile.json
2. normalized_job_requirements.json
3. matching_results.json
4. ats_gap_report.md
5. resume_rewrite_plan.md
6. tailored_resume.md
7. interview_story_bank.json

## Deliverables requested from you
Enhance the existing codebase and produce:
1. a concise architecture explanation of the enhancement
2. a file-by-file change plan
3. any new modules or classes required
4. any changes to ingestion, normalization, retrieval, scoring, or generation flows
5. updated JSON contracts if needed
6. example outputs
7. a list of clarifying questions if needed

## Canonical schema reference
Use the file `resume_optimizer_schema.production.json` as the canonical production schema unless the existing app requires a clearly justified compatible extension.

## Enhancement guide reference
Use the file `resume_optimizer_enhancement_guide.md` as the implementation direction.

## Quality bar
Do not provide a shallow answer.
Do not stop at keyword substitution.
Do not assume vector similarity alone is sufficient.
Think like:
- a hiring manager
- a recruiter
- an ATS parser
- a principal architect interviewer
- a truthfulness auditor

## Ask clarifying questions when needed
If any local file locations, current application architecture, current retrieval logic, current output format, or embedding pipeline details are unclear, ask clarifying questions first so you can do a complete, thorough, and no-excuses job.
