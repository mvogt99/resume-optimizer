#!/bin/bash
# Post-mine verification script
# Run after mining job completes to capture metrics

set -e

echo "=== Phase 2 Post-Mine Analysis ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# Run the Python post-mine analysis
echo "Running post-mine metrics collection..."
cd /home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer
python3 working-docs/journey-update-2026-04-20/phase_2_post_mine_analysis.py > working-docs/journey-update-2026-04-20/post_mine_metrics.json

echo "✓ Post-mine metrics saved to post_mine_metrics.json"
echo ""

# Display summary
echo "Summary:"
python3 << 'PYSUMMARY'
import json

with open('working-docs/journey-update-2026-04-20/post_mine_metrics.json') as f:
    metrics = json.load(f)

pre = {
    "sources": 12086,
    "events": 10316
}

post = metrics['sources']['total'], metrics['events']['total']

print(f"Pre-mine:  {pre['sources']:6d} sources, {pre['events']:6d} events")
print(f"Post-mine: {metrics['sources']['total']:6d} sources, {metrics['events']['total']:6d} events")
print(f"Increase:  +{metrics['sources']['total']-pre['sources']:6d} sources, +{metrics['events']['total']-pre['events']:6d} events")
print(f"Latest event date: {metrics['latest_event_date']}")
print()
print("Source breakdown (post-mine):")
for src_type, count in sorted(metrics['sources']['breakdown'].items(), key=lambda x: -x[1]):
    print(f"  {src_type:15s}: {count:6d}")
print()
print("Event breakdown (post-mine):")
for cat, count in sorted(metrics['events']['breakdown'].items(), key=lambda x: -x[1]):
    print(f"  {cat:15s}: {count:6d}")
PYSUMMARY

echo ""
echo "✓ Post-mine analysis complete"
