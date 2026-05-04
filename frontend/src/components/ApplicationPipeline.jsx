import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import CorrelationDashboard from './CorrelationDashboard';

const DISPLAY_STAGES = [
  'discovered', 'bookmarked', 'applied', 'phone_screen',
  'interview', 'offered',
];

const ALL_STAGES = [
  'discovered', 'bookmarked', 'tailored', 'applied',
  'phone_screen', 'interview', 'offered',
  'accepted', 'rejected', 'withdrawn',
];

const INTERVIEW_STAGES = new Set(['phone_screen', 'interview']);
const COVER_LETTER_PROMPT_STAGE = 'applied';

function ApplicationPipeline({ onNavigateToCoach, onDismissReminder }) {
  const [pipeline, setPipeline] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [followup, setFollowup] = useState(null);
  const [followupLoading, setFollowupLoading] = useState(null);
  const [performanceAnalysis, setPerformanceAnalysis] = useState(null);
  const [analyzingPerformance, setAnalyzingPerformance] = useState(false);
  const [applyingId, setApplyingId] = useState(null);
  const [feedbackModal, setFeedbackModal] = useState(null);
  const [feedbackOutcome, setFeedbackOutcome] = useState('');
  const [feedbackNotes, setFeedbackNotes] = useState('');
  const [prepLoading, setPrepLoading] = useState(null);
  const [coverLetterConfirm, setCoverLetterConfirm] = useState(null);
  const [checklistData, setChecklistData] = useState(null);
  const [checklistLoading, setChecklistLoading] = useState(null);
  // Applied-resume attachment
  const [resumeUploadModal, setResumeUploadModal] = useState(null); // posting id
  const [resumeUploadFile, setResumeUploadFile] = useState(null);
  const [resumeUploading, setResumeUploading] = useState(false);
  const [resumeUploadError, setResumeUploadError] = useState('');
  // Map of postingId → {version_id, file_name, char_count}
  const [attachedResumes, setAttachedResumes] = useState({});

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [pipeData, analyticsData, remindersData] = await Promise.all([
        api.getPipeline(),
        api.getPipelineAnalytics(),
        api.getPipelineReminders(),
      ]);
      setPipeline(pipeData);
      setAnalytics(analyticsData);
      setReminders(remindersData.reminders || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Load attached resume metadata for all applied+ postings after pipeline loads
  useEffect(() => {
    if (!pipeline) return;
    const APPLIED_PLUS = new Set(['applied', 'phone_screen', 'interview', 'offered', 'accepted', 'rejected', 'withdrawn']);
    const allCards = Object.values(pipeline.columns || {}).flat();
    const targets = allCards.filter(c => APPLIED_PLUS.has(c.status) && c.tailored_version_id);
    if (!targets.length) return;
    Promise.all(
      targets.map(c =>
        api.getPostingResume(c.id)
          .then(d => d.resume ? [c.id, d.resume] : null)
          .catch(() => null)
      )
    ).then(results => {
      const map = {};
      results.forEach(r => { if (r) map[r[0]] = r[1]; });
      setAttachedResumes(map);
    });
  }, [pipeline]);

  const handleResumeUploadSubmit = async () => {
    if (!resumeUploadFile || !resumeUploadModal) return;
    setResumeUploading(true);
    setResumeUploadError('');
    try {
      const result = await api.attachPostingResume(resumeUploadModal, resumeUploadFile);
      setAttachedResumes(prev => ({ ...prev, [resumeUploadModal]: result }));
      setResumeUploadModal(null);
      setResumeUploadFile(null);
    } catch (err) {
      setResumeUploadError(err.response?.data?.error || 'Upload failed. Please try again.');
    } finally {
      setResumeUploading(false);
    }
  };

  const [dragId, setDragId] = useState(null);
  const [dragOverStage, setDragOverStage] = useState(null);

  const handleMovePosting = async (postingId, newStatus) => {
    // When moving to "applied", prompt for cover letter generation
    if (newStatus === COVER_LETTER_PROMPT_STAGE) {
      setCoverLetterConfirm({ postingId, targetStatus: newStatus });
      return;
    }
    await api.movePosting(postingId, newStatus);
    loadData();
  };

  const handleConfirmMove = async (generateCL) => {
    if (!coverLetterConfirm) return;
    const { postingId, targetStatus } = coverLetterConfirm;
    setCoverLetterConfirm(null);

    if (generateCL) {
      try {
        await api.generateCoverLetter(postingId);
      } catch {
        // Non-fatal — still move to applied
      }
    }
    await api.movePosting(postingId, targetStatus);
    loadData();
  };

  const handlePrepInterview = async (postingId) => {
    if (onNavigateToCoach) {
      // Navigate directly to coach tab with posting pre-selected
      onNavigateToCoach(postingId);
    } else {
      // Fallback: start session and inform user
      setPrepLoading(postingId);
      try {
        await api.coachStart(postingId, 'hiring_manager', 5);
      } catch {
        // ignore — coach tab will handle session creation
      } finally {
        setPrepLoading(null);
      }
    }
  };

  const handleDragStart = (e, cardId) => {
    setDragId(cardId);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(cardId));
  };

  const handleDragOver = (e, stage) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverStage(stage);
  };

  const handleDragLeave = () => {
    setDragOverStage(null);
  };

  const handleDrop = async (e, targetStage) => {
    e.preventDefault();
    setDragOverStage(null);
    const cardId = dragId || e.dataTransfer.getData('text/plain');
    setDragId(null);
    if (cardId) {
      await handleMovePosting(cardId, targetStage);
    }
  };

  const handleDragEnd = () => {
    setDragId(null);
    setDragOverStage(null);
  };

  const handleFollowup = async (postingId) => {
    setFollowupLoading(postingId);
    setFollowup(null);
    try {
      const result = await api.generateFollowup(postingId);
      setFollowup({ postingId, ...result });
    } catch {
      setFollowup({ error: 'Failed to generate follow-up' });
    } finally {
      setFollowupLoading(null);
    }
  };

  const handleAnalyzePerformance = async () => {
    setAnalyzingPerformance(true);
    try {
      const result = await api.analyzePerformance();
      setPerformanceAnalysis(result);
    } catch {
      setPerformanceAnalysis({ analysis: 'Analysis failed' });
    } finally {
      setAnalyzingPerformance(false);
    }
  };

  const handleQuickApply = async (postingId) => {
    setApplyingId(postingId);
    try {
      await api.applyToJob(postingId);
      await handleMovePosting(postingId, 'applied');
    } catch (err) {
      alert('Apply failed: ' + (err?.response?.data?.error || err.message));
    } finally {
      setApplyingId(null);
    }
  };

  const handleRecordFeedback = async () => {
    if (!feedbackModal || !feedbackOutcome) return;
    try {
      await api.recordFeedback({
        posting_id: feedbackModal,
        outcome: feedbackOutcome,
        notes: feedbackNotes,
      });
      setFeedbackModal(null);
      setFeedbackOutcome('');
      setFeedbackNotes('');
      loadData();
    } catch (err) {
      alert('Feedback failed: ' + (err?.response?.data?.error || err.message));
    }
  };

  const copyFollowup = () => {
    if (followup?.body) {
      navigator.clipboard.writeText(`Subject: ${followup.subject}\n\n${followup.body}`);
    }
  };

  const daysSince = (dateStr) => {
    if (!dateStr) return '?';
    const days = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000);
    return days;
  };

  if (loading) {
    return (
      <div className="agent-loading">
        <div className="agent-spinner" />
        <span>Loading pipeline...</span>
      </div>
    );
  }

  return (
    <div className="pipeline-container">
      {/* Analytics */}
      {analytics && (
        <div className="analytics-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Application Analytics</h3>
            <button
              className="btn-search"
              style={{ fontSize: 12, padding: '6px 14px' }}
              onClick={handleAnalyzePerformance}
              disabled={analyzingPerformance}
            >
              {analyzingPerformance ? 'Analyzing...' : 'Analyze Patterns (RTX 5090)'}
            </button>
          </div>
          <div className="analytics-stats">
            <div className="analytics-stat">
              <div className="stat-value">{analytics.total || 0}</div>
              <div className="stat-label">Total Postings</div>
            </div>
            <div className="analytics-stat">
              <div className="stat-value">{analytics.response_rate || 0}%</div>
              <div className="stat-label">Response Rate</div>
            </div>
            <div className="analytics-stat">
              <div className="stat-value">{analytics.avg_days_to_apply || 0}</div>
              <div className="stat-label">Avg Days to Apply</div>
            </div>
            <div className="analytics-stat">
              <div className="stat-value">{analytics.by_status?.applied || 0}</div>
              <div className="stat-label">Applied</div>
            </div>
            <div className="analytics-stat">
              <div className="stat-value">{analytics.by_status?.interview || 0}</div>
              <div className="stat-label">Interviewing</div>
            </div>
            <div className="analytics-stat">
              <div className="stat-value">{analytics.by_status?.offered || 0}</div>
              <div className="stat-label">Offers</div>
            </div>
          </div>

          {/* Top sources */}
          {analytics.top_sources?.length > 0 && (
            <div style={{ fontSize: 13, color: '#666' }}>
              <strong>Top Sources:</strong>{' '}
              {analytics.top_sources.map(s => `${s.source} (${s.count})`).join(', ')}
            </div>
          )}
        </div>
      )}

      {/* Performance Analysis result */}
      {performanceAnalysis && (() => {
        // Handle both structured object and plain string response formats
        const pa = typeof performanceAnalysis.analysis === 'string' && !performanceAnalysis.patterns
          ? { summary: performanceAnalysis.analysis }
          : performanceAnalysis;
        return (
          <div className="analytics-panel">
            <h3>Performance Analysis</h3>
            {pa.patterns && Array.isArray(pa.patterns) && (
              <div style={{ marginBottom: 12 }}>
                <strong>Patterns:</strong>
                <ul>{pa.patterns.map((p, i) => <li key={i}>{typeof p === 'string' ? p : JSON.stringify(p)}</li>)}</ul>
              </div>
            )}
            {pa.strengths && Array.isArray(pa.strengths) && (
              <div style={{ marginBottom: 12 }}>
                <strong>Strengths:</strong>
                <ul>{pa.strengths.map((s, i) => <li key={i}>{typeof s === 'string' ? s : JSON.stringify(s)}</li>)}</ul>
              </div>
            )}
            {pa.improvements && Array.isArray(pa.improvements) && (
              <div style={{ marginBottom: 12 }}>
                <strong>Improvements:</strong>
                <ul>{pa.improvements.map((s, i) => <li key={i}>{typeof s === 'string' ? s : JSON.stringify(s)}</li>)}</ul>
              </div>
            )}
            {pa.recommended_focus && (
              <p style={{ fontWeight: 500, color: '#667eea' }}>
                {pa.recommended_focus}
              </p>
            )}
            {pa.summary && (
              <p style={{ whiteSpace: 'pre-wrap' }}>{pa.summary}</p>
            )}
          </div>
        );
      })()}

      {/* Kanban columns */}
      {pipeline && (
        <div className="pipeline-columns">
          {DISPLAY_STAGES.map(stage => {
            const cards = pipeline.columns?.[stage] || [];
            const isOver = dragOverStage === stage;
            return (
              <div
                key={stage}
                className={`pipeline-column${isOver ? ' pipeline-column-dragover' : ''}`}
                onDragOver={e => handleDragOver(e, stage)}
                onDragLeave={handleDragLeave}
                onDrop={e => handleDrop(e, stage)}
              >
                <div className="pipeline-column-header">
                  <h4>{stage.replace('_', ' ')}</h4>
                  <span className="pipeline-column-count">{cards.length}</span>
                </div>
                {cards.map(card => (
                  <div
                    key={card.id}
                    className={`pipeline-card${dragId === card.id ? ' pipeline-card-dragging' : ''}`}
                    draggable
                    onDragStart={e => handleDragStart(e, card.id)}
                    onDragEnd={handleDragEnd}
                  >
                    <div className="pipeline-card-title">
                      {card.title}
                      {card.is_test === 1 && (
                        <span className="pipeline-card-test-badge" title="Test / demo posting">TEST</span>
                      )}
                    </div>
                    <div className="pipeline-card-company">{card.company}</div>
                    <div className="pipeline-card-footer">
                      <span
                        className="pipeline-card-score"
                        style={{ color: card.match_score >= 70 ? '#4caf50' : card.match_score >= 40 ? '#ff9800' : '#999' }}
                      >
                        {Math.round(card.match_score || 0)}%
                      </span>
                      <span className="pipeline-card-date">
                        {card.discovered_at ? new Date(card.discovered_at).toLocaleDateString() : ''}
                      </span>
                    </div>
                    <div className="pipeline-card-actions">
                      <select
                        value={card.status}
                        onChange={e => handleMovePosting(card.id, e.target.value)}
                      >
                        {ALL_STAGES.map(s => (
                          <option key={s} value={s}>{s.replace('_', ' ')}</option>
                        ))}
                      </select>
                      <div className="pipeline-card-action-buttons">
                        {['applied','phone_screen','interview','offered','accepted','rejected','withdrawn'].includes(card.status) && (
                          <button
                            className="btn-attach-resume"
                            onClick={e => {
                              e.stopPropagation();
                              setResumeUploadModal(card.id);
                              setResumeUploadFile(null);
                              setResumeUploadError('');
                            }}
                            title={attachedResumes[card.id] ? `Resume: ${attachedResumes[card.id].file_name}` : 'Attach resume used for this application'}
                          >
                            {attachedResumes[card.id] ? '📄 Resume ✓' : '📄 Resume'}
                          </button>
                        )}
                        {(card.status === 'bookmarked' || card.status === 'tailored') && (
                          <button
                            className="btn-quick-apply"
                            onClick={e => { e.stopPropagation(); handleQuickApply(card.id); }}
                            disabled={applyingId === card.id}
                          >
                            {applyingId === card.id ? '…' : 'Quick Apply'}
                          </button>
                        )}
                        {INTERVIEW_STAGES.has(card.status) && (
                          <button
                            className="btn-prep"
                            onClick={e => { e.stopPropagation(); handlePrepInterview(card.id); }}
                            disabled={prepLoading === card.id}
                            title="Start interview prep session"
                          >
                            {prepLoading === card.id ? '…' : 'Prepare'}
                          </button>
                        )}
                        <button
                          className="btn-feedback"
                          onClick={e => { e.stopPropagation(); setFeedbackModal(card.id); }}
                          title="Record Feedback"
                        >
                          Feedback
                        </button>
                        <button
                          className="btn-checklist"
                          onClick={async (e) => {
                            e.stopPropagation();
                            if (checklistData?.posting_id === card.id) {
                              setChecklistData(null);
                              return;
                            }
                            setChecklistLoading(card.id);
                            try {
                              const data = await api.getPipelineChecklist(card.id);
                              setChecklistData(data);
                            } catch { setChecklistData(null); }
                            finally { setChecklistLoading(null); }
                          }}
                          disabled={checklistLoading === card.id}
                          title="Ready-to-apply checklist"
                        >
                          {checklistLoading === card.id ? '…' : 'Checklist'}
                        </button>
                      </div>
                    </div>
                    {/* Attached resume indicator */}
                    {attachedResumes[card.id] && (
                      <div className="pipeline-card-resume-attached">
                        <span title={`${attachedResumes[card.id].char_count.toLocaleString()} chars parsed`}>
                          {attachedResumes[card.id].file_name}
                        </span>
                      </div>
                    )}

                    {/* Checklist inline display */}
                    {checklistData && checklistData.posting_id === card.id && (
                      <div style={{ marginTop: 6, padding: 8, background: '#f8fafc', borderRadius: 6, fontSize: 12 }}>
                        <div style={{ fontWeight: 600, marginBottom: 4, color: '#4338ca' }}>
                          Ready to Apply: {checklistData.completion_pct}%
                        </div>
                        {checklistData.checklist.map((c, ci) => (
                          <div key={ci} style={{ display: 'flex', gap: 6, marginBottom: 2, color: c.done ? '#065f46' : '#991b1b' }}>
                            <span>{c.done ? '\u2713' : '\u2717'}</span>
                            <span style={{ fontWeight: 500 }}>{c.item}</span>
                            <span style={{ color: '#6b7280' }}>— {c.detail}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {cards.length === 0 && (
                  <div style={{ fontSize: 12, color: '#aaa', textAlign: 'center', padding: 16 }}>
                    {isOver ? 'Drop here' : 'Empty'}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Reminders */}
      {reminders.length > 0 && (
        <div className="reminders-section">
          <h3>Follow-up Reminders</h3>
          {reminders.map(r => (
            <div key={r.id} className="reminder-item">
              <div className="reminder-info">
                <div className="reminder-title">{r.title}</div>
                <div className="reminder-company">
                  {r.company} &middot; Applied {daysSince(r.updated_at)} days ago
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  className="btn-followup"
                  onClick={() => handleFollowup(r.id)}
                  disabled={followupLoading === r.id}
                >
                  {followupLoading === r.id ? 'Generating...' : 'Generate Follow-up'}
                </button>
                {onDismissReminder && (
                  <button
                    className="btn-dismiss-reminder"
                    onClick={() => onDismissReminder(r.id)}
                    title="Dismiss this reminder"
                    style={{
                      background: 'none', border: '1px solid #ddd', borderRadius: 4,
                      padding: '4px 10px', fontSize: 12, cursor: 'pointer', color: '#999',
                    }}
                  >
                    Dismiss
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Follow-up result */}
      {followup && !followup.error && (
        <div className="followup-result">
          <h3>Follow-up Email Draft</h3>
          <div className="email-subject">Subject: {followup.subject}</div>
          <div className="email-body" style={{ whiteSpace: 'pre-wrap' }}>{followup.body}</div>
          <button className="btn-copy" onClick={copyFollowup}>Copy to Clipboard</button>
        </div>
      )}

      {/* Feedback modal */}
      {feedbackModal && (
        <div className="feedback-modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <div className="feedback-modal" style={{
            background: '#fff', borderRadius: 8, padding: 24, minWidth: 320, maxWidth: 420,
          }}>
            <h3>Record Feedback</h3>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>Outcome</label>
              <select
                value={feedbackOutcome}
                onChange={e => setFeedbackOutcome(e.target.value)}
                style={{ width: '100%', padding: '8px 10px' }}
                data-testid="feedback-outcome"
              >
                <option value="">Select outcome...</option>
                <option value="interview">Got Interview</option>
                <option value="offer">Got Offer</option>
                <option value="rejected">Rejected</option>
                <option value="ghosted">Ghosted</option>
                <option value="no_response">No Response</option>
                <option value="withdrawn">Withdrawn</option>
              </select>
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>Notes</label>
              <textarea
                value={feedbackNotes}
                onChange={e => setFeedbackNotes(e.target.value)}
                placeholder="Optional notes..."
                rows={3}
                style={{ width: '100%', padding: 8 }}
                data-testid="feedback-notes"
              />
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => { setFeedbackModal(null); setFeedbackOutcome(''); setFeedbackNotes(''); }}>
                Cancel
              </button>
              <button className="btn-search" onClick={handleRecordFeedback} disabled={!feedbackOutcome}>
                Save Feedback
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cover letter confirmation on move to "applied" */}
      {coverLetterConfirm && (
        <div className="feedback-modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <div className="feedback-modal" style={{
            background: '#fff', borderRadius: 8, padding: 24, minWidth: 320, maxWidth: 420,
          }}>
            <h3>Moving to Applied</h3>
            <p style={{ color: '#555', marginBottom: 16 }}>
              Would you like to generate a cover letter for this application?
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => handleConfirmMove(false)}>
                Skip
              </button>
              <button className="btn-search" onClick={() => handleConfirmMove(true)}>
                Generate Cover Letter
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Resume upload modal */}
      {resumeUploadModal && (
        <div className="feedback-modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <div className="feedback-modal" style={{
            background: '#fff', borderRadius: 8, padding: 24, minWidth: 340, maxWidth: 460,
          }}>
            <h3 style={{ marginTop: 0 }}>Attach Applied Resume</h3>
            <p style={{ color: '#555', marginBottom: 12 }}>
              Upload the resume you submitted for this application (PDF, DOCX, DOC, or TXT).
            </p>
            <input
              type="file"
              accept=".pdf,.docx,.doc,.txt"
              onChange={e => { setResumeUploadFile(e.target.files[0] || null); setResumeUploadError(''); }}
              style={{ marginBottom: 12, display: 'block' }}
            />
            {resumeUploadFile && (
              <div style={{ fontSize: 13, color: '#555', marginBottom: 8 }}>
                Selected: <strong>{resumeUploadFile.name}</strong>
              </div>
            )}
            {resumeUploadError && (
              <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 8 }}>{resumeUploadError}</div>
            )}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => { setResumeUploadModal(null); setResumeUploadFile(null); setResumeUploadError(''); }}
                disabled={resumeUploading}
              >
                Cancel
              </button>
              <button
                className="btn-search"
                onClick={handleResumeUploadSubmit}
                disabled={!resumeUploadFile || resumeUploading}
              >
                {resumeUploading ? 'Uploading…' : 'Save Resume'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Callback correlations sidebar */}
      <CorrelationDashboard />

      {/* Empty state */}
      {pipeline && pipeline.total === 0 && (
        <div className="empty-state">
          <p>No applications in the pipeline yet.</p>
          <p style={{ fontSize: 14 }}>Use Job Scout to find and score positions, then track them here.</p>
        </div>
      )}
    </div>
  );
}

export default ApplicationPipeline;
