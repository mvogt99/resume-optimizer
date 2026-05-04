import React, { useState, useRef, useEffect } from 'react';
import api from '../services/api';
import ExpertComparison from './ExpertComparison';
import KeywordGroups from './KeywordGroups';
import GapClassificationPanel from './GapClassificationPanel';
import ClaimAuditPanel from './ClaimAuditPanel';
import RewritePanel from './RewritePanel';
import ArtifactPanel from './ArtifactPanel';
import { saveChatHistoryFromServer } from '../utils/chatHistory';
import '../styles/OptimizedResumeView.css';

function ScoreRing({ score, size = 80, label }) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 70 ? '#4caf50' : score >= 40 ? '#ff9800' : '#f44336';

  return (
    <div className="score-ring-wrapper">
      <svg width={size} height={size} className="score-ring-svg">
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#e0e0e0" strokeWidth="6"
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central"
          fontSize="18" fontWeight="700" fill="#333">
          {Math.round(score)}%
        </text>
      </svg>
      {label && <div className="score-ring-label">{label}</div>}
    </div>
  );
}

function CollapsibleSection({ title, badge, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={`collapsible-section ${open ? 'open' : ''}`}>
      <button className="collapsible-header" onClick={() => setOpen(!open)}>
        <span className="collapsible-title">{title}</span>
        {badge != null && <span className="collapsible-badge">{badge}</span>}
        <span className="collapsible-arrow">{open ? '\u25B2' : '\u25BC'}</span>
      </button>
      {open && <div className="collapsible-body">{children}</div>}
    </div>
  );
}

function getScoreExplanation(label, value, sectionsFound, missingSkills) {
  if (label === 'keyword_coverage') {
    if (value >= 80) return 'Strong keyword alignment — most job description terms appear in your resume.';
    if (value >= 60) return 'Good coverage. Use "Resolve Missing Keywords" below to map remaining gaps via equivalencies, then generate rewrites.';
    if (value >= 40) return 'Moderate keyword overlap. Run the equivalency interview to map your experience to JD terminology, then generate section rewrites.';
    return 'Low keyword match. Start by resolving missing keywords below — many may already match your experience under different names.';
  }
  if (label === 'semantic_similarity') {
    if (value >= 70) return 'Your resume language closely mirrors the job description tone and terminology.';
    if (value >= 50) return 'Moderate relevance. Generate rewrites to weave JD terminology into your resume bullets. Ignore employer-description keywords to remove noise.';
    return 'Weak semantic alignment. Generate section rewrites from resolved equivalencies — this replaces generic language with JD-specific terminology.';
  }
  if (label === 'skills_match') {
    const missingNames = (missingSkills || []).map(s => s.keyword || s).filter(Boolean);
    if (value >= 90) {
      if (missingNames.length > 0)
        return `Excellent coverage. ${missingNames.length} minor gap(s): ${missingNames.join(', ')}. Add these to your Skills section or import from LinkedIn.`;
      return 'Excellent skills coverage — your skills align well with requirements.';
    }
    if (value >= 70) {
      const hint = missingNames.length > 0 ? ` Missing: ${missingNames.slice(0, 5).join(', ')}.` : '';
      return `Good skills match.${hint} Check LinkedIn profile, project analysis, and journey data for additional skills to import.`;
    }
    if (value >= 40) return 'Partial skills match. Import your LinkedIn profile and run the experience interview to surface skills from your career history.';
    return 'Significant skills gap. Import LinkedIn profile, run project analysis, and use the experience chat to extract skills from your work history.';
  }
  if (label === 'section_completeness') {
    const sections = sectionsFound || {};
    const missing = ['summary', 'experience', 'education', 'skills'].filter(s => !sections[s]);
    if (value >= 100) return 'All major resume sections detected.';
    if (missing.length > 0) return `Missing sections: ${missing.map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(', ')}. ATS systems expect standard headings — add these sections to your resume.`;
    return 'Resume structure incomplete. Ensure you have Summary, Experience, Education, and Skills sections with proper headings.';
  }
  return '';
}

/**
 * AtsImprovementPanel
 *
 * Props:
 *   data                 object  — original optimize response (always available)
 *   resumeId             number  — resume DB id
 *   liveScore            number  — current score after rewrites (overrides data score when set)
 *   liveResumeText       string  — post-rewrite resume text (overrides original optimized text)
 *   liveMissingKeywords  string[] — current missing keywords after last rescore
 *   jobDescText          string  — resolved job description text
 */
