import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';
import { saveChatHistoryFromServer } from '../utils/chatHistory';
import '../styles/ExperienceChat.css';

const STAGES = ['intro', 'role', 'responsibilities', 'technologies', 'outcomes', 'challenges', 'complete'];

function ExperienceChat({ onExperienceCreated }) {
  const [sessionId, setSessionId] = useState(null);
  const [stage, setStage] = useState('intro');
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [context, setContext] = useState({
    title: '', responsibilities: [], technologies: [], outcomes: [], challenges: [],
  });
  const [bulletPoints, setBulletPoints] = useState([]);
  const [showReview, setShowReview] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [finalized, setFinalized] = useState(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [uploadingContext, setUploadingContext] = useState(false);
  const [uploadedContextFiles, setUploadedContextFiles] = useState([]);

  // Start form state
  const [employer, setEmployer] = useState('');
  const [client, setClient] = useState('');

  const messagesEndRef = useRef(null);
  const contextFileRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleStart = async (e) => {
    e.preventDefault();
    if (!employer.trim()) return;
    try {
      const res = await api.startExperienceSession(employer.trim(), client.trim());
      setSessionId(res.session_id);
      setStage(res.stage);
      setMessages([{ id: Date.now(), role: 'assistant', text: res.message }]);
    } catch (err) {
      setMessages([{ id: Date.now(), role: 'assistant', text: 'Failed to start session. Please try again.' }]);
    }
  };

  const handleSend = async () => {
    if (!inputValue.trim() || !sessionId || sending) return;
    const text = inputValue.trim();
    setInputValue('');
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text }]);
    setSending(true);

    try {
      const res = await api.sendExperienceMessage(sessionId, text);
      setStage(res.stage);
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', text: res.message }]);

      if (res.context) {
        setContext({
          title: res.context.title || '',
          responsibilities: res.context.responsibilities || [],
          technologies: res.context.technologies || [],
          outcomes: res.context.outcomes || [],
          challenges: res.context.challenges || [],
        });
      }

      if (res.is_complete) {
        setIsComplete(true);
        // Fetch full summary for bullet points
        const summary = await api.getExperienceSummary(sessionId);
        setBulletPoints(summary.bullet_points || []);
        setContext({
          title: summary.title || '',
          responsibilities: summary.responsibilities || [],
          technologies: summary.technologies || [],
          outcomes: summary.outcomes || [],
          challenges: summary.challenges || [],
        });
      }
    } catch (err) {
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', text: 'Something went wrong. Please try again.' }]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleEditBullet = (idx, val) => {
    const next = [...bulletPoints];
    next[idx] = val;
    setBulletPoints(next);
  };

  const handleDeleteBullet = (idx) => {
    setBulletPoints(bulletPoints.filter((_, i) => i !== idx));
  };

  const handleMoveBullet = (idx, dir) => {
    const next = [...bulletPoints];
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= next.length) return;
    [next[idx], next[newIdx]] = [next[newIdx], next[idx]];
    setBulletPoints(next);
  };

  const handleFinalize = async () => {
    setFinalizing(true);
    try {
      const res = await api.finalizeExperience(sessionId, { bullet_points: bulletPoints });
      setFinalized(res);
      if (onExperienceCreated) onExperienceCreated(res.experience_id);
    } catch (err) {
      alert('Failed to finalize. Please try again.');
    } finally {
      setFinalizing(false);
    }
  };

  const handleApplyToResume = async () => {
    if (!sessionId) return;
    setApplying(true);
    try {
      const res = await api.applyExperience(sessionId);
      setApplied(true);
      if (onExperienceCreated) onExperienceCreated(res.resume_id);
    } catch (err) {
      alert('Failed to apply experience to resume.');
    } finally {
      setApplying(false);
    }
  };

  const handleUploadContext = async (file) => {
    if (!sessionId || !file) return;
    setUploadingContext(true);
    try {
      const res = await api.uploadExperienceContext(sessionId, file);
      setUploadedContextFiles(prev => [...prev, { name: file.name, fields: res.fields_updated || [] }]);
      // Add a system message about the upload
      setMessages(prev => [...prev, {
        id: Date.now(),
        role: 'assistant',
        text: `I've reviewed your uploaded document (${file.name}). ${
          res.fields_updated?.length
            ? `Found additional context for: ${res.fields_updated.join(', ')}.`
            : 'It will help me ask more targeted questions.'
        }`,
      }]);
      // Update context if fields were extracted
      if (res.fields_updated?.length) {
        const summary = await api.getExperienceSummary(sessionId);
        setContext({
          title: summary.title || context.title,
          responsibilities: summary.responsibilities || context.responsibilities,
          technologies: summary.technologies || context.technologies,
          outcomes: summary.outcomes || context.outcomes,
          challenges: summary.challenges || context.challenges,
        });
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now(),
        role: 'assistant',
        text: 'Failed to process the uploaded file. Please try a different format.',
      }]);
    } finally {
      setUploadingContext(false);
    }
  };

  const handleStartOver = () => {
    setSessionId(null);
    setStage('intro');
    setMessages([]);
    setInputValue('');
    setIsComplete(false);
    setContext({ title: '', responsibilities: [], technologies: [], outcomes: [], challenges: [] });
    setBulletPoints([]);
    setShowReview(false);
    setFinalized(null);
    setApplied(false);
    setUploadedContextFiles([]);
    setEmployer('');
    setClient('');
  };

  // Stage indicator
  const currentIdx = STAGES.indexOf(stage);
  const renderStages = () => (
    <div className="exp-stages">
      {STAGES.map((s, i) => (
        <div key={s} className={`exp-stage ${i < currentIdx ? 'done' : ''} ${i === currentIdx ? 'active' : ''}`}>
          <span className="exp-stage-dot">{i < currentIdx ? '\u2713' : i + 1}</span>
          <span className="exp-stage-label">{s}</span>
        </div>
      ))}
    </div>
  );

  // Finalized view
  if (finalized) {
    return (
      <div className="experience-chat">
        <div className="exp-finalized">
          <h2>Experience Saved</h2>
          <p>Your experience at <strong>{employer}</strong> has been finalized.</p>
          <ul className="exp-final-bullets">
            {finalized.bullet_points.map((bp, i) => <li key={i}>{bp}</li>)}
          </ul>
          <div className="exp-finalized-actions">
            {!applied ? (
              <button
                className="btn-apply-resume"
                onClick={handleApplyToResume}
                disabled={applying}
              >
                {applying ? 'Creating Resume...' : 'Apply to Resume'}
              </button>
            ) : (
              <span className="exp-applied-badge">Added to resume versions</span>
            )}
            <button
              className="btn-apply-resume"
              style={{ background: '#6366f1' }}
              onClick={async () => {
                try {
                  const res = await api.importExperienceToBuilder(finalized.experience_id);
                  alert(`Imported to Builder! Session: ${res.session_id?.slice(0, 8)}... Go to Resume Builder tab to continue.`);
                } catch (err) {
                  alert('Import failed: ' + (err?.response?.data?.error || err.message));
                }
              }}
            >
              Import to Builder
            </button>
            <button className="btn-primary" onClick={handleStartOver}>Add Another Experience</button>
          </div>
        </div>
      </div>
    );
  }

  // Start form (no session yet)
  if (!sessionId) {
    return (
      <div className="experience-chat">
        <h2>Experience Interview</h2>
        <p className="exp-subtitle">Tell us about a work experience and we'll help you create resume-ready bullet points.</p>
        <form onSubmit={handleStart} className="exp-start-form">
          <div className="form-group">
            <label>Employer *</label>
            <input
              value={employer} onChange={e => setEmployer(e.target.value)}
              placeholder="e.g., PwC, Google, Acme Corp"
              required
            />
          </div>
          <div className="form-group">
            <label>Client (optional)</label>
            <input
              value={client} onChange={e => setClient(e.target.value)}
              placeholder="e.g., Major Bank, Internal project"
            />
          </div>
          <button type="submit" className="btn-primary" disabled={!employer.trim()}>
            Start Interview
          </button>
        </form>
      </div>
    );
  }

  // Review mode
  if (showReview || (isComplete && !showReview)) {
    // Auto-show review when complete
  }

  return (
    <div className="experience-chat">
      <div className="experience-chat-title-row">
        <h2>Experience Interview &mdash; {employer}{client ? ` / ${client}` : ''}</h2>
        {sessionId && messages.length > 0 && (
          <button
            className="btn-save-history"
            onClick={() => saveChatHistoryFromServer(api, 'experience', sessionId)}
            title="Save chat history"
          >
            Save History
          </button>
        )}
      </div>
      {renderStages()}

      <div className="exp-layout">
        {/* Chat Panel */}
        <div className="exp-chat-panel">
          <div className="exp-messages">
            {messages.map(msg => (
              <div key={msg.id} className={`exp-message exp-message-${msg.role}`}>
                <div className="exp-bubble">{msg.text}</div>
              </div>
            ))}
            {sending && (
              <div className="exp-message exp-message-assistant">
                <div className="exp-bubble exp-typing">Thinking...</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {!isComplete ? (
            <div className="exp-input-area">
              <div className="exp-input-row">
                <input
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your response..."
                  disabled={sending}
                />
                <button onClick={handleSend} disabled={!inputValue.trim() || sending} className="btn-send">
                  Send
                </button>
              </div>
              <div className="exp-context-upload">
                <input
                  ref={contextFileRef}
                  type="file"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleUploadContext(f);
                    e.target.value = '';
                  }}
                  accept=".json,.xml,.docx,.doc,.pdf,.txt"
                  className="hidden"
                />
                <button
                  className="btn-upload-context"
                  onClick={() => contextFileRef.current?.click()}
                  disabled={uploadingContext || sending}
                  title="Upload a document to provide additional context (interview transcript, notes, etc.)"
                >
                  {uploadingContext ? 'Processing...' : 'Upload Context Document'}
                </button>
                {uploadedContextFiles.length > 0 && (
                  <span className="uploaded-count">
                    {uploadedContextFiles.length} document(s) uploaded
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="exp-complete-bar">
              <span>Interview complete!</span>
              <button className="btn-primary" onClick={() => setShowReview(true)}>
                Review & Finalize
              </button>
            </div>
          )}
        </div>

        {/* Sidebar: extracted data */}
        <div className="exp-sidebar">
          <h3>Extracted Data</h3>

          {context.title && (
            <div className="exp-field">
              <label>Title</label>
              <div className="exp-field-value">{context.title}</div>
            </div>
          )}

          {context.responsibilities.length > 0 && (
            <div className="exp-field">
              <label>Responsibilities ({context.responsibilities.length})</label>
              <ul>{context.responsibilities.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          )}

          {context.technologies.length > 0 && (
            <div className="exp-field">
              <label>Technologies ({context.technologies.length})</label>
              <div className="exp-tags">
                {context.technologies.map((t, i) => <span key={i} className="exp-tag">{t}</span>)}
              </div>
            </div>
          )}

          {context.outcomes.length > 0 && (
            <div className="exp-field">
              <label>Outcomes ({context.outcomes.length})</label>
              <ul>{context.outcomes.map((o, i) => <li key={i}>{o}</li>)}</ul>
            </div>
          )}

          {context.challenges.length > 0 && (
            <div className="exp-field">
              <label>Challenges ({context.challenges.length})</label>
              <ul>{context.challenges.map((c, i) => <li key={i}>{c}</li>)}</ul>
            </div>
          )}

          {!context.title && context.responsibilities.length === 0 && (
            <p className="exp-empty-sidebar">Data will appear here as you answer questions.</p>
          )}
        </div>
      </div>

      {/* Review Panel */}
      {showReview && (
        <div className="exp-review">
          <h3>Review Bullet Points</h3>
          <p>Edit, reorder, or remove bullet points before saving.</p>
          <div className="exp-bullet-list">
            {bulletPoints.map((bp, i) => (
              <div key={i} className="exp-bullet-row">
                <div className="exp-bullet-controls">
                  <button onClick={() => handleMoveBullet(i, -1)} disabled={i === 0} title="Move up">&uarr;</button>
                  <button onClick={() => handleMoveBullet(i, 1)} disabled={i === bulletPoints.length - 1} title="Move down">&darr;</button>
                </div>
                <input
                  value={bp}
                  onChange={e => handleEditBullet(i, e.target.value)}
                  className="exp-bullet-input"
                />
                <button onClick={() => handleDeleteBullet(i)} className="btn-delete-bullet" title="Remove">&times;</button>
              </div>
            ))}
          </div>
          <div className="exp-review-actions">
            <button onClick={() => setBulletPoints([...bulletPoints, ''])} className="btn-add-bullet">
              + Add Bullet
            </button>
            <button onClick={handleFinalize} disabled={finalizing} className="btn-finalize">
              {finalizing ? 'Saving...' : 'Finalize & Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ExperienceChat;
