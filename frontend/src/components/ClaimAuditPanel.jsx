import React from 'react';

const RISK_COLOR = { high: '#f44336', medium: '#ff9800', low: '#4caf50' };
const RISK_BG    = { high: '#fdecea', medium: '#fff3e0', low: '#e8f5e9' };

const CLAIM_TYPE_LABEL = {
  years_experience:  'Years',
  quantified_metric: 'Metric',
  technology_skill:  'Tech Skill',
  role_scope:        'Scope',
  other:             'Other',
};

function RiskBadge({ level }) {
  const lc = (level || 'low').toLowerCase();
  return (
    <span
      className="claim-risk-badge"
      style={{ background: RISK_COLOR[lc] || '#999', color: '#fff' }}
    >
      {lc.toUpperCase()}
    </span>
  );
}

function TypeBadge({ claimType }) {
  return (
    <span className="claim-type-badge">
      {CLAIM_TYPE_LABEL[claimType] || claimType || 'Other'}
    </span>
  );
}

function SupportedIndicator({ isSupported }) {
  return (
    <span
      className="claim-supported-indicator"
      style={{ color: isSupported ? '#4caf50' : '#f44336' }}
    >
      {isSupported ? '\u2713 Supported' : '\u2717 Unsupported'}
    </span>
  );
}

function ClaimItem({ audit }) {
  const risk = (audit.risk_level || 'low').toLowerCase();
  const clampedText = (audit.claim_text || '').length > 120
    ? audit.claim_text.slice(0, 117) + '\u2026'
    : audit.claim_text || '';
  const showRevision = (risk === 'high' || risk === 'medium') && audit.suggested_revision;

  return (
    <div
      className="claim-item"
      style={{
        borderLeft: `3px solid ${RISK_COLOR[risk] || '#999'}`,
        background: (RISK_BG[risk] || '#f5f5f5') + '66',
      }}
    >
      <div className="claim-item-top">
        <RiskBadge level={risk} />
        <TypeBadge claimType={audit.claim_type} />
        <SupportedIndicator isSupported={audit.is_supported} />
      </div>
      <div className="claim-item-text">{clampedText}</div>
      {showRevision && (
        <div className="claim-revision">
          <strong>Suggestion:</strong> {audit.suggested_revision}
        </div>
      )}
    </div>
  );
}

function RiskGroup({ label, items, risk, emptyMessage }) {
  return (
    <div className="claim-risk-group">
      <div
        className="claim-risk-header"
        style={{ color: RISK_COLOR[risk] || '#333' }}
      >
        {label} ({items.length})
      </div>
      {items.length === 0 && emptyMessage ? (
        <div className="claim-risk-empty">{emptyMessage}</div>
      ) : (
        items.map((a, i) => <ClaimItem key={a.audit_id || i} audit={a} />)
      )}
    </div>
  );
}

function ClaimAuditPanel({ audits, summary, loading, error }) {
  if (loading) {
    return (
      <div className="claim-audit-panel claim-audit-panel-loading">
        <span className="analysis-spinner" /> Auditing claims&hellip;
      </div>
    );
  }

  if (error) {
    return (
      <div className="claim-audit-panel claim-audit-panel-error">
        <strong>Audit error:</strong> {error}
      </div>
    );
  }

  if (!audits || audits.length === 0) {
    return (
      <div className="claim-audit-panel claim-audit-panel-empty">
        No claims detected to audit.
      </div>
    );
  }

  const high   = audits.filter(a => (a.risk_level || '').toLowerCase() === 'high');
  const medium = audits.filter(a => (a.risk_level || '').toLowerCase() === 'medium');
  const low    = audits.filter(a => (a.risk_level || '').toLowerCase() === 'low');

  const total        = summary?.total || audits.length;
  const supported    = summary?.supported_count ?? audits.filter(a => a.is_supported).length;
  const unsupported  = summary?.unsupported_count ?? (total - supported);
  const highRiskCt   = summary?.high_risk_count ?? high.length;

  return (
    <div className="claim-audit-panel">
      <div className="claim-audit-summary-bar">
        <span>{total} claims audited</span>
        <span style={{ color: '#4caf50' }}>&bull; {supported} supported</span>
        <span style={{ color: '#f44336' }}>&bull; {highRiskCt} high risk</span>
        {unsupported > 0 && (
          <span style={{ color: '#ff9800' }}>&bull; {unsupported} unsupported</span>
        )}
      </div>

      <RiskGroup
        label="High Risk"
        items={high}
        risk="high"
        emptyMessage={'\u2713 No high-risk claims detected'}
      />
      <RiskGroup label="Medium Risk" items={medium} risk="medium" />
      <RiskGroup label="Low Risk"    items={low}    risk="low"    />
    </div>
  );
}

export default ClaimAuditPanel;
