# Resume Optimizer Enhancement Guide

## Objective
Enhance the existing application so it produces more relevant, evidence-backed ATS and recruiter-facing resume outputs using the application's current structure, a local Qdrant instance, and a stricter requirement-to-evidence matching model.

## Design goal
The application should move from general semantic similarity toward a hybrid alignment engine that can:
- normalize job requirements into atomic requirement objects
- map those requirements to evidence from LinkedIn, experience journey, and local resumes
- distinguish direct evidence from inferred alignment
- identify real gaps versus weak wording gaps
- produce targeted rewrites with an audit trail

## Recommended enhancement layers

### 1. Normalization layer
Add a normalization phase before retrieval and before generation.

Inputs:
- LinkedIn local copy
- resume master and variants
- experience journey
- job descriptions

Outputs:
- normalized candidate profile JSON
- normalized job requirements JSON
- canonical skill inventory with synonyms and aliases

What to normalize:
- titles and role families
- tools and platforms
- architecture scope terms
- leadership signals
- business outcomes
- domain terms
- acronyms and synonyms

Examples:
- `CDM` -> `canonical data model`
- `DQ` -> `data quality`
- `DLH` -> `data lakehouse` or `data platform` depending on your taxonomy
- `solution architect` and `solution architecture` should resolve to a shared concept group

### 2. Better chunking
Do not chunk only by token length.

Instead, chunk candidate artifacts by semantic units:
- summary section
- each role block
- each project block
- each notable achievement or architecture initiative
- optional micro-chunks for high-value bullets

Chunk job descriptions by atomic requirements:
- must-have skill
- preferred skill
- leadership requirement
- domain requirement
- education or certification requirement

This prevents large blended chunks from weakening retrieval relevance.

### 3. Qdrant payload enrichment
Keep vectors, but improve payload quality.

Recommended payload fields:
- `doc_type`
- `artifact_id`
- `chunk_id`
- `section`
- `company`
- `title`
- `date_range`
- `skills`
- `canonical_skills`
- `domains`
- `seniority_signals`
- `leadership_signals`
- `tools_platforms`
- `business_outcomes`
- `architecture_scope`
- `evidence_strength`
- `source_path`

These fields let the application filter, score, and explain results instead of relying on raw semantic similarity.

### 4. Hybrid matching model
Do not use vector score alone.

Use a weighted model such as:
- semantic similarity: 0.35
- keyword alignment: 0.20
- evidence strength: 0.20
- seniority alignment: 0.10
- domain alignment: 0.05
- leadership alignment: 0.05
- recency alignment: 0.05

#### Scoring guidance
- `semantic_similarity`: embedding similarity from Qdrant
- `keyword_alignment`: exact phrase or synonym coverage for ATS terms
- `evidence_strength`: directness and quality of the supporting evidence
- `seniority_alignment`: how strongly the evidence supports architect / principal framing
- `domain_alignment`: industry and business-context fit
- `leadership_alignment`: stakeholder influence, strategy, architecture governance
- `recency_alignment`: weight more recent relevant evidence slightly more

### 5. Requirement-to-evidence mapping
For each requirement in a job description, retrieve:
1. top matching candidate evidence chunks
2. nearby skill concept nodes or aliases
3. optional bullet or phrasing templates

Then produce a structured match record:
- requirement id
- overall score
- match type
- subscores
- evidence set
- rewrite recommendation

### 6. Gap classification
Not all gaps are true missing experience.

Classify gaps into:
- missing experience
- weak wording
- missing explicit ATS keyword
- insufficient leadership signal
- seniority mismatch
- domain gap
- unsupported claim risk

This distinction is essential. In many cases, the candidate has the experience, but it is not expressed in ATS-safe or recruiter-scannable language.

### 7. Generation strategy
Do not jump straight from job description to rewritten resume.

Use a pipeline:
1. normalize candidate
2. normalize job requirements
3. retrieve evidence
4. score matches
5. classify gaps
6. create rewrite targets
7. generate tailored resume
8. run unsupported-claim audit

### 8. Output artifacts
For each job description, generate:
- `normalized_candidate_profile.json`
- `normalized_job_requirements.json`
- `matching_results.json`
- `ats_gap_report.md`
- `resume_rewrite_plan.md`
- `tailored_resume.md`
- `interview_story_bank.json`

## Suggested Qdrant collections

### candidate_artifacts
Stores chunks from LinkedIn, resumes, experience journey, and project notes.

### job_requirements
Stores normalized requirement objects from job descriptions.

### skill_concepts
Stores canonical skills, aliases, related terms, and role-family signals.

### achievement_patterns
Optional collection of strong phrasing templates and bullet patterns.

## Suggested implementation sequence

### Phase 1: low-risk enhancement
- keep the existing application structure
- add normalization logic
- enrich Qdrant payloads
- break JD text into atomic requirements
- add hybrid scoring
- add gap classification

### Phase 2: stronger retrieval relevance
- add synonym expansion and taxonomy alignment
- add role-family logic such as architect versus engineer
- add leadership and seniority detection
- add domain weighting

### Phase 3: stronger generation quality
- generate rewrite targets before generating a full resume
- add an unsupported claim audit
- add a recruiter-scan report and ATS report

## Minimal algorithm

```text
For each job description:
  Parse JD into atomic requirements
  Normalize requirement skills, domains, and leadership signals
  For each requirement:
    Query Qdrant candidate_artifacts
    Optionally query skill_concepts
    Compute blended score
    Save evidence-backed match object
  Classify gaps
  Build rewrite targets
  Generate targeted resume
  Audit all claims against evidence
```

## Notes for Claude Code
- enhance the existing app rather than replacing it
- preserve current working ingestion and generation paths where possible
- add new scoring and normalization as isolated modules
- make JSON the canonical reasoning layer
- keep all new outputs machine-readable and traceable
- ask clarifying questions when needed to do a complete, thorough, and no-excuses job
