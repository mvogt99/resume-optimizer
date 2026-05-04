import React from 'react';

const SEV_COLOR = { high: '#f44336', medium: '#ff9800', low: '#4caf50' };
const SEV_BG   = { high: '#fdecea', medium: '#fff3e0', low: '#e8f5e9' };

const MATCH_COLOR = {
  direct:               '#4caf50',
  direct_plus_inferred: '#8bc34a',
  partial:              '#ff9800',
  weak:                 '#ff5722',
  none:                 '#f44336',
};

const TYPE_LABEL = {
  missing_experience:            'Missing Experience',
  weak_wording:                  'Weak Wording',
  missing_explicit_keyword:      'Missing Keyword',
  insufficient_leadership_signal:'Leadership Gap',
  seniority_mismatch:            'Seniority Mismatch',
  domain_gap:                    'Domain Gap',
  unsupported_claim_risk:        'Unsupported Claim',
};

function MatchDistribution({ distribution }) {
  if (!distribution) return null;
  const entries = Object.entries(distribution).filter(([, count]) => count > 0);
  if (!entries.length) return null;
  return (
    <div className="gap-match-dist">
      {entries.map(([type, count]) => (
        <span
          key={type}
          className="gap-match-badge"
          style={{
            background: (MATCH_COLOR[type] || '#999') + '22',
            color: MATCH_COLOR[type] || '#999',
            border: `1px solid ${MATCH_COLOR[type] || '#999'}`,
          }}
        >
          {type.replace(/_/g, '\u00a0')} &times; {count}
        </span>
      ))}
    </div>
  );
}

function GapItem({ gap }) {
  const sev = gap.severity || 'low';
  return (
    <div
      className="gap-item"
      style={{
        borderLeft: `3px solid ${SEV_COLOR[sev]}`,
        background: SEV_BG[sev] + '55',
      }}
    >
      <div className="gap-item-top">
        <span
          className="gap-sev-badge"
          style={{ background: SEV_COLOR[sev] }}
        >
          {sev.toUpperCase()}
        </span>
        <span className="gap-type-badge">
          {TYPE_LABEL[gap.gap_type] || gap.gap_type}
        </span>
      </div>
      <div className="gap-item-desc">{gap.description}</div>
      {gap.recommended_action && (
        <div className="gap-item-action">
          <strong>Action:</strong> {gap.recommended_action}
        </div>
      )}
    </div>
  );
}

function RequirementScores({ scores, requirements }) {
  if (!scores || scores.length === 0) return null;
  const reqMap = {};
  (requirements || []).forEach(r => { reqMap[r.requirement_id] = r; });

  const sorted = [...scores]
    .sort((a, b) => (b.composite_score || 0) - (a.composite_score || 0))
    .slice(0, 12);
  return (
    <div className="gap-scores-section">
      <div className="gap-scores-title">Requirement Match Scores</div>
      <div className="gap-scores-list">
        {sorted.map((s, i) => {
          const pct = Math.round((s.composite_score || 0) * 100);
          const color = MATCH_COLOR[s.match_type] || '#999';
          const req = reqMap[s.requirement_id];
          const label = req
            ? (req.text || '').slice(0, 60) + ((req.text || '').length > 60 ? '…' : '')
            : s.requirement_id;
          return (
            <div key={s.requirement_id || i} className="gap-score-row">
              <div className="gap-score-label-text" title={req?.text || s.requirement_id}>
                {label}
              </div>
              <div className="gap-score-bar-track">
                <div
                  className="gap-score-bar-fill"
                  style={{ width: `${pct}%`, background: color }}
                />
              </div>
              <span className="gap-score-pct">{pct}%</span>
              <span className="gap-score-type" style={{ color }}>
                {(s.match_type || '—').replace(/_/g, ' ')}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GapClassificationPanel({ gaps, scores, summary, requirements }) {
  if (!gaps || gaps.length === 0) {
    return (
      <div className="gap-panel gap-panel-empty">
        <span className="gap-empty-icon">&#10003;</span>
        <p>No significant gaps detected — strong alignment with this role.</p>
      </div>
    );
  }

  const high   = gaps.filter(g => g.severity === 'high');
  const medium = gaps.filter(g => g.severity === 'medium');
  const low    = gaps.filter(g => g.severity === 'low');

  const overallScore = summary?.overall_score != null
    ? Math.round(summary.overall_score * 100)
    : null;

  const scoreColor = overallScore == null ? '#666'
    : overallScore >= 65 ? '#4caf50'
    : overallScore >= 40 ? '#ff9800'
    : '#f44336';

  return (
    <div className="gap-panel">
      {overallScore != null && (
        <div className="gap-panel-header">
          <div className="gap-overall-score">
            <span className="gap-score-num" style={{ color: scoreColor }}>
              {overallScore}%
            </span>
            <span className="gap-score-label">Alignment Score</span>
          </div>
          <MatchDistribution distribution={summary?.match_distribution} />
        </div>
      )}

      {[
        { label: 'High Priority', items: high,   sev: 'high'   },
        { label: 'Medium Priority', items: medium, sev: 'medium' },
        { label: 'Lower Priority', items: low,   sev: 'low'    },
      ].map(({ label, items, sev }) =>
        items.length > 0 ? (
          <div key={sev} className="gap-severity-group">
            <div
              className="gap-severity-header"
              style={{ color: SEV_COLOR[sev] }}
            >
              {label} ({items.length})
            </div>
            {items.map((gap, i) => (
              <GapItem key={gap.gap_id || i} gap={gap} />
            ))}
          </div>
        ) : null
      )}

      <RequirementScores scores={scores} requirements={requirements} />
    </div>
  );
}

export default GapClassificationPanel;
