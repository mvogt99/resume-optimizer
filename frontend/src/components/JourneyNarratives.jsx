import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';
import '../styles/JourneyMiner.css';

const NARRATIVE_TABS = [
  { key: 'resume_entry', label: 'Resume Entries' },
  { key: 'linkedin', label: 'LinkedIn Sections' },
  { key: 'campaign_seed', label: 'Campaign Seeds' },
];

function JourneyNarratives({ onApproved }) {
  const [narratives, setNarratives] = useState([]);
  const [activeTab, setActiveTab] = useState('resume_entry');
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Narrative interview state
  const [interviewSessionId, setInterviewSessionId] = useState(null);
  const [interviewMessages, setInterviewMessages] = useState([]);
  const [interviewInput, setInterviewInput] = useState('');
  const [interviewLoading, setInterviewLoading] = useState(false);
  const [interviewComplete, setInterviewComplete] = useState(false);
  // Per-narrative discussion
  const [discussingId, setDiscussingId] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadNarratives();
  }, []);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [interviewMessages]);

  const loadNarratives = async () => {
    setLoading(true);
    try {
      const data = await api.getJourneyNarratives();
      setNarratives(data.narratives || []);
    } catch {
      // empty
    } finally {
      setLoading(false);
    }
  };

  const filtered = narratives.filter(n => {
    if (activeTab === 'linkedin') {
      return n.narrative_type.startsWith('linkedin');
    }
    return n.narrative_type === activeTab;
  });

  const startEdit = (narrative) => {
    setEditingId(narrative.id);
    setEditText(narrative.content);
  };

  const saveEdit = async (id) => {
    try {
      await api.updateJourneyNarratives([{ id, content: editText }]);
      setEditingId(null);
      loadNarratives();
    } catch (err) {
      setError('Failed to save');
    }
  };

  const approveAll = async () => {
    try {
      await api.approveJourneyNarratives();
      loadNarratives();
      if (onApproved) onApproved();
    } catch (err) {
      setError('Failed to approve');
    }
  };

  const approveOne = async (id) => {
    try {
      await api.approveJourneyNarratives([id]);
      loadNarratives();
      if (onApproved) onApproved();
    } catch (err) {
      setError('Failed to approve');
    }
  };

  // --- Narrative interview handlers ---

  const startNarrativeInterview = async () => {
    setInterviewLoading(true);
    setInterviewComplete(false);
    setInterviewMessages([]);
    setDiscussingId(null);
    try {
      const data = await api.startJourneyReview('narrative');
      setInterviewSessionId(data.session_id);
      setInterviewMessages([{ role: 'assistant', content: data.message }]);
    } catch (err) {
      setError('Failed to start narrative interview');
    } finally {
      setInterviewLoading(false);
    }
  };

  const startDiscussion = async (narrative) => {
    setDiscussingId(narrative.id);
    setInterviewLoading(true);
    setInterviewComplete(false);
    setInterviewMessages([]);
    try {
      const data = await api.startJourneyReview('narrative');
      setInterviewSessionId(data.session_id);
      // Send initial context about this narrative
      const contextMsg = `I want to refine this narrative: "${narrative.content}"`;
      setInterviewMessages([{ role: 'assistant', content: data.message }]);
      const resp = await api.sendJourneyReviewMessage(data.session_id, contextMsg);
      setInterviewMessages([
        { role: 'assistant', content: data.message },
        { role: 'user', content: contextMsg },
        { role: 'assistant', content: resp.message },
      ]);
    } catch (err) {
      setError('Failed to start discussion');
    } finally {
      setInterviewLoading(false);
    }
  };

  const sendInterviewMessage = async () => {
    if (!interviewInput.trim() || interviewLoading) return;
    const msg = interviewInput.trim();
    setInterviewInput('');
    setInterviewMessages(prev => [...prev, { role: 'user', content: msg }]);
    setInterviewLoading(true);
    try {
      const data = await api.sendJourneyReviewMessage(interviewSessionId, msg);
      setInterviewMessages(prev => [...prev, { role: 'assistant', content: data.message }]);
      if (data.is_complete) setInterviewComplete(true);
    } catch (err) {
      setError('Failed to send message');
    } finally {
      setInterviewLoading(false);
    }
  };

  const applyInterview = async () => {
    setInterviewLoading(true);
    try {
      await api.applyJourneyReviewChanges(interviewSessionId);
      setInterviewSessionId(null);
      setInterviewMessages([]);
      setInterviewComplete(false);
      setDiscussingId(null);
      loadNarratives();
      if (onApproved) onApproved();
    } catch (err) {
      setError('Failed to apply');
    } finally {
      setInterviewLoading(false);
    }
  };

  const closeInterview = () => {
    setInterviewSessionId(null);
    setInterviewMessages([]);
    setInterviewComplete(false);
    setDiscussingId(null);
  };

  const renderContent = (narrative) => {
    // Campaign seeds are stored as JSON
    if (narrative.narrative_type === 'campaign_seed') {
      try {
        const data = JSON.parse(narrative.content);
        return (
          <div>
            <p><strong>{data.theme}</strong></p>
            <p>{data.description}</p>
            {data.post_angles && (
              <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                {data.post_angles.map((angle, i) => (
                  <li key={i} style={{ marginBottom: '4px', color: '#555' }}>{angle}</li>
                ))}
              </ul>
            )}
            {data.target_audience && (
              <p style={{ fontSize: '12px', color: '#888' }}>
                Audience: {data.target_audience}
              </p>
            )}
          </div>
        );
      } catch {
        return <p>{narrative.content}</p>;
      }
    }
    return <p>{narrative.content}</p>;
  };

  const renderInterviewPanel = () => {
    if (!interviewSessionId) return null;
    return (
      <div className="narrative-interview-panel">
        <div className="journey-review-header">
          <h4>{discussingId ? 'Refine Narrative' : 'Build Narratives with AI'}</h4>
          <button onClick={closeInterview}>&times;</button>
        </div>
        <div className="journey-chat-messages">
          {interviewMessages.map((m, i) => (
            <div key={i} className={`journey-chat-msg ${m.role}`}>
              {m.content}
            </div>
          ))}
          {interviewLoading && <div className="journey-chat-msg assistant">Thinking...</div>}
          <div ref={messagesEndRef} />
        </div>
        <div className="journey-chat-input-row">
          <input
            type="text"
            value={interviewInput}
            onChange={e => setInterviewInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendInterviewMessage()}
            placeholder="Describe your goals, preferences..."
            disabled={interviewLoading}
          />
          <button onClick={sendInterviewMessage} disabled={interviewLoading || !interviewInput.trim()}>
            Send
          </button>
          {interviewComplete && (
            <button className="journey-btn journey-btn-approve" onClick={applyInterview} disabled={interviewLoading}>
              Apply & Save
            </button>
          )}
        </div>
      </div>
    );
  };

  if (loading) {
    return <div className="journey-empty"><p>Loading narratives...</p></div>;
  }

  if (narratives.length === 0 && !interviewSessionId) {
    return (
      <div className="journey-empty">
        <h3>No narratives generated yet</h3>
        <p>Build narratives with AI assistance, or run mining to auto-generate them.</p>
        <button className="journey-btn journey-btn-approve" onClick={startNarrativeInterview}>
          Build Narratives with AI
        </button>
        {renderInterviewPanel()}
      </div>
    );
  }

  const hasUnapproved = narratives.some(n => !n.approved);

  return (
    <div>
      {error && (
        <div className="error-banner">
          {error}
          <button onClick={() => setError('')}>x</button>
        </div>
      )}

      {/* Interview panel (top) */}
      {renderInterviewPanel()}

      {/* Build/Refine button */}
      {!interviewSessionId && (
        <div style={{ marginBottom: '12px' }}>
          <button className="journey-btn journey-btn-secondary" onClick={startNarrativeInterview}>
            {narratives.length > 0 ? 'Refine with AI' : 'Build Narratives with AI'}
          </button>
        </div>
      )}

      {/* Narrative type tabs */}
      <div className="journey-narrative-tabs">
        {NARRATIVE_TABS.map(tab => (
          <button
            key={tab.key}
            className={`journey-narr-tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Narrative cards */}
      {filtered.length === 0 ? (
        <div className="journey-empty">
          <p>No {NARRATIVE_TABS.find(t => t.key === activeTab)?.label.toLowerCase()} yet.</p>
        </div>
      ) : (
        filtered.map(narrative => (
          <div key={narrative.id} className="journey-narrative-card">
            <div className="journey-narrative-header">
              <h4>
                {narrative.title || narrative.narrative_type}
                {narrative.approved === 1 && (
                  <span className="proj-status-badge completed" style={{ marginLeft: '8px', fontSize: '10px' }}>
                    Approved
                  </span>
                )}
              </h4>
              <div style={{ display: 'flex', gap: '6px' }}>
                {!interviewSessionId && (
                  <button
                    className="journey-btn journey-btn-secondary"
                    onClick={() => startDiscussion(narrative)}
                    style={{ fontSize: '11px', padding: '4px 8px' }}
                  >
                    Discuss
                  </button>
                )}
                {editingId !== narrative.id && (
                  <button
                    className="journey-btn journey-btn-secondary"
                    onClick={() => startEdit(narrative)}
                  >
                    Edit
                  </button>
                )}
                {!narrative.approved && (
                  <button
                    className="journey-btn journey-btn-approve"
                    onClick={() => approveOne(narrative.id)}
                  >
                    Approve
                  </button>
                )}
              </div>
            </div>

            <div className="journey-narrative-content">
              {editingId === narrative.id ? (
                <>
                  <textarea
                    value={editText}
                    onChange={e => setEditText(e.target.value)}
                  />
                  <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                    <button
                      className="journey-btn journey-btn-secondary"
                      onClick={() => setEditingId(null)}
                    >
                      Cancel
                    </button>
                    <button
                      className="journey-btn journey-btn-approve"
                      onClick={() => saveEdit(narrative.id)}
                    >
                      Save
                    </button>
                  </div>
                </>
              ) : (
                renderContent(narrative)
              )}
            </div>
          </div>
        ))
      )}

      {/* Approve all bar */}
      {hasUnapproved && (
        <div className="journey-approve-bar">
          <button className="journey-btn journey-btn-approve" onClick={approveAll}>
            Approve All & Store in Knowledge Graph
          </button>
        </div>
      )}
    </div>
  );
}

export default JourneyNarratives;
