/**
 * AcceptanceBadge — shows AI verification status inline.
 *
 * Props:
 *   acceptance: { passed, criteria_total, criteria_passed, failures, a_score_penalty }
 *   attempts:   number of attempts made (1 = first try, 2 = retried)
 *   compact:    boolean — if true renders just the icon+label, no failure list
 */
import React, { useState } from 'react';

const STYLES = {
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    padding: '2px 8px',
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 600,
    cursor: 'pointer',
    userSelect: 'none',
    border: '1px solid transparent',
  },
  pass: { background: '#e8f5e9', color: '#2e7d32', borderColor: '#a5d6a7' },
  warn: { background: '#fff8e1', color: '#e65100', borderColor: '#ffe082' },
  fail: { background: '#fce4ec', color: '#b71c1c', borderColor: '#ef9a9a' },
  unknown: { background: '#f5f5f5', color: '#757575', borderColor: '#e0e0e0' },
  panel: {
    marginTop: 6,
    padding: '8px 10px',
    background: '#fff8f8',
    border: '1px solid #f8bbd0',
    borderRadius: 6,
    fontSize: 11,
    lineHeight: 1.5,
  },
  failureRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    marginTop: 4,
  },
  failureName: { fontWeight: 600, color: '#c62828' },
  failureHint: { color: '#555', paddingLeft: 10 },
};

function AcceptanceBadge({ acceptance, attempts = 1, compact = false }) {
  const [expanded, setExpanded] = useState(false);

  if (!acceptance) {
    return (
      <span style={{ ...STYLES.badge, ...STYLES.unknown }}>
        ⬜ Not verified
      </span>
    );
  }

  const { passed, criteria_total, criteria_passed, failures = [], a_score_penalty = 0 } = acceptance;
  const wasRetried = attempts > 1;

  let variant, icon, label;
  if (passed && !wasRetried) {
    variant = STYLES.pass;
    icon = '✓';
    label = `Verified (${criteria_passed}/${criteria_total})`;
  } else if (passed && wasRetried) {
    variant = STYLES.warn;
    icon = '⟳';
    label = `Verified on retry ${attempts} (${criteria_passed}/${criteria_total})`;
  } else {
    variant = STYLES.fail;
    icon = '✗';
    label = `${failures.length} check${failures.length !== 1 ? 's' : ''} failed`;
  }

  const hasPenalty = a_score_penalty > 0;

  return (
    <span>
      <span
        style={{ ...STYLES.badge, ...variant }}
        title={passed ? 'AI output verified' : 'Click to see verification failures'}
        onClick={() => !compact && failures.length > 0 && setExpanded(e => !e)}
      >
        {icon} {label}
        {hasPenalty && <span style={{ opacity: 0.75 }}> (-{a_score_penalty})</span>}
      </span>

      {!compact && expanded && failures.length > 0 && (
        <div style={STYLES.panel}>
          <strong style={{ fontSize: 11 }}>Verification failures:</strong>
          <div style={STYLES.failureRow}>
            {failures.map((f, i) => (
              <div key={i}>
                <div style={STYLES.failureName}>{f.name}</div>
                <div style={STYLES.failureHint}>{f.hint}</div>
              </div>
            ))}
          </div>
          {hasPenalty && (
            <div style={{ marginTop: 6, color: '#e65100', fontSize: 10 }}>
              Quality score penalised by {a_score_penalty} points.
            </div>
          )}
        </div>
      )}
    </span>
  );
}

export default AcceptanceBadge;
