# Resume Optimizer Enhancement Plan — Hybrid Alignment Engine

**Date:** 2026-04-13
**Status:** APPROVED ARCHITECTURE — awaiting phasing decision + model swap before execution
**Source docs:** `uploads/2026-04-13/resume_optimizer_enhancement_guide.md`, `resume_optimizer_schema.production.json`, `claude_code_prompt_full_resume_optimizer.md`

## Problem Statement

The current scoring pipeline (`resume_scorer.py`) uses 4 signals — keyword overlap (20%), semantic similarity (20%), endorsement-weighted skills match (50%), section completeness (10%). This is fundamentally a word-counting engine. It cannot distinguish equivalent technologies (Kinesis vs Kafka), weak wording from missing experience, seniority-level contributions, leadership signals, or recency of evidence.

## Target Architecture

Replace the flat keyword-matching model with an **evidence-based hybrid alignment engine** that:
1. Normalizes job requirements into atomic, typed requirement objects
2. Normalizes candidate artifacts into a canonical skill/evidence model
3. Matches each requirement individually against specific career evidence
4. Scores matches on 7 dimensions (not just keyword overlap)
5. Classifies gaps precisely (7 types, not binary missing/present)
6. Generates targeted rewrites with an audit trail
7. Audits generated claims against evidence

## Key Architecture Decision: ArangoDB Only (No Qdrant)

**Decision:** Drop Qdrant from the design. Use ArangoDB as the sole data layer. Compute vector similarity in Python.

**Rationale:**
- ArangoDB 3.12.4 already stores 6,130 skills, 4,019 business outcomes, 5,437 technologies with graph edge provenance across 6 client projects
- Graph traversal provides evidence chains (skill → client → outcome → technology) that flat Qdrant payloads cannot
- Only 1 of 7 scoring dimensions (semantic_similarity, weight 0.35) requires vector math — computed in Python via `all-MiniLM-L6-v2` (already loaded in `nlp_engine.py`) + numpy cosine similarity
- ArangoSearch with `text_en` analyzer handles full-text/BM25 search
- Single-user application — no concurrent query scale requirements
- If native vector indexing is ever needed, ArangoDB 3.12 supports it via `--experimental-vector-index` flag (one container restart)

**Collection mapping (guide → ArangoDB):**

| Guide's Qdrant Collection | ArangoDB Implementation |
|---------------------------|------------------------|
| `candidate_artifacts` | New `ro_evidence_chunks` — semantic chunks with embeddings as document fields |
| `job_requirements` | New `ro_job_requirements` — atomic typed requirement objects |
| `skill_concepts` | Enriched existing `ro_skills` — add aliases, canonical mappings, role-family signals |
| `achievement_patterns` | Query existing `ro_business_outcomes` with template patterns |

## Existing Assets (What We Already Have)

| Asset | Location | Count | Enhancement Needed |
|-------|----------|-------|--------------------|
| Skills inventory | `ro_skills` | 6,130 | Add aliases, synonyms, canonical grouping |
| Business outcomes | `ro_business_outcomes` | 4,019 | Add evidence_strength, scope_tags |
| Technologies | `ro_technologies` | 5,437 | Add aliases, grouping |
| Governance controls | `ro_governance_controls` | 4,633 | Map to compliance gap types |
| Skill→Client edges | `ro_client_demonstrated_skill` | 6,442 | Already provides provenance |
| Outcome→Client edges | `ro_client_produced_outcome` | 4,422 | Already provides evidence chains |
| LinkedIn profile | `linkedin_cache` + file | 76 skills, 4 roles, 9 recs | Normalize to canonical skills |
| Sentence transformer | `nlp_engine.py` | `all-MiniLM-L6-v2` | Compute embeddings for evidence chunks |
| NLP extraction | `nlp_engine.py` | spaCy `en_core_web_md` + NLTK | Keep for keyword extraction |
| Keyword grouper | `keyword_grouper.py` | LLM semantic grouping | Integrate as user-facing view |
| Keyword equivalency | `keyword_equivalency.py` | Interview + rewrite | Becomes user-override layer on top of auto-normalization |

## Hybrid Scoring Model (7 Dimensions)

| Dimension | Weight | Implementation |
|-----------|--------|----------------|
| `semantic_similarity` | 0.35 | Python: embed requirement + evidence chunks, numpy cosine similarity |
| `keyword_alignment` | 0.20 | AQL: exact phrase / synonym coverage via enriched `ro_skills` aliases |
| `evidence_strength` | 0.20 | AQL: graph traversal depth — direct evidence > inferred > weak |
| `seniority_alignment` | 0.10 | AQL: filter on scope_tags (architect, principal, lead vs. individual contributor) |
| `domain_alignment` | 0.05 | AQL: filter on category, domain fields |
| `leadership_alignment` | 0.05 | AQL: filter on leadership_signals in evidence |
| `recency_alignment` | 0.05 | AQL: filter/weight on date_range |

## Gap Classification (7 Types)

| Gap Type | Description | Example |
|----------|-------------|---------|
| `missing_experience` | No evidence exists | "Flink" — never used |
| `weak_wording` | Evidence exists but resume doesn't express it well | Has Kinesis experience but bullet says "worked with data" |
| `missing_explicit_keyword` | Equivalent experience exists, ATS keyword absent | Uses Kinesis, resume doesn't say "Kafka" |
| `insufficient_leadership_signal` | Did the work but doesn't show leadership | Designed architecture but resume says "participated" |
| `seniority_mismatch` | Experience is at wrong level | JD wants principal-level, resume shows senior-level framing |
| `domain_gap` | Wrong industry context | Has streaming experience but not in healthcare |
| `unsupported_claim_risk` | Resume claims something evidence doesn't back | Resume says "led team of 20" but no evidence supports this |

