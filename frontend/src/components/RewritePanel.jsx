import React, { useState } from 'react';
import api from '../services/api';

const SEV_COLOR = { high: '#f44336', medium: '#ff9800', low: '#4caf50' };

const TYPE_LABEL = {
  missing_experience:             'Missing Experience',
  weak_wording:                   'Weak Wording',
  missing_explicit_keyword:       'Missing Keyword',
  insufficient_leadership_signal: 'Leadership Gap',
  seniority_mismatch:             'Seniority Mismatch',
  domain_gap:                     'Domain Gap',
  unsupported_claim_risk:         'Unsupported Claim',
};

function SevBadge({ severity }) {
  const lc = (severity || 'low').toLowerCase();
  return (
    <span
      className="rewrite-sev-badge"
      style={{ background: SEV_COLOR[lc] || '#999', color: '#fff' }}
    >
      {lc.toUpperCase()}
    </span>
  );
}

function RewriteTargetCard({ gap, index, resumeId, jobDescText, onApplied }) {
  const [applying, setApplying]   = useState(false);
  const [result, setResult]       = useState(null);
  const [applyErr, setApplyErr]   = useState('');
  const [copied, setCopied]       = useState(false);

  const handleApply = async () => {
    setApplying(true);
    setApplyErr('');
    setResult(null);
    try {
      // Build a synthetic rewrite target from the gap object.
      // rewrite_template is required by the backend — use recommended_action as template.
      const action = gap.recommended_action || gap.description || gap.gap_type || 'Improve this section';
      const syntheticTarget = {
        target_id:        gap.gap_id || `gap_${index}`,
        gap_id:           gap.gap_id,
        gap_type:         gap.gap_type,
        suggested_action: action,
        rewrite_template: action,
        evidence_anchor:  gap.keyword || gap.skill || '',
        severity:         gap.severity || 'low',
        priority:         index + 1,
      };
      const data = await api.applyRewrite(resumeId, syntheticTarget, jobDescText);
      setResult(data);
      // Notify parent so gap analysis score can be re-run
      if (onApplied) onApplied(data);
    } catch (err) {
      setApplyErr(err.response?.data?.error || err.message || 'Apply failed.');
    } finally {
      setApplying(false);
    }
  };

  const handleCopy = () => {
    if (!result?.suggested_text) return;
    navigator.clipboard.writeText(result.suggested_text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const sev = (gap.severity || 'low').toLowerCase();

  return (
    <div
      className="rewrite-target-card"
      style={{ borderLeft: `3px solid ${SEV_COLOR[sev] || '#999'}` }}
    >
      <div className="rewrite-card-top">
        <span className="rewrite-priority-badge">#{index + 1}</span>
        <SevBadge severity={sev} />
        <span className="rewrite-type-label">
          {TYPE_LABEL[gap.gap_type] || gap.gap_type || ''}
        </span>
      </div>

      <div className="rewrite-action">
        {gap.recommended_action || gap.description || 'No action specified.'}
      </div>

      {!result && (
        <button
          className="btn-apply-rewrite"
          onClick={handleApply}
          disabled={applying}
        >
          {applying ? 'Applying\u2026' : 'Apply Suggestion'}
        </button>
      )}

      {applyErr && (
        <div className="rewrite-apply-error">{applyErr}</div>
      )}

      {result && (
        <div className="rewrite-diff-box">
          {result.original_snippet && (
            <div className="rewrite-diff-before">
              <strong>Before:</strong>
              <pre>{result.original_snippet}</pre>
            </div>
          )}
          {result.suggested_text && (
            <div className="rewrite-diff-after">
              <strong>After:</strong>
              <pre>{result.suggested_text}</pre>
              <button className="btn-copy-rewrite" onClick={handleCopy}>
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>
          )}
          {result.diff_hint && (
            <div className="rewrite-diff-hint">{result.diff_hint}</div>
          )}
        </div>
      )}
    </div>
  );
}

function RewritePanel({ gaps, resumeId, jobDescText, onApplied }) {
  if (!gaps || gaps.length === 0) {
    return (
      <div className="rewrite-panel rewrite-panel-empty">
        No rewrite targets \u2014 alignment looks strong!
      </div>
    );
  }

  // Sort by severity: high first, then medium, then low; take top 5
  const SEV_ORDER = { high: 0, medium: 1, low: 2 };
  const sorted = [...gaps]
    .sort((a, b) =>
      (SEV_ORDER[(a.severity || 'low').toLowerCase()] || 2) -
      (SEV_ORDER[(b.severity || 'low').toLowerCase()] || 2)
    )
    .slice(0, 5);

  return (
    <div className="rewrite-panel">
      <div className="rewrite-panel-header">
        Rewrite Suggestions ({Math.min(gaps.length, 5)} of {gaps.length} shown)
      </div>
      {sorted.map((gap, i) => (
        <RewriteTargetCard
          key={gap.gap_id || i}
          gap={gap}
          index={i}
          resumeId={resumeId}
          jobDescText={jobDescText}
          onApplied={onApplied}
        />
      ))}
    </div>
  );
}

export default RewritePanel;