function AtsImprovementPanel({
  data,
  resumeId,
  liveScore = null,
  liveBreakdown = null,
  liveResumeText = null,
  liveMissingKeywords = null,
  jobDescText = '',
  jobSessionId = null,
  onSessionScoreUpdate = null,
}) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const [improvedText, setImprovedText] = useState('');
  const [showPanel, setShowPanel] = useState(false);
  const [rescoring, setRescoring] = useState(false);
  const [rescoreResult, setRescoreResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedVersionId, setSavedVersionId] = useState(null);
  const [downloadingFmt, setDownloadingFmt] = useState(null);
  const [corrections, setCorrections] = useState([]);
  const [showCorrections, setShowCorrections] = useState(false);
  const [newOldText, setNewOldText] = useState('');
  const [newNewText, setNewNewText] = useState('');
  const messagesEndRef = useRef(null);

  // True effective values — live state wins over stale original data
  const effectiveScore = liveScore ?? (data?.relevance_score || data?.ats_compliance_score || 0);
  const effectiveResumeText = liveResumeText || data?.optimized_resume?.optimized_text || '';
  const effectiveJobDesc = jobDescText || data?.job_description_text || '';
  const isPostRescore = liveScore != null;

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Load remembered corrections when panel opens
  useEffect(() => {
    if (showPanel) {
      api.listCorrections(resumeId).then(data => {
        setCorrections(data.corrections || []);
      }).catch(() => {});
    }
  }, [showPanel, resumeId]);

  const handleRemoveCorrection = async (id) => {
    try {
      await api.deleteCorrection(id);
      setCorrections(prev => prev.filter(c => c.id !== id));
    } catch {
      alert('Failed to remove correction.');
    }
  };

  const handleAddCorrection = async () => {
    if (!newOldText.trim() || !newNewText.trim()) return;
    try {
      const result = await api.addCorrection(newOldText.trim(), newNewText.trim(), resumeId);
      setCorrections(prev => [...prev, { id: result.id, old_text: newOldText.trim(), new_text: newNewText.trim(), resume_id: resumeId }]);
      setNewOldText('');
      setNewNewText('');
    } catch {
      alert('Failed to save correction.');
    }
  };

  const persistSessionScore = (newScore) => {
    if (jobSessionId && newScore != null) {
      api.updateSession(jobSessionId, { ats_score: newScore }).catch(() => {});
      if (onSessionScoreUpdate) onSessionScoreUpdate();
    }
  };

  const handleStart = async () => {
    setShowPanel(true);
    setLoading(true);
    try {
      const scoreData = {
        score: effectiveScore,
        score_breakdown: liveBreakdown || data?.score_breakdown || {},
        added_keywords: liveMissingKeywords || data?.optimized_resume?.added_keywords || [],
        sections_found: data?.sections_found || {},
        job_desc_text: effectiveJobDesc,
        original_text: data?.original_resume_text || '',
        // Use the live post-rewrite text as the starting point when available
        optimized_text: effectiveResumeText,
        // Pass remaining missing keywords so the AI knows what gaps are left
        missing_keywords: liveMissingKeywords || [],
        post_rescore: isPostRescore,
      };
      const result = await api.startAtsImprovement(resumeId, scoreData);
      setSessionId(result.session_id);
      setStage(result.stage);
      setMessages([{ role: 'assistant', content: result.message }]);
    } catch (err) {
      setMessages([{ role: 'assistant', content: 'Failed to start improvement session. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !sessionId || loading) return;
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);
    try {
      const result = await api.sendAtsImprovementMessage(sessionId, userMsg);
      setMessages(prev => [...prev, { role: 'assistant', content: result.message }]);
      setStage(result.stage);
      if (result.is_complete) setIsComplete(true);
      if (result.is_complete === false) setIsComplete(false);
      if (result.improved_text) setImprovedText(result.improved_text);

      // Auto-trigger rescore when backend signals it
      if (result.rescore_request && (result.improved_text || improvedText)) {
        const textToScore = result.improved_text || improvedText;
        const jd = effectiveJobDesc;
        try {
          const scoreResult = await api.scoreResumeText(textToScore, jd);
          setRescoreResult(scoreResult);
          persistSessionScore(scoreResult.ats_score);
          const delta = effectiveScore != null
            ? ` (${scoreResult.ats_score > effectiveScore ? '+' : ''}${scoreResult.ats_score - effectiveScore} pts from baseline)`
            : '';
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: `**ATS Score: ${scoreResult.ats_score}%**${delta}\n\nKeywords: ${scoreResult.score_breakdown?.keyword_coverage ?? '—'}% · Semantic: ${scoreResult.score_breakdown?.semantic_similarity ?? '—'}% · Skills: ${scoreResult.score_breakdown?.skills_match ?? '—'}% · Sections: ${scoreResult.score_breakdown?.section_completeness ?? '—'}%\n\nWould you like to make further changes or **accept** to finalize?`,
          }]);
        } catch {
          setMessages(prev => [...prev, { role: 'assistant', content: 'Re-score failed — try the Re-Score button below.' }]);
        }
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Something went wrong. Please try again.',
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (effectiveScore >= 100) return null;

  return (
    <div className="ats-improve-section">
      {!showPanel ? (
        <div className="ats-improve-prompt">
          <div className="ats-improve-prompt-content">
            <div className="ats-improve-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#667eea" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div>
              <h4>{isPostRescore ? 'Continue Improving' : 'Improve Your Score'}</h4>
              <p>
                {isPostRescore ? (
                  <>
                    Score updated to <strong>{effectiveScore}%</strong> after your recent rewrites.
                    {liveMissingKeywords?.length > 0
                      ? ` ${liveMissingKeywords.length} keyword gap${liveMissingKeywords.length !== 1 ? 's' : ''} remain.`
                      : ' Start a guided AI session to push it higher.'}
                  </>
                ) : (
                  <>Your score is {effectiveScore}%. Start a guided AI conversation to identify
                  the best improvements and generate an optimized version.</>
                )}
              </p>
            </div>
          </div>
          <button className="btn-improve-score" onClick={handleStart}>
            Improve Score
          </button>
        </div>
      ) : (
        <div className="ats-improve-chat">
          <div className="ats-improve-chat-header">
            <h4>Score Improvement</h4>
            <div className="ats-improve-stage-badges">
              {['diagnose', 'improve', 'confirming', 'rewrite', 'review'].map(s => (
                <span key={s} className={`ats-stage-badge ${stage === s ? 'active' : ''} ${
                  ['diagnose', 'improve', 'confirming', 'rewrite', 'review'].indexOf(s) <
                  ['diagnose', 'improve', 'confirming', 'rewrite', 'review'].indexOf(stage) ? 'done' : ''
                }`}>
                  {s}
                </span>
              ))}
            </div>
            {sessionId && messages.length > 0 && (
              <button
                className="ats-improve-save-history"
                onClick={() => saveChatHistoryFromServer(api, 'ats_improve', sessionId)}
                title="Save chat history"
              >
                Save History
              </button>
            )}
            <button
              className="ats-improve-corrections-toggle"
              onClick={() => setShowCorrections(v => !v)}
              title="Remembered corrections"
            >
              Corrections {corrections.length > 0 && `(${corrections.length})`}
            </button>
            <button
              className="ats-improve-close"
              onClick={() => setShowPanel(false)}
              title="Minimize"
            >
              &minus;
            </button>
          </div>

          {showCorrections && (
            <div className="ats-corrections-panel">
              <div className="ats-corrections-title">
                Remembered Corrections — applied automatically to every generated resume
              </div>
              {corrections.length === 0 ? (
                <p className="ats-corrections-empty">No corrections saved yet.</p>
              ) : (
                <ul className="ats-corrections-list">
                  {corrections.map(c => (
                    <li key={c.id} className="ats-correction-item">
                      <span className="ats-correction-scope">
                        {c.resume_id ? `Resume ${c.resume_id}` : 'All resumes'}
                      </span>
                      <span className="ats-correction-old">&ldquo;{c.old_text.slice(0, 60)}{c.old_text.length > 60 ? '…' : ''}&rdquo;</span>
                      <span className="ats-correction-arrow">→</span>
                      <span className="ats-correction-new">&ldquo;{c.new_text.slice(0, 60)}{c.new_text.length > 60 ? '…' : ''}&rdquo;</span>
                      <button
                        className="ats-correction-remove"
                        onClick={() => handleRemoveCorrection(c.id)}
                        title="Remove this correction"
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="ats-corrections-add">
                <input
                  type="text"
                  placeholder='Replace this text…'
                  value={newOldText}
                  onChange={e => setNewOldText(e.target.value)}
                />
                <span>→</span>
                <input
                  type="text"
                  placeholder='…with this text'
                  value={newNewText}
                  onChange={e => setNewNewText(e.target.value)}
                />
                <button onClick={handleAddCorrection} disabled={!newOldText.trim() || !newNewText.trim()}>
                  Add
                </button>
              </div>
            </div>
          )}

          <div className="ats-improve-messages">
            {messages.map((msg, i) => (
              <div key={i} className={`ats-chat-msg ${msg.role}`}>
                <div className="ats-chat-msg-content">{msg.content}</div>
              </div>
            ))}
            {loading && (
              <div className="ats-chat-msg assistant">
                <div className="ats-chat-msg-content ats-typing">Thinking...</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {(
            <div className="ats-improve-input-row">
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={stage === 'diagnose'
                  ? 'Choose an area to improve (e.g., "1" or "keywords")...'
                  : stage === 'improve'
                  ? 'Discuss changes or say "go ahead" to generate...'
                  : stage === 'confirming'
                  ? 'Say "yes" / "go ahead" to generate, or describe final changes...'
                  : stage === 'review'
                  ? 'Say "re-score", describe more changes, or ask a question...'
                  : 'Review changes, say "re-score", or say "accept" to finalize...'}
                disabled={loading}
              />
              <button onClick={handleSend} disabled={loading || !input.trim()}>
                Send
              </button>
            </div>
          )}

          {isComplete && improvedText && (
            <div className="ats-improve-done-panel">
              <div className="ats-done-header">Improved resume ready</div>

              {/* Re-score */}
              <div className="ats-done-row">
                <button
                  className="btn-ats-action btn-ats-rescore"
                  disabled={rescoring}
                  onClick={async () => {
                    setRescoring(true);
                    setRescoreResult(null);
                    try {
                      const jd = data?.job_description_text || '';
                      const result = await api.scoreResumeText(improvedText, jd);
                      setRescoreResult(result);
                      persistSessionScore(result.ats_score);
                    } catch {
                      setRescoreResult({ error: 'Re-score failed. Please try again.' });
                    } finally {
                      setRescoring(false);
                    }
                  }}
                >
                  {rescoring ? 'Scoring…' : 'Re-score ATS'}
                </button>
                {rescoreResult && !rescoreResult.error && (
                  <span className="ats-rescore-badge">
                    New ATS score: <strong>{rescoreResult.ats_score}%</strong>
                    {effectiveScore != null && (
                      <span className={rescoreResult.ats_score > effectiveScore ? 'ats-delta-up' : 'ats-delta-down'}>
                        {' '}({rescoreResult.ats_score > effectiveScore ? '+' : ''}{rescoreResult.ats_score - effectiveScore} pts)
                      </span>
                    )}
                  </span>
                )}
                {rescoreResult?.error && (
                  <span className="ats-rescore-error">{rescoreResult.error}</span>
                )}
              </div>

              {/* Save to database */}
              <div className="ats-done-row">
                <button
                  className="btn-ats-action btn-ats-save"
                  disabled={saving || !!savedVersionId}
                  onClick={async () => {
                    setSaving(true);
                    try {
                      const result = await api.saveResumeVersion(improvedText, 'ATS Improved');
                      setSavedVersionId(result.version_id);
                    } catch {
                      alert('Failed to save resume version.');
                    } finally {
                      setSaving(false);
                    }
                  }}
                >
                  {saving ? 'Saving…' : savedVersionId ? 'Saved to Library ✓' : 'Save to Resume Library'}
                </button>
              </div>

              {/* Download buttons */}
              <div className="ats-done-row ats-done-downloads">
                <span className="ats-done-label">Download:</span>
                {['pdf', 'docx', 'txt'].map(fmt => (
                  <button
                    key={fmt}
                    className="btn-ats-action btn-ats-dl"
                    disabled={!!downloadingFmt}
                    onClick={() => {
                      if (fmt === 'txt') {
                        const blob = new Blob([improvedText], { type: 'text/plain' });
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url; a.download = 'improved_resume.txt';
                        document.body.appendChild(a); a.click();
                        window.URL.revokeObjectURL(url); document.body.removeChild(a);
                        return;
                      }
                      setDownloadingFmt(fmt);
                      api.exportResumeText(improvedText, fmt)
                        .then(blob => {
                          const url = window.URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url; a.download = `improved_resume.${fmt}`;
                          document.body.appendChild(a); a.click();
                          window.URL.revokeObjectURL(url); document.body.removeChild(a);
                        })
                        .catch(() => alert(`Failed to download ${fmt.toUpperCase()}`))
                        .finally(() => setDownloadingFmt(null));
                    }}
                  >
                    {downloadingFmt === fmt ? `${fmt.toUpperCase()}…` : fmt.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OptimizedResumeView({ data, onStartOver, resumeSource, resumeName, jobDescTextFallback, resumeId, jobSessionId = null, onSessionScoreUpdate = null }) {
  const [downloadingFmt, setDownloadingFmt] = useState(null);
  const [liveResumeText, setLiveResumeText] = useState(null); // set when rewrites applied
  // Inline editing of the optimized resume text
  const [editingResume, setEditingResume] = useState(false);
  const [resumeEditDraft, setResumeEditDraft] = useState('');

  // Alignment analysis (gap classification + hybrid scoring)
  const [alignmentData, setAlignmentData] = useState(null);
  const [alignmentLoading, setAlignmentLoading] = useState(false);
  const [alignmentError, setAlignmentError] = useState('');
  // Cache key: resumeId + first 200 chars of jd — avoids re-running on every render
  const [alignmentCacheKey, setAlignmentCacheKey] = useState('');

  // Claim audit state (lazy — triggered by "Audit Claims" button)
  const [auditData, setAuditData]       = useState(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError]     = useState('');

  // Rewrite-applied toast: shows "Re-analyzing score..." banner for 3 s after a rewrite lands
  const [rewriteAppliedToast, setRewriteAppliedToast] = useState(false);
  // Live ATS score after rewrites — overrides the static score from the initial optimize call
  const [liveAtsScore, setLiveAtsScore] = useState(null);
  const [liveBreakdown, setLiveBreakdown] = useState(null);
  const [liveMissingKeywords, setLiveMissingKeywords] = useState(null);
  const [liveMissingSkills, setLiveMissingSkills] = useState(null);
  const [rescoring, setRescoring] = useState(false);
  const initialScoreDone = useRef(false);

  // Auto-rescore on mount so equivalencies are reflected in the displayed scores
  // instead of showing stale numbers from the original optimize call.
  useEffect(() => {
    if (initialScoreDone.current) return;
    const resumeText = data?.optimized_resume?.optimized_text || '';
    const jdText = data?.job_description_text || jobDescTextFallback || '';
    if (!resumeText || !jdText) return;
    initialScoreDone.current = true;
    setRescoring(true);
    api.scoreResumeText(resumeText, jdText)
      .then(result => {
        if (result?.ats_score != null) setLiveAtsScore(result.ats_score);
        if (result?.score_breakdown) setLiveBreakdown(result.score_breakdown);
        if (result?.missing_keywords) setLiveMissingKeywords(result.missing_keywords);
        if (result?.missing_skills) setLiveMissingSkills(result.missing_skills);
      })
      .catch(() => { /* non-fatal — keep original scores */ })
      .finally(() => setRescoring(false));
  }, [data, jobDescTextFallback]);

  const handleRewriteApplied = async (newText) => {
    setRewriteAppliedToast(true);
    // Re-score the ATS using the updated resume text
    const jdText = data?.job_description_text || jobDescTextFallback || '';
    if (newText && jdText) {
      setRescoring(true);
      try {
        const result = await api.scoreResumeText(newText, jdText);
        if (result?.ats_score != null) setLiveAtsScore(result.ats_score);
        if (result?.score_breakdown) setLiveBreakdown(result.score_breakdown);
        if (result?.missing_keywords) setLiveMissingKeywords(result.missing_keywords);
        if (result?.missing_skills) setLiveMissingSkills(result.missing_skills);
      } catch { /* non-fatal — keep old score */ }
      finally { setRescoring(false); }
    }
    // Also force re-run gap analysis
    handleRunAnalysis(true);
    setTimeout(() => setRewriteAppliedToast(false), 3000);
  };

  const handleRunAudit = async () => {
    const jdText = data?.job_description_text || jobDescTextFallback || '';
    const rid = resumeId || data?.resume_id;
    if (!rid || !jdText) return;
    setAuditLoading(true);
    setAuditError('');
    try {
      const result = await api.runClaimAudit(rid, jdText);
      setAuditData(result);
    } catch (err) {
      setAuditError(err.response?.data?.error || err.message || 'Audit failed.');
    } finally {
      setAuditLoading(false);
    }
  };

  const handleRunAnalysis = async (force = false) => {
    const jdText = data?.job_description_text || jobDescTextFallback || '';
    const rid = resumeId || data?.resume_id;
    if (!rid || !jdText) return;
    const cacheKey = `${rid}::${jdText.slice(0, 200)}`;
    if (!force && alignmentData && alignmentCacheKey === cacheKey) return;
    setAlignmentLoading(true);
    setAlignmentError('');
    try {
      const result = await api.runAlignmentAnalysis(rid, jdText);
      setAlignmentData(result);
      setAlignmentCacheKey(cacheKey);
    } catch (err) {
      setAlignmentError(
        err.response?.data?.error || err.message || 'Analysis failed.'
      );
    } finally {
      setAlignmentLoading(false);
    }
  };

  const handleStartResumeEdit = () => {
    const currentText = liveResumeText || (data?.optimized_resume?.optimized_text || '');
    setResumeEditDraft(currentText);
    setEditingResume(true);
  };
  const handleSaveResumeEdit = () => {
    setLiveResumeText(resumeEditDraft);
    setEditingResume(false);
    handleRewriteApplied(resumeEditDraft);
  };
  const handleCancelResumeEdit = () => setEditingResume(false);

  const handleDownload = (format) => {
    const text = data?.optimized_resume?.optimized_text || '';
    if (!text) { alert('No optimized resume text available to download.'); return; }

    if (format === 'txt') {
      const blob = new Blob([text], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'optimized_resume.txt';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      return;
    }

    // PDF or DOCX — POST optimized text to backend exporter
    setDownloadingFmt(format);
    api.exportResumeText(text, format)
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `optimized_resume.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      })
      .catch(err => {
        const msg = err.response?.data?.error || err.message || 'Download failed';
        alert('Download failed: ' + msg);
      })
      .finally(() => setDownloadingFmt(null));
  };

  const atsScore = liveAtsScore ?? (data?.relevance_score || data?.ats_compliance_score || 0);
  const matchingKeywords = data?.optimized_resume?.matching_keywords || [];
  const addedKeywords = data?.optimized_resume?.added_keywords || [];
  const rawOptimizedText = data?.optimized_resume?.optimized_text || '';
  const optimizedText = liveResumeText || rawOptimizedText;
  const breakdown = liveBreakdown || data?.score_breakdown || {};
  const accomplishments = data?.accomplishments || [];
  const recommendations = data?.recommendations || [];
  const originalText = data?.original_resume_text || '';
  const jobDescText = data?.job_description_text || jobDescTextFallback || '';
  const sectionsFound = data?.sections_found || {};
  const skillPhrases = data?.skill_phrases_matched || [];
  // Effective resume ID — prefer prop (from Dashboard state), fall back to ID in API response
  const effectiveResumeId = resumeId || data?.resume_id || null;

  const hasBreakdown = Object.keys(breakdown).length > 0;

  return (
    <div className="optimized-resume-view">
      <h2>Your Optimized Resume</h2>

      {(resumeSource || resumeName) && (
        <div className="resume-source-info">
          <span className={`source-badge source-${resumeSource || 'upload'}`}>
            {resumeSource === 'linkedin' ? 'LinkedIn' :
             resumeSource === 'google_drive' ? 'Google Drive' :
             resumeSource === 'experience_chat' ? 'Experience Interview' : 'File Upload'}
          </span>
          {resumeName && <span className="source-name">{resumeName}</span>}
        </div>
      )}

      <div className="results-summary">
        <div className="score-card">
          <div className="score-value">
            {rescoring ? <span className="analysis-spinner" /> : `${atsScore}%`}
          </div>
          <div className="score-label">
            Relevance Score
            {liveAtsScore != null && !rescoring && (
              <span className={`score-delta ${liveAtsScore > (data?.relevance_score || 0) ? 'score-delta--up' : 'score-delta--down'}`}>
                {liveAtsScore > (data?.relevance_score || 0) ? ' ▲' : ' ▼'}
                {Math.abs(liveAtsScore - (data?.relevance_score || 0))} pts
              </span>
            )}
          </div>
        </div>

        {hasBreakdown && (
          <div className="score-breakdown-grid">
            <ScoreRing score={breakdown.keyword_coverage || 0} size={72} label="Keywords" />
            <ScoreRing score={breakdown.semantic_similarity || 0} size={72} label="Relevance" />
            <ScoreRing score={breakdown.skills_match || 0} size={72} label="Skills" />
            <ScoreRing score={breakdown.section_completeness || 0} size={72} label="Sections" />
          </div>
        )}
      </div>

      {/* ATS Improvement Panel — always available; uses live score/text when a rescore has run */}
      <AtsImprovementPanel
        data={data}
        resumeId={effectiveResumeId}
        liveScore={liveAtsScore}
        liveBreakdown={liveBreakdown}
        liveResumeText={liveResumeText || null}
        liveMissingKeywords={liveMissingKeywords}
        jobDescText={jobDescText}
        jobSessionId={jobSessionId}
        onSessionScoreUpdate={onSessionScoreUpdate}
      />

      {hasBreakdown && (
        <div className="breakdown-detail">
          <h4>Score Breakdown</h4>
          <div className="breakdown-bars">
            <BreakdownBar label="Keyword Coverage" value={breakdown.keyword_coverage || 0} weight="20%" />
            <BreakdownBar label="Semantic Relevance" value={breakdown.semantic_similarity || 0} weight="20%" />
            <BreakdownBar label="Skills Match" value={breakdown.skills_match || 0} weight="50%" />
            <BreakdownBar label="Section Completeness" value={breakdown.section_completeness || 0} weight="10%" />
          </div>

          <div className="score-explanations">
            <ul className="explanation-list">
              {[
                ['keyword_coverage', 'Keywords', breakdown.keyword_coverage],
                ['semantic_similarity', 'Relevance', breakdown.semantic_similarity],
                ['skills_match', 'Skills', breakdown.skills_match],
                ['section_completeness', 'Sections', breakdown.section_completeness],
              ].map(([key, name, val]) => {
                const v = val || 0;
                const cls = v >= 70 ? 'good' : v >= 40 ? 'moderate' : 'low';
                return (
                  <li key={key} className={`explanation-item explanation-${cls}`}>
                    <strong>{name}:</strong> {getScoreExplanation(key, v, sectionsFound, liveMissingSkills)}
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}

      {(jobDescText || originalText || matchingKeywords.length > 0 || skillPhrases.length > 0) && (
        <div className="context-comparison-panel">
          <h4>Context & Comparison</h4>

          {jobDescText && (
            <CollapsibleSection
              title="Job Description"
              badge={`${jobDescText.length.toLocaleString()} chars`}
            >
              <pre className="context-text">{jobDescText}</pre>
            </CollapsibleSection>
          )}

          {originalText && (
            <CollapsibleSection
              title="Original Resume"
              badge={`${originalText.length.toLocaleString()} chars`}
            >
              <pre className="context-text">{originalText}</pre>
            </CollapsibleSection>
          )}

          {(matchingKeywords.length > 0 || skillPhrases.length > 0) && (
            <CollapsibleSection
              title="Keyword Highlights"
              badge={`${matchingKeywords.length + skillPhrases.length} matches`}
            >
              {matchingKeywords.length > 0 && (
                <div className="highlight-group">
                  <span className="highlight-label">Matching Keywords</span>
                  <div className="keyword-chips">
                    {matchingKeywords.map((kw, i) => (
                      <span key={i} className="chip chip-success">{kw}</span>
                    ))}
                  </div>
                </div>
              )}
              {skillPhrases.length > 0 && (
                <div className="highlight-group">
                  <span className="highlight-label">Skill Phrases Matched</span>
                  <div className="keyword-chips">
                    {skillPhrases.map((sp, i) => (
                      <span key={i} className="chip chip-phrase">{sp}</span>
                    ))}
                  </div>
                </div>
              )}
            </CollapsibleSection>
          )}
        </div>
      )}

      <KeywordGroups
        matchingKeywords={matchingKeywords}
        missingKeywords={rescoring ? [] : (liveMissingKeywords ?? addedKeywords)}
        jobDescription={jobDescText}
        resumeText={optimizedText}
        originalText={rawOptimizedText}
        onResumeUpdated={(newText) => setLiveResumeText(newText)}
        onApplied={handleRewriteApplied}
      />

      {/* Gap Classification — Phase A+B alignment engine */}
      <div className="alignment-analysis-section">
        <div className="alignment-section-header">
          <h3>Gap Analysis</h3>
          {!alignmentData && (
            <button
              className="btn-run-analysis"
              onClick={() => handleRunAnalysis(false)}
              disabled={alignmentLoading || !effectiveResumeId || !jobDescText}
              title={
                !effectiveResumeId ? 'Resume ID not available — try re-optimizing' :
                !jobDescText ? 'Job description not available' :
                'Deep AI analysis: classifies gaps by type, scores 7 dimensions of fit, identifies weak wording and seniority signals'
              }
            >
              {alignmentLoading ? (
                <><span className="analysis-spinner" /> Analyzing&hellip;</>
              ) : (
                'Analyze Gaps'
              )}
            </button>
          )}
          {alignmentData && (
            <button
              className="btn-run-analysis btn-rerun"
              onClick={() => handleRunAnalysis(true)}
              disabled={alignmentLoading}
              title="Re-run analysis"
            >
              {alignmentLoading ? 'Re-analyzing\u2026' : 'Re-analyze'}
            </button>
          )}
        </div>
        {alignmentError && (
          <div className="alignment-error">{alignmentError}</div>
        )}
        {alignmentData && (
          <GapClassificationPanel
            gaps={alignmentData.gaps || []}
            scores={alignmentData.scores || []}
            summary={alignmentData.summary || null}
            requirements={alignmentData.requirements || []}
          />
        )}

        {/* Rewrite Suggestions — shown once gap analysis is available */}
        {alignmentData && (alignmentData.gaps || []).length > 0 && (
          <div className="rewrite-subsection">
            {rewriteAppliedToast && (
              <div className="rewrite-score-toast">
                <span className="analysis-spinner" /> Re-analyzing alignment score&hellip;
              </div>
            )}
            <RewritePanel
              gaps={alignmentData.gaps || []}
              resumeId={resumeId}
              jobDescText={jobDescText}
              onApplied={handleRewriteApplied}
            />
          </div>
        )}

        {/* Claim Audit — lazy-loaded on demand */}
        <div className="claim-audit-subsection">
          <div className="claim-audit-subsection-header">
            <span className="claim-audit-subsection-title">Claim Audit</span>
            {!auditData && (
              <button
                className="btn-run-analysis"
                onClick={handleRunAudit}
                disabled={auditLoading || !effectiveResumeId || !jobDescText}
                title={
                  !effectiveResumeId ? 'Resume ID not available — try re-optimizing' :
                  !jobDescText ? 'Job description not available' :
                  'Checks each factual claim in your resume against the job description — flags vague or unsupported statements'
                }
              >
                {auditLoading ? (
                  <><span className="analysis-spinner" /> Auditing&hellip;</>
                ) : (
                  'Audit Claims'
                )}
              </button>
            )}
            {auditData && (
              <button
                className="btn-run-analysis btn-rerun"
                onClick={handleRunAudit}
                disabled={auditLoading}
                title="Re-run audit"
              >
                {auditLoading ? 'Re-auditing\u2026' : 'Re-audit'}
              </button>
            )}
          </div>
          {(auditLoading || auditData || auditError) && (
            <ClaimAuditPanel
              audits={auditData?.audits || []}
              summary={auditData?.summary || null}
              loading={auditLoading}
              error={auditError}
            />
          )}
        </div>
      </div>

      {/* Artifact Generation — Phase C */}
      <div className="alignment-analysis-section">
        <div className="alignment-section-header">
          <h3>Career Documents</h3>
        </div>
        <ArtifactPanel resumeId={effectiveResumeId} jobDescText={jobDescText} />
      </div>

      {accomplishments.length > 0 && (
        <div className="accomplishments-section">
          <h3>Matched Accomplishments</h3>
          <p className="section-desc">LinkedIn accomplishments relevant to this job description</p>
          <div className="accomplishment-list">
            {accomplishments.map((acc, idx) => (
              <div key={idx} className="accomplishment-item">
                <div className="accomplishment-text">{acc.text}</div>
                <div className="accomplishment-meta">
                  <span className="acc-source">{acc.source_company}</span>
                  <span className="acc-score">{acc.relevance_score}% match</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="recommendations-section">
          <h3>Relevant Recommendations</h3>
          <p className="section-desc">Professional endorsements that align with job requirements</p>
          <div className="recommendation-list">
            {recommendations.map((rec, idx) => (
              <div key={idx} className="recommendation-item">
                <blockquote className="rec-text">"{rec.text}"</blockquote>
                <div className="rec-meta">
                  <span className="rec-author">&mdash; {rec.author}</span>
                  {rec.relationship && <span className="rec-role">{rec.relationship}</span>}
                  <span className="rec-score">{rec.relevance_score}% match</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="resume-content">
        <div className="content-header">
          <h3>Optimized Resume</h3>
          <div className="download-buttons">
            {editingResume ? (
              <>
                <button onClick={handleSaveResumeEdit} className="btn-download btn-edit-save">
                  Save &amp; Re-score
                </button>
                <button onClick={handleCancelResumeEdit} className="btn-download btn-edit-cancel">
                  Cancel
                </button>
              </>
            ) : (
              <>
                <button onClick={handleStartResumeEdit} className="btn-download btn-edit-resume">
                  Edit
                </button>
                <button
                  onClick={() => handleDownload('pdf')}
                  className="btn-download btn-download-pdf"
                  disabled={!!downloadingFmt}
                >
                  {downloadingFmt === 'pdf' ? 'Generating...' : 'PDF'}
                </button>
                <button
                  onClick={() => handleDownload('docx')}
                  className="btn-download btn-download-docx"
                  disabled={!!downloadingFmt}
                >
                  {downloadingFmt === 'docx' ? 'Generating...' : 'DOCX'}
                </button>
                <button
                  onClick={() => handleDownload('txt')}
                  className="btn-download btn-download-txt"
                >
                  TXT
                </button>
              </>
            )}
          </div>
        </div>
        {editingResume ? (
          <textarea
            className="resume-edit-area"
            value={resumeEditDraft}
            onChange={e => setResumeEditDraft(e.target.value)}
          />
        ) : (
          <pre className="resume-text">{optimizedText}</pre>
        )}
      </div>

      <CollapsibleSection title="Compare with Expert AI" badge="LinkedIn AI / External">
        <ExpertComparison
          ourText={optimizedText}
          jobDescription={data?.job_description_text || jobDescTextFallback || ''}
        />
      </CollapsibleSection>

      <div className="tips-section">
        <h3>Next Steps</h3>
        <ul>
          <li>Review the optimized resume and make any necessary adjustments</li>
          <li>Ensure all added keywords are naturally integrated</li>
          <li>Proofread for grammar and formatting</li>
          <li>Save in multiple formats (PDF, DOCX) for different applications</li>
          <li>Customize further for specific company culture</li>
        </ul>
      </div>

      <div className="button-group">
        <button onClick={onStartOver} className="btn-primary">
          Optimize Another Resume
        </button>
      </div>
    </div>
  );
}

function BreakdownBar({ label, value, weight }) {
  const color = value >= 70 ? '#4caf50' : value >= 40 ? '#ff9800' : '#f44336';
  return (
    <div className="breakdown-bar-row">
      <div className="breakdown-bar-label">
        <span>{label}</span>
        <span className="breakdown-bar-weight">{weight}</span>
      </div>
      <div className="breakdown-bar-track">
        <div className="breakdown-bar-fill" style={{ width: `${value}%`, background: color }} />
      </div>
      <span className="breakdown-bar-value">{Math.round(value)}%</span>
    </div>
  );
}

export default OptimizedResumeView;
