/**
 * AgentRunsPanel — shows recent agent execution history with FTAL + acceptance status.
 * Mounted as the "Runs" tab in AgentDashboard.
 */
import React, { useEffect, useState } from 'react';
import AcceptanceBadge from './AcceptanceBadge';
import api from '../services/api';

const AGENT_LABELS = {
  resume_tailor: 'Resume Tailor',
  cover_letter: 'Cover Letter',
  interview_coach: 'Interview Coach',
  career_advisor: 'Career Advisor',
  job_scout: 'Job Scout',
  app_tracker: 'App Tracker',
};

function ftalColor(gap) {
  if (gap == null) return '#aaa';
  if (gap < 20) return '#2e7d32';
  if (gap < 30) return '#f57c00';
  return '#b71c1c';
}

function formatDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

const STYLES = {
  container: { display: 'flex', flexDirection: 'column', gap: 12 },
  toolbar: { display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  select: { padding: '5px 8px', border: '1px solid #ddd', borderRadius: 6, fontSize: 12 },
  empty: { color: '#888', textAlign: 'center', padding: 32, fontSize: 13 },
  card: {
    border: '1px solid #e0e0e0',
    borderRadius: 8,
    padding: '10px 14px',
    background: '#fff',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  cardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 },
  agentLabel: { fontWeight: 600, fontSize: 13, color: '#333' },
  timestamp: { fontSize: 11, color: '#999' },
  metaRow: { display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  statusChip: (status) => ({
    padding: '1px 7px',
    borderRadius: 10,
    fontSize: 11,
    fontWeight: 600,
    background: status === 'completed' ? '#e8f5e9' : status === 'failed' ? '#fce4ec' : '#fff8e1',
    color: status === 'completed' ? '#2e7d32' : status === 'failed' ? '#b71c1c' : '#e65100',
  }),
  ftalBadge: (gap) => ({
    fontSize: 11,
    fontWeight: 600,
    color: ftalColor(gap),
    padding: '1px 7px',
    borderRadius: 10,
    background: '#f5f5f5',
    border: `1px solid ${ftalColor(gap)}33`,
  }),
  taskDesc: { fontSize: 12, color: '#555', fontStyle: 'italic' },
};

function AgentRunsPanel() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [verifiedOnly, setVerifiedOnly] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.getAgentRuns(50, filter === 'all' ? null : filter)
      .then(d => setRuns(d.runs || []))
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, [filter]);

  const displayed = verifiedOnly
    ? runs.filter(r => r.acceptance_passed != null)
    : runs;

  return (
    <div style={STYLES.container}>
      <div style={STYLES.toolbar}>
        <select
          style={STYLES.select}
          value={filter}
          onChange={e => setFilter(e.target.value)}
        >
          <option value="all">All agents</option>
          {Object.entries(AGENT_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <label style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={verifiedOnly}
            onChange={e => setVerifiedOnly(e.target.checked)}
          />
          Show verified runs only
        </label>
        <span style={{ fontSize: 11, color: '#999', marginLeft: 'auto' }}>
          {displayed.length} run{displayed.length !== 1 ? 's' : ''}
        </span>
      </div>

      {loading && <div style={STYLES.empty}>Loading runs…</div>}

      {!loading && displayed.length === 0 && (
        <div style={STYLES.empty}>No runs found. Complete an agent task to see results here.</div>
      )}

      {!loading && displayed.map(run => {
        const acceptance = run.acceptance_details || null;
        const attempts = run.acceptance_attempts || 1;
        const gap = run.ftal_gap;

        return (
          <div key={run.id} style={STYLES.card}>
            <div style={STYLES.cardHeader}>
              <span style={STYLES.agentLabel}>
                {AGENT_LABELS[run.agent_type] || run.agent_type}
              </span>
              <span style={STYLES.timestamp}>{formatDate(run.created_at)}</span>
            </div>

            {run.task_description && (
              <div style={STYLES.taskDesc}>"{run.task_description}"</div>
            )}

            <div style={STYLES.metaRow}>
              <span style={STYLES.statusChip(run.status)}>{run.status}</span>

              {gap != null && (
                <span style={STYLES.ftalBadge(gap)}>
                  FTAL gap: {gap}
                </span>
              )}

              {acceptance && (
                <AcceptanceBadge
                  acceptance={acceptance}
                  attempts={attempts}
                  compact={false}
                />
              )}

              {run.acceptance_passed == null && (
                <span style={{ fontSize: 11, color: '#bbb' }}>No verification</span>
              )}

              {run.duration_ms > 0 && (
                <span style={{ fontSize: 11, color: '#bbb' }}>
                  {(run.duration_ms / 1000).toFixed(1)}s
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default AgentRunsPanel;
