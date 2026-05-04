# Full Suite Regression — 10x Stability Report

**Date:** 2026-03-06 17:16 UTC
**Suite:** `backend/tests/` (all test files)
**Python:** Python 3.13.12
**Iterations:** 10

## Per-Run Results

| Run | Status | Passed | Failed | Errors | Time |
|-----|--------|--------|--------|--------|------|
| 1 | PASS | 260 | 0 | 0 | 197.8s |
| 2 | PASS | 260 | 0 | 0 | 223.9s |
| 3 | PASS | 260 | 0 | 0 | 196.3s |
| 4 | PASS | 260 | 0 | 0 | 188.2s |
| 5 | PASS | 260 | 0 | 0 | 202.0s |
| 6 | PASS | 260 | 0 | 0 | 226.3s |
| 7 | PASS | 260 | 0 | 0 | 267.3s |
| 8 | PASS | 260 | 0 | 0 | 186.0s |
| 9 | PASS | 260 | 0 | 0 | 263.8s |
| 10 | PASS | 260 | 0 | 0 | 237.5s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Total test executions | 2600 |
| Total passed | 2600 |
| Total failed | 0 |
| **Pass rate** | **100.0%** |
| Run pass rate | 10/10 runs |
| Min time | 186.0s |
| Max time | 267.3s |
| Avg time | 218.9s |

## Flaky Test Analysis

**No flaky tests detected.** All 10 runs passed with zero failures.

## Notes

- All tests use fresh SQLite databases (temp files per test)
- No external services required (no LLM, no Qdrant, no ArangoDB)
- Agent singleton resets prevent cross-test state leakage
- NLP scoring is deterministic (spaCy + sentence-transformers)
