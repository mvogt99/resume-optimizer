import React, { useState, useEffect } from 'react';
import JobScout from './JobScout';
import ApplicationPipeline from './ApplicationPipeline';
import ResumeTailor from './ResumeTailor';
import CoverLetter from './CoverLetter';
import InterviewCoach from './InterviewCoach';
import CareerAdvisor from './CareerAdvisor';
import AgentRunsPanel from './AgentRunsPanel';
import api from '../services/api';
import '../styles/Agents.css';

const TABS = [
  { id: 'scout', label: 'Job Scout' },
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'tailor', label: 'Resume Tailor' },
  { id: 'cover', label: 'Cover Letter' },
  { id: 'coach', label: 'Interview Coach' },
  { id: 'advisor', label: 'Career Advisor' },
  { id: 'runs', label: '✓ Verification History' },
];

function AgentDashboard({ onDismissReminder }) {
  const [subTab, setSubTab] = useState('scout');
  const [agentStatus, setAgentStatus] = useState(null);
  const [selectedPostingId, setSelectedPostingId] = useState('');
  const [postings, setPostings] = useState([]);
  const [coachPostingId, setCoachPostingId] = useState('');
  const [verificationSummary, setVerificationSummary] = useState(null);

  useEffect(() => {
    api.getAgentStatus()
      .then(setAgentStatus)
      .catch(() => setAgentStatus(null));
    // Load postings for tailor/cover letter context
    api.scoutListPostings(null, 0, 50)
      .then(d => setPostings(d.postings || []))
      .catch(() => {});
    // Load recent runs for the verification summary badge
    api.getAgentRuns(20, null)
      .then(d => {
        const runs = d.runs || [];
        const verified = runs.filter(r => r.acceptance_passed != null);
        const passed = verified.filter(r => r.acceptance_passed === 1).length;
        if (verified.length > 0) {
          setVerificationSummary({ total: verified.length, passed });
        }
      })
      .catch(() => {});
  }, []);

  const modelReady = agentStatus?.model?.current_swap_id;

  const needsPosting = subTab === 'tailor' || subTab === 'cover';

  return (
    <div className="agents-dashboard">
      <div className="agents-header">
        <h2>AI Career Agents</h2>
        <div className="agent-status-bar">
          <span className={`agent-status-dot ${modelReady ? '' : 'offline'}`} />
          <span>{modelReady ? `RTX 5090: ${agentStatus.model.current_swap_id}` : 'Connecting...'}</span>
          <span style={{ color: '#4caf50', fontWeight: 600 }}>{agentStatus?.cost || '$0.00'}</span>
          <span style={{ fontSize: 12, color: '#888' }}>
            {agentStatus?.agents?.length || 0} agents
          </span>
          {verificationSummary && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                padding: '2px 8px',
                borderRadius: 10,
                background: verificationSummary.passed === verificationSummary.total ? '#e8f5e9' : '#fff8e1',
                color: verificationSummary.passed === verificationSummary.total ? '#2e7d32' : '#e65100',
                cursor: 'pointer',
              }}
              title="AI output verification rate — click Verification History tab for details"
              onClick={() => setSubTab('runs')}
            >
              ✓ {verificationSummary.passed}/{verificationSummary.total} verified
            </span>
          )}
        </div>
      </div>

      <div className="agents-sub-nav" style={{ overflowX: 'auto' }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={subTab === tab.id ? 'active' : ''}
            onClick={() => setSubTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Posting selector for tailor/cover letter tabs */}
      {needsPosting && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0' }}>
          <label style={{ fontSize: 13, color: '#666', fontWeight: 500 }}>Job Posting:</label>
          <select
            value={selectedPostingId}
            onChange={e => setSelectedPostingId(e.target.value)}
            style={{ padding: '6px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, minWidth: 300 }}
          >
            <option value="">Select a posting...</option>
            {postings.map(p => (
              <option key={p.id} value={p.id}>
                {p.title} @ {p.company} (Score: {Math.round(p.match_score || 0)})
              </option>
            ))}
          </select>
        </div>
      )}

      {subTab === 'scout' && <JobScout />}
      {subTab === 'pipeline' && (
        <ApplicationPipeline
          onNavigateToCoach={(postingId) => {
            setCoachPostingId(postingId);
            setSubTab('coach');
          }}
          onDismissReminder={onDismissReminder}
        />
      )}
      {subTab === 'tailor' && <ResumeTailor postingId={selectedPostingId} />}
      {subTab === 'cover' && <CoverLetter postingId={selectedPostingId} />}
      {subTab === 'coach' && <InterviewCoach initialPostingId={coachPostingId} />}
      {subTab === 'advisor' && <CareerAdvisor />}
      {subTab === 'runs' && <AgentRunsPanel />}
    </div>
  );
}

export default AgentDashboard;
