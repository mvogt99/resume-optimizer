import React, { useState, useEffect, useCallback, useRef } from 'react';
import api from '../services/api';
import JourneyTimeline from './JourneyTimeline';
import JourneySkills from './JourneySkills';
import JourneyNarratives from './JourneyNarratives';
import '../styles/JourneyMiner.css';

function JourneyMiner() {
  const [subView, setSubView] = useState('timeline');
  const [mining, setMining] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState(null);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');
  const [miningHistory, setMiningHistory] = useState([]);

  // Review session state
  const [reviewSessionId, setReviewSessionId] = useState(null);
  const [reviewMessages, setReviewMessages] = useState([]);
  const [reviewInput, setReviewInput] = useState('');
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewComplete, setReviewComplete] = useState(false);
  const reviewEndRef = useRef(null);

  // Update criteria state
  const [showCriteria, setShowCriteria] = useState(false);
  const [criteria, setCriteria] = useState({
    since_date: '',
    until_date: '',
    project_scope: ['all'],
    sources: ['files', 'git', 'arango', 'enrichment'],
  });

  const loadStats = useCallback(async () => {
    try {
      const [timelineData, skillsData, achieveData] = await Promise.all([
        api.getJourneyTimeline(1, 1),
        api.getJourneySkills(),
        api.getJourneyAchievements(),
      ]);
      setStats({
        events: timelineData.total || 0,
        skills: (skillsData.skills || []).length,
        achievements: (achieveData.achievements || []).length,
      });
    } catch {
      // Stats may not exist yet
    }
  }, []);

  const loadMiningHistory = useCallback(async () => {
    try {
      const data = await api.getMiningHistory(10);
      setMiningHistory(data.runs || []);
    } catch {
      // History may not exist yet
    }
  }, []);

  useEffect(() => {
    loadStats();
    loadMiningHistory();
  }, [loadStats, loadMiningHistory]);

  // Poll mining job
  useEffect(() => {
    if (!jobId) return;

    const interval = setInterval(async () => {
      try {
        const job = await api.getJobStatus(jobId);
        setProgress(job.progress_json || {});
        if (job.status === 'completed' || job.status === 'failed') {
          setMining(false);
          setJobId(null);
          setProgress(null);
          if (job.status === 'failed') {
            setError(`Mining failed: ${job.error_message}`);
          }
          loadStats();
          loadMiningHistory();
        }
      } catch {
        // ignore
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [jobId, loadStats, loadMiningHistory]);

  const startMining = async (overrideCriteria) => {
    setMining(true);
    setError('');
    try {
      const opts = overrideCriteria || criteria;
      const data = await api.startJourneyMining(opts);
      setJobId(data.job_id);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to start mining');
      setMining(false);
    }
  };

  const toggleScope = (val) => {
    setCriteria(prev => {
      if (val === 'all') return { ...prev, project_scope: ['all'] };
      const scopes = prev.project_scope.filter(s => s !== 'all');
      return {
        ...prev,
        project_scope: scopes.includes(val)
          ? scopes.filter(s => s !== val) || ['all']
          : [...scopes, val],
      };
    });
  };

  const toggleSource = (val) => {
    setCriteria(prev => {
      const sources = prev.sources.includes(val)
        ? prev.sources.filter(s => s !== val)
        : [...prev.sources, val];
      return { ...prev, sources: sources.length ? sources : ['files'] };
    });
  };

  const clearAndRemine = async () => {
    if (!window.confirm('Clear all mined data and start fresh? Narratives are preserved.')) return;
    setError('');
    try {
      await api.resetJourneySources();
      setStats(null);
      startMining();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to clear journey data');
    }
  };

  // Scroll review messages
  useEffect(() => {
    if (reviewEndRef.current) {
      reviewEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [reviewMessages]);

  const startReview = async () => {
    setReviewLoading(true);
    setReviewComplete(false);
    setReviewMessages([]);
    try {
      const data = await api.startJourneyReview('timeline');
      setReviewSessionId(data.session_id);
      setReviewMessages([{ role: 'assistant', content: data.message }]);
    } catch (err) {
      setError('Failed to start review');
    } finally {
      setReviewLoading(false);
    }
  };

  const sendReviewMessage = async () => {
    if (!reviewInput.trim() || reviewLoading) return;
    const msg = reviewInput.trim();
    setReviewInput('');
    setReviewMessages(prev => [...prev, { role: 'user', content: msg }]);
    setReviewLoading(true);
    try {
      const data = await api.sendJourneyReviewMessage(reviewSessionId, msg);
      setReviewMessages(prev => [...prev, { role: 'assistant', content: data.message }]);
      if (data.is_complete) setReviewComplete(true);
    } catch (err) {
      setError('Failed to send review message');
    } finally {
      setReviewLoading(false);
    }
  };

  const applyReviewChanges = async () => {
    setReviewLoading(true);
    try {
      await api.applyJourneyReviewChanges(reviewSessionId);
      setReviewSessionId(null);
      setReviewMessages([]);
      setReviewComplete(false);
      loadStats();
    } catch (err) {
      setError('Failed to apply review changes');
    } finally {
      setReviewLoading(false);
    }
  };

  const phases = [
    { key: 'harvesting_files', label: 'Local Files', cssClass: 'files' },
    { key: 'scanning_qdrant', label: 'Qdrant', cssClass: 'qdrant' },
    { key: 'scanning_arango', label: 'ArangoDB', cssClass: 'arango' },
    { key: 'parsing_git', label: 'Git History', cssClass: 'git' },
    { key: 'deduplicating', label: 'Dedup', cssClass: 'files' },
    { key: 'building_timeline', label: 'Timeline', cssClass: 'qdrant' },
    { key: 'generating_narratives', label: 'Narratives', cssClass: 'arango' },
  ];

  const currentPhaseIndex = progress
    ? phases.findIndex(p => p.key === progress.phase)
    : -1;

  return (
    <div className="journey-container">
      <div className="journey-header">
        <h2>AI Journey Knowledge Mining</h2>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            className="journey-btn journey-btn-secondary"
            onClick={() => setShowCriteria(v => !v)}
            disabled={mining}
            title="Set date range, project scope, and source filters"
          >
            {showCriteria ? '▲ Hide Criteria' : '⚙ Update Criteria'}
          </button>
          <button
            className="journey-btn-mine"
            onClick={() => startMining()}
            disabled={mining}
          >
            {mining ? 'Mining...' : 'Start Mining'}
          </button>
          {stats && stats.events > 0 && !reviewSessionId && (
            <>
              <button
                className="journey-btn journey-btn-secondary"
                onClick={startReview}
                disabled={reviewLoading}
              >
                Review Findings
              </button>
              <button
                className="journey-btn journey-btn-secondary"
                onClick={clearAndRemine}
                disabled={mining}
                title="Clear all mined data and re-mine from scratch. Narratives are preserved."
              >
                Clear &amp; Re-mine
              </button>
            </>
          )}
        </div>
      </div>

      {/* Update Criteria Panel */}
      {showCriteria && (
        <div className="journey-criteria-panel">
          <h3>Mining Criteria</h3>
          <div className="journey-criteria-row">
            <label>Date Range</label>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="date"
                value={criteria.since_date}
                onChange={e => setCriteria(p => ({ ...p, since_date: e.target.value }))}
                className="journey-criteria-date"
                placeholder="Since"
              />
              <span style={{ color: '#999' }}>→</span>
              <input
                type="date"
                value={criteria.until_date}
                onChange={e => setCriteria(p => ({ ...p, until_date: e.target.value }))}
                className="journey-criteria-date"
                placeholder="Until"
              />
              {(criteria.since_date || criteria.until_date) && (
                <button
                  className="journey-criteria-clear"
                  onClick={() => setCriteria(p => ({ ...p, since_date: '', until_date: '' }))}
                >
                  Clear dates
                </button>
              )}
            </div>
          </div>
          <div className="journey-criteria-row">
            <label>Project Scope</label>
            <div className="journey-criteria-checks">
              {[
                { val: 'all', label: 'All projects' },
                { val: 'hybrid-ai-windows', label: 'hybrid-ai-windows' },
                { val: 'resume-optimizer', label: 'resume-optimizer' },
                { val: 'workdir-only', label: 'workdir only' },
              ].map(({ val, label }) => (
                <label key={val} className="journey-criteria-check">
                  <input
                    type="checkbox"
                    checked={criteria.project_scope.includes(val)}
                    onChange={() => toggleScope(val)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
          <div className="journey-criteria-row">
            <label>Sources</label>
            <div className="journey-criteria-checks">
              {[
                { val: 'files', label: 'Local files' },
                { val: 'git', label: 'Git history' },
                { val: 'arango', label: 'ArangoDB' },
                { val: 'enrichment', label: 'Enrichment data' },
              ].map(({ val, label }) => (
                <label key={val} className="journey-criteria-check">
                  <input
                    type="checkbox"
                    checked={criteria.sources.includes(val)}
                    onChange={() => toggleSource(val)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
          <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
            Criteria apply to the next "Start Mining" run. Clear &amp; Re-mine always uses all sources.
          </div>
        </div>
      )}

      {error && (
        <div className="error-banner">
          {error}
          <button onClick={() => setError('')}>x</button>
        </div>
      )}

      {/* Mining progress */}
      {mining && progress && (
        <div className="journey-progress-section">
          <h3>Mining Progress</h3>
          {phases.map((phase, i) => {
            const isActive = i === currentPhaseIndex;
            const isDone = i < currentPhaseIndex;
            const pct = isActive && progress.total > 0
              ? (progress.processed / progress.total) * 100
              : isDone ? 100 : 0;

            return (
              <div key={phase.key} className="journey-progress-row">
                <div className="journey-progress-label">
                  <span style={{ fontWeight: isActive ? '600' : '400' }}>
                    {phase.label}
                    {isActive && progress.processed > 0 && ` (${progress.processed})`}
                  </span>
                  <span>{isDone ? 'Done' : isActive ? 'In progress' : ''}</span>
                </div>
                <div className="journey-progress-bar">
                  <div
                    className={`journey-progress-fill ${phase.cssClass}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Review panel */}
      {reviewSessionId && (
        <div className="journey-review-panel">
          <div className="journey-review-header">
            <h3>Review Findings</h3>
            <button onClick={() => { setReviewSessionId(null); setReviewMessages([]); }}>&times;</button>
          </div>
          <div className="journey-chat-messages">
            {reviewMessages.map((m, i) => (
              <div key={i} className={`journey-chat-msg ${m.role}`}>
                {m.content}
              </div>
            ))}
            {reviewLoading && <div className="journey-chat-msg assistant">Thinking...</div>}
            <div ref={reviewEndRef} />
          </div>
          <div className="journey-chat-input-row">
            <input
              type="text"
              value={reviewInput}
              onChange={e => setReviewInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendReviewMessage()}
              placeholder="Type your response..."
              disabled={reviewLoading}
            />
            <button onClick={sendReviewMessage} disabled={reviewLoading || !reviewInput.trim()}>
              Send
            </button>
            {reviewComplete && (
              <button className="journey-btn journey-btn-approve" onClick={applyReviewChanges} disabled={reviewLoading}>
                Apply Changes
              </button>
            )}
          </div>
        </div>
      )}

      {/* Stats cards */}
      {stats && (
        <div className="journey-stats">
          <div className="journey-stat-card">
            <div className="journey-stat-value">{stats.events}</div>
            <div className="journey-stat-label">Timeline Events</div>
          </div>
          <div className="journey-stat-card">
            <div className="journey-stat-value">{stats.skills}</div>
            <div className="journey-stat-label">Skills Tracked</div>
          </div>
          <div className="journey-stat-card">
            <div className="journey-stat-value">{stats.achievements}</div>
            <div className="journey-stat-label">Achievements</div>
          </div>
        </div>
      )}

      {/* Sub-navigation */}
      <div className="journey-subnav">
        {[
          { id: 'timeline', label: 'Timeline' },
          { id: 'skills', label: 'Skills' },
          { id: 'narratives', label: 'Narratives' },
          { id: 'history', label: 'Mining History' },
        ].map(tab => (
          <button
            key={tab.id}
            className={`journey-subnav-btn ${subView === tab.id ? 'active' : ''}`}
            onClick={() => setSubView(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Sub-views */}
      {subView === 'timeline' && <JourneyTimeline />}
      {subView === 'skills' && <JourneySkills />}
      {subView === 'narratives' && <JourneyNarratives onApproved={loadStats} />}
      {subView === 'history' && (
        <div className="journey-history">
          <h3>Mining Runs</h3>
          {miningHistory.length === 0 ? (
            <p style={{ color: '#999' }}>No mining runs yet.</p>
          ) : (
            <table className="journey-history-table">
              <thead>
                <tr>
                  <th>Started</th>
                  <th>Completed</th>
                  <th>Status</th>
                  <th>Sources</th>
                  <th>Events</th>
                  <th>Updated</th>
                  <th>Deduped</th>
                </tr>
              </thead>
              <tbody>
                {miningHistory.map(run => (
                  <tr key={run.id}>
                    <td style={{ fontSize: 12 }}>{new Date(run.started_at).toLocaleString()}</td>
                    <td style={{ fontSize: 12 }}>{run.completed_at ? new Date(run.completed_at).toLocaleString() : '—'}</td>
                    <td><span className={`journey-status-${run.status}`}>{run.status}</span></td>
                    <td>{run.sources_scanned}</td>
                    <td><strong>{run.events_added}</strong></td>
                    <td>{run.events_updated}</td>
                    <td>{run.events_deduplicated}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

export default JourneyMiner;