## Generation Pipeline (8 Stages)

```
1. normalize_candidate()     → candidate_profile JSON (from ArangoDB + LinkedIn + resumes)
2. parse_job_requirements()  → atomic requirement objects with types + importance
3. retrieve_evidence()       → for each requirement, graph traversal + embedding similarity
4. score_matches()           → 7-dimension hybrid scoring per requirement
5. classify_gaps()           → 7-type gap classification
6. create_rewrite_targets()  → prioritized section rewrites with evidence refs
7. generate_resume()         → tailored resume from rewrite targets
8. audit_claims()            → flag unsupported claims against evidence
```

## Output Artifacts (Per Job Description)

1. `normalized_candidate_profile.json` — canonical skill inventory + experience units
2. `normalized_job_requirements.json` — atomic typed requirements
3. `matching_results.json` — per-requirement match objects with subscores + evidence
4. `ats_gap_report.md` — human-readable gap analysis with recommendations
5. `resume_rewrite_plan.md` — section-by-section rewrite targets with evidence refs
6. `tailored_resume.md` — generated resume with evidence audit trail
7. `interview_story_bank.json` — STAR stories linked to matched requirements

## New Modules

| Module | Purpose | ~Lines |
|--------|---------|--------|
| `normalizer.py` | Candidate profile + JD normalization (pulls ArangoDB + LinkedIn + resume) | ~350 |
| `jd_parser.py` | Atomic requirement parsing with LLM (must_have/preferred/leadership/domain/education) | ~200 |
| `hybrid_scorer.py` | 7-dimension scoring engine, evidence retrieval, match objects | ~400 |
| `gap_classifier.py` | 7-type gap classification from match results | ~200 |
| `rewrite_planner.py` | Rewrite target generation with evidence refs + risk warnings | ~200 |
| `claim_auditor.py` | Post-generation unsupported claim audit | ~150 |
| `artifact_generator.py` | Produces 7 output files per JD | ~200 |
| `routes/alignment_routes.py` | API routes for the new pipeline | ~250 |

## Modified Modules

| Module | Change |
|--------|--------|
| `resume_scorer.py` | Keep as fast pre-filter; new hybrid scorer for full scoring |
| `nlp_engine.py` | Add embedding helper (batch embed text chunks via `all-MiniLM-L6-v2`) |
| `keyword_grouper.py` | Integrate with normalizer's canonical skill inventory |
| `keyword_equivalency.py` | Becomes user-override layer on auto-normalization |
| `models.py` | Add `ro_job_requirements`, `ro_evidence_chunks` ArangoDB collection init |
| `arango_client.py` | Add evidence retrieval, graph traversal helpers for hybrid scoring |

## Integration with Existing Features

- **Expert Comparison** (`expert_comparison.py`): Uses hybrid scorer for more accurate ATS scores in comparison
- **Experience Chat** (`experience_chat.py`): Evidence from chat sessions feeds into `ro_evidence_chunks`
- **Campaign System**: Knowledge graph context already available, no changes needed
- **Deep Profile** (`deep_profile.py`): Normalized candidate profile replaces empty `ro_deep_profiles`

## Schema Reference

Canonical production schema: `uploads/2026-04-13/resume_optimizer_schema.production.json`

The schema defines strict contracts for `candidate_profile`, `job.normalized_requirements`, `matches`, `gaps`, `rewrite_targets`, and `generation_constraints`. All new modules must produce output conforming to this schema.

## LLM Call Budget (Per Optimization)

| Stage | LLM Calls | Can Cache? |
|-------|-----------|------------|
| Candidate normalization | 1-2 | Yes — once per candidate, reuse across jobs |
| JD requirement parsing | 1 | Yes — once per JD |
| Gap classification | 1 | No — per (candidate, JD) pair |
| Rewrite target generation | 1 | No |
| Resume generation | 1 | No |
| Claim audit | 1 | No |
| **Total per optimization** | **4-6** | 2 cacheable |

## Phasing

### Phase A — Foundation (Highest Value)
- `normalizer.py` — candidate profile normalization from ArangoDB + LinkedIn + resume
- `jd_parser.py` — atomic requirement parsing with LLM
- Enrich `ro_skills` with aliases/synonyms (one-time backfill + ongoing)
- `gap_classifier.py` — 7-type gap classification
- Frontend: requirement-level gap view (replaces flat keyword list)
- **Value:** Users see "weak wording" vs "missing experience" instead of a flat keyword list

### Phase B — Evidence Retrieval + Hybrid Scoring
- Semantic chunking of candidate artifacts into `ro_evidence_chunks`
- `hybrid_scorer.py` — 7-dimension scoring per requirement
- Evidence retrieval via ArangoDB graph traversal + Python embedding similarity
- ArangoSearch view over `ro_evidence_chunks` for BM25 text search
- `routes/alignment_routes.py` — new API routes
- Frontend: per-requirement match detail with evidence refs + subscores
- **Value:** Replaces flat ATS score with evidence-backed per-requirement scoring

### Phase C — Generation Quality
- `rewrite_planner.py` — rewrite targets with evidence refs
- `claim_auditor.py` — unsupported claim audit
- `artifact_generator.py` — 7 output files per JD
- Tailored resume generation from rewrite plan
- Frontend: rewrite review with accept/reject per section
- **Value:** Evidence-backed resume generation with truthfulness audit

## Pre-Execution Requirements

- [ ] User approves phasing (A → B → C or different priority)
- [ ] Model swap to appropriate model for implementation (coding task)
- [ ] Verify ArangoDB `ro_skills` alias enrichment approach
- [ ] Decide: backfill existing 6,130 skills with aliases in Phase A or Phase B
