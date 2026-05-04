#!/usr/bin/env bash
# run_regression_10x.sh — Run full backend test suite 10 consecutive times
# Captures per-run results and generates markdown report.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORT="$SCRIPT_DIR/roadmap/REGRESSION_V2_10X_REPORT.md"
BACKEND="$SCRIPT_DIR/backend"
RUNS=10

cd "$SCRIPT_DIR"
source .venv/bin/activate
cd "$BACKEND"

echo "================================================================"
echo "  Full Suite Regression — $RUNS consecutive runs"
echo "  Test dir: backend/tests/"
echo "================================================================"
echo ""

declare -a RUN_PASSED RUN_FAILED RUN_ERRORS RUN_TIME RUN_STATUS

for i in $(seq 1 $RUNS); do
    echo -n "Run $i/$RUNS ... "
    START_NS=$(date +%s%N)

    OUTPUT=$(python -m pytest tests/ -v --tb=line 2>&1) || true

    END_NS=$(date +%s%N)
    ELAPSED_MS=$(( (END_NS - START_NS) / 1000000 ))
    ELAPSED_S=$(printf "%.1f" "$(echo "scale=1; $ELAPSED_MS / 1000" | bc)")

    PASSED=$(echo "$OUTPUT" | grep -oP '\d+(?= passed)' | tail -1 || echo "0")
    FAILED=$(echo "$OUTPUT" | grep -oP '\d+(?= failed)' | tail -1 || echo "0")
    ERRORS=$(echo "$OUTPUT" | grep -oP '\d+(?= error)' | tail -1 || echo "0")

    RUN_PASSED[$i]=$PASSED
    RUN_FAILED[$i]=${FAILED:-0}
    RUN_ERRORS[$i]=${ERRORS:-0}
    RUN_TIME[$i]=$ELAPSED_S

    if [[ "${FAILED:-0}" == "0" && "${ERRORS:-0}" == "0" ]]; then
        RUN_STATUS[$i]="PASS"
        echo "PASS ($PASSED passed, ${ELAPSED_S}s)"
    else
        RUN_STATUS[$i]="FAIL"
        echo "FAIL ($PASSED passed, ${FAILED:-0} failed, ${ERRORS:-0} errors, ${ELAPSED_S}s)"
    fi
done

# Compute aggregate stats
TOTAL_PASSED=0
TOTAL_FAILED=0
MIN_TIME="999999"
MAX_TIME="0"
SUM_TIME="0"
PASS_RUNS=0

for i in $(seq 1 $RUNS); do
    TOTAL_PASSED=$((TOTAL_PASSED + ${RUN_PASSED[$i]}))
    TOTAL_FAILED=$((TOTAL_FAILED + ${RUN_FAILED[$i]:-0} + ${RUN_ERRORS[$i]:-0}))
    T=${RUN_TIME[$i]}
    if (( $(echo "$T < $MIN_TIME" | bc -l) )); then MIN_TIME=$T; fi
    if (( $(echo "$T > $MAX_TIME" | bc -l) )); then MAX_TIME=$T; fi
    SUM_TIME=$(echo "$SUM_TIME + $T" | bc)
    if [[ "${RUN_STATUS[$i]}" == "PASS" ]]; then PASS_RUNS=$((PASS_RUNS + 1)); fi
done

GRAND_TOTAL=$((TOTAL_PASSED + TOTAL_FAILED))
if [[ "$GRAND_TOTAL" -gt 0 ]]; then
    PASS_RATE=$(printf "%.1f" "$(echo "scale=1; $TOTAL_PASSED * 100 / $GRAND_TOTAL" | bc)")
else
    PASS_RATE="0.0"
fi
AVG_TIME=$(printf "%.1f" "$(echo "scale=1; $SUM_TIME / $RUNS" | bc)")

# Write report
mkdir -p "$(dirname "$REPORT")"
{
    echo "# Full Suite Regression — 10x Stability Report"
    echo ""
    echo "**Date:** $(date -u '+%Y-%m-%d %H:%M UTC')"
    echo "**Suite:** \`backend/tests/\` (all test files)"
    echo "**Python:** $(python --version 2>&1)"
    echo "**Iterations:** $RUNS"
    echo ""
    echo "## Per-Run Results"
    echo ""
    echo "| Run | Status | Passed | Failed | Errors | Time |"
    echo "|-----|--------|--------|--------|--------|------|"
    for i in $(seq 1 $RUNS); do
        echo "| $i | ${RUN_STATUS[$i]} | ${RUN_PASSED[$i]} | ${RUN_FAILED[$i]:-0} | ${RUN_ERRORS[$i]:-0} | ${RUN_TIME[$i]}s |"
    done
    echo ""
    echo "## Aggregate Statistics"
    echo ""
    echo "| Metric | Value |"
    echo "|--------|-------|"
    echo "| Total test executions | $GRAND_TOTAL |"
    echo "| Total passed | $TOTAL_PASSED |"
    echo "| Total failed | $TOTAL_FAILED |"
    echo "| **Pass rate** | **${PASS_RATE}%** |"
    echo "| Run pass rate | ${PASS_RUNS}/${RUNS} runs |"
    echo "| Min time | ${MIN_TIME}s |"
    echo "| Max time | ${MAX_TIME}s |"
    echo "| Avg time | ${AVG_TIME}s |"
    echo ""
    echo "## Flaky Test Analysis"
    echo ""
    if [[ "$PASS_RUNS" -eq "$RUNS" ]]; then
        echo "**No flaky tests detected.** All $RUNS runs passed with zero failures."
    else
        echo "Some runs had failures. Review test output logs for details."
    fi
    echo ""
    echo "## Notes"
    echo ""
    echo "- All tests use fresh SQLite databases (temp files per test)"
    echo "- No external services required (no LLM, no Qdrant, no ArangoDB)"
    echo "- Agent singleton resets prevent cross-test state leakage"
    echo "- NLP scoring is deterministic (spaCy + sentence-transformers)"
} > "$REPORT"

echo ""
echo "================================================================"
echo "  Report: $REPORT"
echo "  Pass rate: ${PASS_RATE}% ($TOTAL_PASSED / $GRAND_TOTAL)"
echo "  Run pass rate: ${PASS_RUNS}/${RUNS}"
echo "  Avg time: ${AVG_TIME}s per run"
echo "================================================================"
