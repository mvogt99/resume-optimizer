import React, { useState, useRef, useEffect } from 'react';
import api from '../services/api';
import { saveChatHistoryFromServer } from '../utils/chatHistory';
import '../styles/ResumeInterview.css';

const STAGE_LABELS = ['Welcome', 'Contact', 'Objective', 'Experience', 'Education', 'Skills', 'Optional', 'Review'];
const STAGE_IDS = ['welcome', 'contact', 'objective', 'experience', 'education', 'skills', 'optional', 'review'];

function ResumeInterview({ onComplete }) {
  const [sessionId, setSessionId] = useState(null);
  const [stage, setStage] = useState('welcome');
  const [subStage, setSubStage] = useState('');
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [context, setContext] = useState({});
  const [progress, setProgress] = useState({ stage_index: 0, total_stages: 8 });
  const [showFinalize, setShowFinalize] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [finalized, setFinalized] = useState(null);
  const [previewText, setPreviewText] = useState('');
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [started, setStarted] = useState(false);
  const [startError, setStartError] = useState('');

  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load preview whenever we enter review stage
  useEffect(() => {
    if (stage === 'review' && sessionId && !previewText) {
      loadPreview();
    }
  }, [stage, sessionId]); // eslint-disable-line

  const loadPreview = async () => {
    if (!sessionId) return;
    setLoadingPreview(true);
    try {
      const res = await api.previewResumeInterview(sessionId);
      setPreviewText(res.compiled_text || '');
    } catch {
      // preview unavailable, show raw context
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleStart = async () => {
    setStartError('');
    try {
      const res = await api.startResumeInterview();
      setSessionId(res.session_id);
      setStage(res.stage || 'welcome');
      setSubStage(res.sub_stage || '');
      setProgress(res.progress || { stage_index: 0, total_stages: 8 });
      setMessages([{ id: Date.now(), role: 'assistant', text: res.message }]);
      setStarted(true);
    } catch (err) {
      setStartError('Could not start the interview. Please try again.');
    }
  };

  const handleSend = async () => {
    if (!inputValue.trim() || !sessionId || sending) return;
    const text = inputValue.trim();
    setInputValue('');
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text }]);
    setSending(true);

    try {
      const res = await api.sendResumeInterviewMessage(sessionId, text);
      setStage(res.stage || stage);
      setSubStage(res.sub_stage || '');
      setContext(res.context || {});
      setProgress(res.progress || progress);
      setShowFinalize(!!res.show_finalize);
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', text: res.message }]);
    } catch {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        text: "I'm sorry, something went wrong. Please try again.",
      }]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Quick-action buttons for experience loop choices
  const handleQuickAction = (text) => {
    setInputValue(text);
    setTimeout(() => handleSend(), 50);
  };

  const handleFinalize = async () => {
    if (!sessionId || finalizing) return;
    setFinalizing(true);
    try {
      const res = await api.finalizeResumeInterview(sessionId, {});
      setFinalized(res);
      if (onComplete && res.version_id) {
        onComplete(res.version_id);
      }
    } catch {
      setMessages(prev => [...prev, {
        id: Date.now(),
        role: 'assistant',
        text: "There was a problem saving your resume. Please try again.",
      }]);
    } finally {
      setFinalizing(false);
    }
  };

  const currentStageIdx = STAGE_IDS.indexOf(stage);

  if (!started) {
    return (
      <div className="resume-interview-container">
        <div style={{ maxWidth: 600, margin: '40px auto', textAlign: 'center', padding: '30px' }}>
          <h2 style={{ color: '#1976D2', marginBottom: 16 }}>Build Your Resume from Scratch</h2>
          <p style={{ color: '#555', fontSize: 15, lineHeight: 1.6, marginBottom: 24 }}>
            No resume? No problem. I'll walk you through a guided interview — about 10 minutes —
            and we'll build a professional resume together, step by step.
          </p>
          <p style={{ color: '#777', fontSize: 13, marginBottom: 30 }}>
            Works for any career: teaching, healthcare, trades, retail, and more.
          </p>
          {startError && (
            <div style={{ color: '#c62828', marginBottom: 16 }}>{startError}</div>
          )}
          <button
            onClick={handleStart}
            style={{
              padding: '14px 36px',
              background: '#1976D2',
              color: 'white',
              border: 'none',
              borderRadius: 8,
              fontSize: 16,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Start Building My Resume
          </button>
        </div>
      </div>
    );
  }

  if (finalized) {
    return (
      <div className="resume-interview-container">
        <div style={{ maxWidth: 600, margin: '40px auto', textAlign: 'center', padding: '30px' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
          <h2 style={{ color: '#2E7D32', marginBottom: 12 }}>Your Resume is Saved!</h2>
          <p style={{ color: '#555', marginBottom: 24 }}>
            <strong>{finalized.file_name}</strong> has been saved to your account.
          </p>
          <p style={{ color: '#777', fontSize: 13, marginBottom: 30 }}>
            You can now optimize it against a job description in the Optimize tab,
            or make further edits in the Resume Builder.
          </p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
            <button
              onClick={() => onComplete && onComplete(finalized.version_id)}
              style={{
                padding: '12px 28px',
                background: '#1976D2',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Optimize for a Job
            </button>
            <button
              onClick={() => {
                setStarted(false);
                setSessionId(null);
                setMessages([]);
                setStage('welcome');
                setFinalized(null);
                setPreviewText('');
              }}
              style={{
                padding: '12px 28px',
                background: 'white',
                color: '#666',
                border: '1px solid #ddd',
                borderRadius: 6,
                cursor: 'pointer',
              }}
            >
              Start Another Resume
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="resume-interview-container">
      {/* Progress bar */}
      <div className="ri-progress-bar">
        {STAGE_LABELS.map((label, idx) => (
          <div key={label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div
              className={`ri-progress-dot ${idx === currentStageIdx ? 'current' : ''} ${idx < currentStageIdx ? 'completed' : ''}`}
            >
              {idx < currentStageIdx ? '✓' : idx + 1}
            </div>
            <div className="ri-progress-label">{label}</div>
          </div>
        ))}
      </div>

      {/* Main content */}
      <div className="ri-content">
        {/* Chat panel */}
        <div className="ri-chat-panel">
          {sessionId && messages.length > 0 && (
            <div className="ri-chat-toolbar">
              <button
                className="btn-save-history"
                onClick={() => saveChatHistoryFromServer(api, 'resume_interview', sessionId)}
                title="Save chat history"
              >
                Save History
              </button>
            </div>
          )}
          <div className="ri-messages">
            {messages.map(msg => (
              <div key={msg.id} className={`ri-message ${msg.role}`}>
                <div className="ri-bubble" style={{ whiteSpace: 'pre-wrap' }}>
                  {msg.text}
                </div>
              </div>
            ))}
            {sending && (
              <div className="ri-message ai">
                <div className="ri-bubble">
                  <div className="ri-loading">
                    <div className="ri-loading-dot" />
                    <div className="ri-loading-dot" />
                    <div className="ri-loading-dot" />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick-action buttons for experience/education loops */}
          {subStage === 'exp_another' && (
            <div className="ri-action-buttons">
              <button className="ri-action-btn primary" onClick={() => handleQuickAction('yes')}>
                + Add Another Job
              </button>
              <button className="ri-action-btn" onClick={() => handleQuickAction('no')}>
                That's All My Jobs →
              </button>
            </div>
          )}
          {subStage === 'edu_more' && (
            <div className="ri-action-buttons">
              <button className="ri-action-btn primary" onClick={() => handleQuickAction('yes')}>
                + Add Another Degree
              </button>
              <button className="ri-action-btn" onClick={() => handleQuickAction('no')}>
                Continue →
              </button>
            </div>
          )}
          {subStage === 'exp_more' && (
            <div className="ri-action-buttons">
              <button className="ri-action-btn" onClick={() => handleQuickAction('next')}>
                Done with this job →
              </button>
            </div>
          )}

          {/* Input */}
          {stage !== 'complete' && (
            <div className="ri-input-area">
              <input
                type="text"
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={stage === 'review' ? "Tell me what to change, or click Finalize & Save…" : "Type your answer…"}
                disabled={sending}
                autoFocus
              />
              <button onClick={handleSend} disabled={!inputValue.trim() || sending}>
                Send
              </button>
            </div>
          )}

          {/* Finalize button */}
          {showFinalize && !finalized && (
            <div className="ri-finalize-area">
              <button
                className="ri-finalize-btn secondary"
                onClick={loadPreview}
                disabled={loadingPreview}
              >
                {loadingPreview ? 'Loading…' : 'Refresh Preview'}
              </button>
              <button
                className="ri-finalize-btn primary"
                onClick={handleFinalize}
                disabled={finalizing}
              >
                {finalizing ? 'Saving…' : 'Finalize & Save Resume'}
              </button>
            </div>
          )}
        </div>

        {/* Sidebar — shows context / preview */}
        <div className="ri-sidebar">
          {stage === 'review' ? (
            <ReviewSidebar previewText={previewText} loading={loadingPreview} />
          ) : (
            <ContextSidebar stage={stage} context={context} />
          )}
        </div>
      </div>
    </div>
  );
}

function ContextSidebar({ stage, context }) {
  const experiences = context.experiences || [];
  const education = context.education || [];

  return (
    <>
      <div className="ri-sidebar-title">What We've Collected</div>

      {context.name && (
        <div style={{ marginBottom: 12, fontSize: 13 }}>
          <strong>{context.preferred_name || context.name}</strong>
          {context.email && <div style={{ color: '#666' }}>{context.email}</div>}
          {context.phone && <div style={{ color: '#666' }}>{context.phone}</div>}
          {context.location && <div style={{ color: '#666' }}>{context.location}</div>}
        </div>
      )}

      {context.career_field && (
        <div style={{ marginBottom: 12, fontSize: 13 }}>
          <strong>Field:</strong> {context.career_field}
          {context.years_experience && ` (${context.years_experience} years)`}
        </div>
      )}

      {experiences.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#555', marginBottom: 6 }}>
            EXPERIENCE ({experiences.length} job{experiences.length !== 1 ? 's' : ''})
          </div>
          {experiences.map((exp, i) => (
            <div key={i} className="ri-job-card">
              <div className="ri-job-card-title">{exp.title || '(title pending)'}</div>
              <div className="ri-job-card-company">{exp.employer}</div>
              {exp.start_date && (
                <div className="ri-job-card-dates">
                  {exp.start_date} – {exp.end_date || 'Present'}
                </div>
              )}
              {exp.duties && exp.duties.length > 0 && (
                <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                  {exp.duties.length} bullet{exp.duties.length !== 1 ? 's' : ''} added
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {education.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#555', marginBottom: 6 }}>
            EDUCATION
          </div>
          {education.map((edu, i) => (
            <div key={i} className="ri-job-card">
              <div className="ri-job-card-title">{edu.degree || '(degree pending)'}</div>
              <div className="ri-job-card-company">{edu.school}</div>
              {edu.year && <div className="ri-job-card-dates">{edu.year}</div>}
            </div>
          ))}
        </div>
      )}

      {(context.hard_skills?.length > 0 || context.soft_skills?.length > 0 || context.certifications?.length > 0) && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#555', marginBottom: 6 }}>SKILLS</div>
          <div style={{ fontSize: 12, color: '#666', lineHeight: 1.6 }}>
            {[...context.certifications || [], ...context.hard_skills || [], ...context.soft_skills || []].join(', ')}
          </div>
        </div>
      )}

      {!context.name && (
        <div style={{ color: '#aaa', fontSize: 13, textAlign: 'center', marginTop: 20 }}>
          Your information will appear here as we chat.
        </div>
      )}
    </>
  );
}

function ReviewSidebar({ previewText, loading }) {
  return (
    <>
      <div className="ri-sidebar-title">Resume Preview</div>
      {loading ? (
        <div style={{ color: '#aaa', fontSize: 13 }}>Loading preview…</div>
      ) : previewText ? (
        <div className="ri-resume-preview">{previewText}</div>
      ) : (
        <div style={{ color: '#aaa', fontSize: 13 }}>
          Click "Refresh Preview" to see your compiled resume.
        </div>
      )}
    </>
  );
}

export default ResumeInterview;
