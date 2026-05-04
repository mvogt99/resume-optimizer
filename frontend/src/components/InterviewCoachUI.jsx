import React, { useState, useEffect, useCallback, useRef } from 'react';
import api from '../services/api';

const PERSONAS = [
  { value: 'hiring_manager', label: 'Hiring Manager' },
  { value: 'technical', label: 'Technical Interviewer' },
  { value: 'hr_recruiter', label: 'HR Recruiter' },
  { value: 'executive', label: 'Executive' },
];

function InterviewCoachUI() {
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [userInput, setUserInput] = useState('');
  const [persona, setPersona] = useState('hiring_manager');
  const [questionCount, setQuestionCount] = useState(5);
  const [showConfig, setShowConfig] = useState(false);
  const [assessment, setAssessment] = useState(null);
  const [prepSheet, setPrepSheet] = useState(null);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadSessions = useCallback(async () => {
    try {
      const res = await api.coachListSessions();
      setSessions(res.sessions || []);
    } catch (err) {
      setError('Failed to load sessions.');
    }
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.coachStart(null, persona, questionCount);
      setActiveSession(res);
      setMessages([{ id: Date.now(), role: 'assistant', text: res.question || res.message }]);
      setAssessment(null);
      setShowConfig(false);
    } catch (err) {
      setError('Failed to start session.');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!userInput.trim() || !activeSession || loading) return;
    const text = userInput.trim();
    setUserInput('');
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text }]);
    setLoading(true);
    try {
      const res = await api.coachAnswer(activeSession.session_id, text);
      setMessages(prev => [...prev, {
        id: Date.now() + 1, role: 'assistant',
        text: res.feedback ? `${res.feedback}\n\n${res.question || ''}` : res.question || res.message,
      }]);
      if (res.assessment) {
        setAssessment(res.assessment);
      }
    } catch (err) {
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', text: 'Something went wrong.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleLoadSession = async (sessionId) => {
    setLoading(true);
    try {
      const res = await api.coachGetSession(sessionId);
      setActiveSession(res);
      setMessages((res.messages || []).map((m, i) => ({ id: i, role: m.role, text: m.text || m.content })));
      if (res.assessment) setAssessment(res.assessment);
    } catch (err) {
      setError('Failed to load session.');
    } finally {
      setLoading(false);
    }
  };

  const handlePrepSheet = async () => {
    setLoading(true);
    try {
      const res = await api.generatePrepSheet(activeSession?.posting_id || '');
      setPrepSheet(res);
    } catch (err) {
      setError('Failed to generate prep sheet.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="coach-container">
      <div className="coach-layout">
        {/* Sidebar */}
        <div className="coach-sidebar">
          <h3>Sessions</h3>
          <button className="btn-primary" onClick={() => setShowConfig(true)} disabled={loading}>
            New Session
          </button>
          <div className="coach-session-list">
            {sessions.map(s => (
              <div key={s.session_id} className={`coach-session-item ${activeSession?.session_id === s.session_id ? 'active' : ''}`}
                onClick={() => handleLoadSession(s.session_id)}>
                <span className="coach-session-persona">{s.persona || 'interview'}</span>
                <span className={`coach-session-status ${s.is_complete ? 'complete' : 'in-progress'}`}>
                  {s.is_complete ? 'Complete' : 'In Progress'}
                </span>
              </div>
            ))}
            {sessions.length === 0 && <p className="coach-empty">No sessions yet.</p>}
          </div>
        </div>

        {/* Main */}
        <div className="coach-main">
          {error && <div className="coach-error">{error}</div>}

          {showConfig && !activeSession && (
            <div className="coach-config">
              <h3>Configure Mock Interview</h3>
              <div className="form-group">
                <label>Interviewer Persona</label>
                <select value={persona} onChange={e => setPersona(e.target.value)}>
                  {PERSONAS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Questions: {questionCount}</label>
                <input type="range" min="5" max="15" value={questionCount}
                  onChange={e => setQuestionCount(Number(e.target.value))} />
              </div>
              <button className="btn-primary" onClick={handleStart} disabled={loading}>
                {loading ? 'Starting...' : 'Start Interview'}
              </button>
            </div>
          )}

          {activeSession && !assessment && (
            <>
              <div className="coach-messages">
                {messages.map(msg => (
                  <div key={msg.id} className={`exp-message exp-message-${msg.role}`}>
                    <div className="exp-bubble">{msg.text}</div>
                  </div>
                ))}
                {loading && <div className="exp-message exp-message-assistant"><div className="exp-bubble exp-typing">Thinking...</div></div>}
                <div ref={messagesEndRef} />
              </div>
              <div className="exp-input-row">
                <input value={userInput} onChange={e => setUserInput(e.target.value)}
                  onKeyPress={handleKeyPress} placeholder="Type your answer..." disabled={loading} />
                <button onClick={handleSend} disabled={!userInput.trim() || loading} className="btn-send">Send</button>
              </div>
            </>
          )}

          {assessment && (
            <div className="coach-assessment">
              <h3>Interview Assessment</h3>
              <div className="coach-score-grid">
                {Object.entries(assessment.scores || assessment).filter(([k]) => k !== 'strengths' && k !== 'improvements' && k !== 'overall').map(([key, val]) => (
                  <div key={key} className="coach-score-card">
                    <span className="coach-score-label">{key}</span>
                    <span className="coach-score-value">{typeof val === 'number' ? `${val}/10` : val}</span>
                  </div>
                ))}
              </div>
              {assessment.strengths && (
                <div className="coach-feedback-section">
                  <h4>Strengths</h4>
                  <ul>{(Array.isArray(assessment.strengths) ? assessment.strengths : [assessment.strengths]).map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
              {assessment.improvements && (
                <div className="coach-feedback-section">
                  <h4>Areas for Improvement</h4>
                  <ul>{(Array.isArray(assessment.improvements) ? assessment.improvements : [assessment.improvements]).map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
              <div className="coach-assessment-actions">
                <button className="btn-primary" onClick={handlePrepSheet} disabled={loading}>
                  {loading ? 'Generating...' : 'Get Prep Sheet'}
                </button>
                <button className="btn-primary" onClick={() => { setActiveSession(null); setAssessment(null); setMessages([]); loadSessions(); }}>
                  Back to Sessions
                </button>
              </div>
            </div>
          )}

          {prepSheet && (
            <div className="coach-prep-sheet">
              <h3>Preparation Sheet</h3>
              <pre className="coach-prep-content">{typeof prepSheet === 'string' ? prepSheet : JSON.stringify(prepSheet, null, 2)}</pre>
              <button className="btn-primary" onClick={() => setPrepSheet(null)}>Close</button>
            </div>
          )}

          {!showConfig && !activeSession && !assessment && (
            <div className="coach-empty-main">
              <h3>Interview Coach</h3>
              <p>Practice mock interviews with AI personas. Select a past session or start a new one.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default InterviewCoachUI;
