# E2E Regression — 10x Stability Report

**Date:** 2026-03-05 23:29
**Test file:** `backend/tests/test_regression_e2e.py`
**Python:** Python 3.13.12
**Runs:** 10 consecutive

## Per-Run Results

| Run | Status | Passed | Failed | Total | Time (s) |
|-----|--------|--------|--------|-------|----------|
| 1 | + PASS | 37 | 0 | 37 | 112.8 |
| 2 | + PASS | 37 | 0 | 37 | 95.0 |
| 3 | + PASS | 37 | 0 | 37 | 102.6 |
| 4 | + PASS | 37 | 0 | 37 | 174.2 |
| 5 | + PASS | 37 | 0 | 37 | 134.9 |
| 6 | + PASS | 37 | 0 | 37 | 96.6 |
| 7 | + PASS | 37 | 0 | 37 | 96.0 |
| 8 | + PASS | 37 | 0 | 37 | 134.1 |
| 9 | + PASS | 37 | 0 | 37 | 97.3 |
| 10 | + PASS | 37 | 0 | 37 | 99.5 |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Total tests executed | 370 |
| Total passed | 370 |
| Total failed | 0 |
| **Pass rate** | **100.0%** |
| Min time | 95.0s |
| Max time | 174.2s |
| Avg time | 114.3s |

## Flaky Test Analysis

**No flaky tests detected.** All tests that passed in any run passed in every run.

## Score Consistency

The NLP scoring pipeline (spaCy + NLTK) is deterministic — same input always
produces the same score. With `en_core_web_md` (real word vectors), semantic
similarity is based on actual word meaning, not just context-sensitive tensors.

**Calibrated scores (post-fix):**
- Matched pair (Enterprise Architect vs Solutions Architect): **69** (was ~55 pre-calibration)
- Mismatched pair (Chef vs ML Engineer): **3** (was ~33 pre-calibration)
- Score discrimination: **66-point gap** (was 22-point gap)

**Implication:** Scores are reproducible, deterministic, and now well-calibrated.
No randomness in the pipeline (no sampling, no temperature, no LLM involvement).

## Notes

- All tests use fresh SQLite databases (temp files per test)
- No external services required (no LLM, no Qdrant, no ArangoDB)
- Agent singleton resets prevent cross-test state leakage
- Campaign tests drive the full 7-stage interview state machine
- spaCy `en_core_web_md` provides real word vectors for semantic similarity
- Floor correction expands usable score range from 25-80 to 0-100
