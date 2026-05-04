import React, { useState, useEffect, useRef, useCallback } from 'react';
import api from '../services/api';
import { saveChatHistoryFromServer } from '../utils/chatHistory';

const PERSONAS = [
  { id: 'hiring_manager', label: 'Hiring Manager' },
  { id: 'technical', label: 'Technical' },
  { id: 'hr_recruiter', label: 'HR Recruiter' },
  { id: 'executive', label: 'Executive' },
];

function InterviewCoach({ initialPostingId }) {
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [assessment, setAssessment] = useState(null);
  const [postingId, setPostingId] = useState(initialPostingId || '');
  const [persona, setPersona] = useState('hiring_manager');
  const [questionCount, setQuestionCount] = useState(5);
  const [postings, setPostings] = useState([]);
  const [prepSheet, setPrepSheet] = useState(null);
  const [prepLoading, setPrepLoading] = useState(null);
  const messagesEnd = useRef(null);

  const loadSessions = useCallback(async () => {
    try {
      const data = await api.coachListSessions();
      setSessions(data.sessions || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadSessions();
    api.scoutListPostings(null, 0, 20).then(d => setPostings(d.postings || [])).catch(() => {});
  }, [loadSessions]);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleStart = async () => {
    setStarting(true);
    try {
      const data = await api.coachStart(postingId, persona, questionCount);
      setActiveSession(data.session_id);
      setMessages([
        { role: 'assistant', content: data.message },
        { role: 'assistant', content: data.question },
      ]);
      setAssessment(null);
      loadSessions();
    } catch (err) {
      alert(err?.response?.data?.error || 'Failed to start session');
    } finally {
      setStarting(false);
    }
  };

  const handleSubmitAnswer = async () => {
    if (!answer.trim() || !activeSession) return;
    setLoading(true);

    const userMsg = { role: 'user', content: answer };
    setMessages(prev => [...prev, userMsg]);
    setAnswer('');

    try {
      const data = await api.coachAnswer(activeSession, answer);

      if (data.score) {
        const scoreMsg = {
          role: 'system',
          content: formatScore(data.score),
          score: data.score,
        };
        setMessages(prev => [...prev, scoreMsg]);
      }

      if (data.is_complete) {
        setAssessment(data.assessment);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Interview complete! Check your assessment below.',
        }]);
      } else if (data.next_question) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.next_question,
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'system',
        content: 'Error submitting answer. Please try again.',
      }]);
    } finally {
      setLoading(false);
    }
  };

  const loadSession = async (sessionId) => {
    try {
      const data = await api.coachGetSession(sessionId);
      setActiveSession(sessionId);
      setMessages((data.messages || []).filter(m => m.role !== 'system' || m.score_json).map(m => ({
        role: m.role,
        content: m.content,
        score: typeof m.score_json === 'object' && m.score_json?.expertise !== undefined ? m.score_json : null,
      })));
      if (data.is_complete && data.overall_assessment_json) {
        setAssessment(typeof data.overall_assessment_json === 'string'
          ? JSON.parse(data.overall_assessment_json)
          : data.overall_assessment_json);
      } else {
        setAssessment(null);
      }
    } catch { /* ignore */ }
  };

  const formatScore = (score) => {
    if (!score) return '';
    const parts = [
      `Expertise: ${score.expertise}/10`,
      `Communication: ${score.communication}/10`,
      `Relevance: ${score.relevance}/10`,
      `STAR Quality: ${score.star_quality}/10`,
    ];
    let text = parts.join(' | ');
    if (score.feedback) text += `\n\nFeedback: ${score.feedback}`;
    if (score.improved_answer) text += `\n\nStronger answer: ${score.improved_answer}`;
    return text;
  };

  const handlePrepSheet = async (pid) => {
    setPrepLoading(pid);
    setPrepSheet(null);
    try {
      const resp = await api.generatePrepSheet(pid);
      setPrepSheet(resp);
    } catch {
      setPrepSheet({ error: 'Failed to generate prep sheet' });
    } finally {
      setPrepLoading(null);
    }
  };

  const scoreBadgeClass = (val) => {
    if (val >= 8) return 'coach-score-badge high';
    if (val >= 5) return 'coach-score-badge medium';
    return 'coach-score-badge low';
  };

  return (
    <div className="coach-container">
      {/* Sidebar */}
      <div className="coach-sidebar">
        <div className="postings-section">
          <h3>New Session</h3>
          <div className="form-row">
            <label>Job Posting (optional)</label>
            <select value={postingId} onChange={e => setPostingId(e.target.value)}>
              <option value="">General practice</option>
              {postings.map(p => (
                <option key={p.id} value={p.id}>
                  {p.title} @ {p.company}
                </option>
              ))}
            </select>
            {postingId && (
              <button
                className="btn-search"
                style={{ marginTop: 6, width: '100%', fontSize: 12, padding: '6px 12px' }}
                onClick={() => handlePrepSheet(postingId)}
                disabled={prepLoading === postingId}
              >
                {prepLoading === postingId ? 'Generating...' : 'Generate Prep Sheet'}
              </button>
            )}
          </div>
          <div className="form-row">
            <label>Interviewer Persona</label>
            <select value={persona} onChange={e => setPersona(e.target.value)}>
              {PERSONAS.map(p => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label>Questions ({questionCount})</label>
            <input
              type="range" min="3" max="10" value={questionCount}
              onChange={e => setQuestionCount(parseInt(e.target.value))}
            />
          </div>
          <button
            className="btn-search"
            onClick={handleStart}
            disabled={starting}
            style={{ width: '100%' }}
          >
            {starting ? 'Starting...' : 'Start Mock Interview'}
          </button>
        </div>

        {sessions.length > 0 && (
          <div className="postings-section">
            <h3>Past Sessions</h3>
            {sessions.map(s => (
              <div
                key={s.id}
                className="coach-session-item"
                onClick={() => loadSession(s.id)}
                style={activeSession === s.id ? { background: '#e8eaf6', borderColor: '#667eea' } : {}}
              >
                <div className="session-persona">
                  {PERSONAS.find(p => p.id === s.persona)?.label || s.persona}
                </div>
                <div className="session-meta">
                  {s.is_complete ? `Complete (${s.question_count}Q)` : `Q${s.current_question}/${s.question_count}`}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Prep Sheet */}
      {prepSheet && !prepSheet.error && (
        <div className="postings-section" style={{ margin: '0 0 16px' }}>
          <h3>Prep Sheet: {prepSheet.title} @ {prepSheet.company}</h3>
          {prepSheet.prep_data && (
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, fontSize: 13, marginBottom: 12 }}>
              {typeof prepSheet.prep_data === 'string' ? prepSheet.prep_data : JSON.stringify(prepSheet.prep_data, null, 2)}
            </div>
          )}
          {prepSheet.star_examples?.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <strong>STAR Examples:</strong>
              <ul>{prepSheet.star_examples.map((ex, i) => <li key={i}>{typeof ex === 'string' ? ex : JSON.stringify(ex)}</li>)}</ul>
            </div>
          )}
          {prepSheet.talking_points?.length > 0 && (
            <div>
              <strong>Talking Points:</strong>
              <ul>{prepSheet.talking_points.map((tp, i) => <li key={i}>{typeof tp === 'string' ? tp : JSON.stringify(tp)}</li>)}</ul>
            </div>
          )}
        </div>
      )}
      {prepSheet?.error && (
        <div className="text-error" style={{ margin: '0 0 16px' }}>{prepSheet.error}</div>
      )}

      {/* Chat area */}
      <div className="coach-main">
        {!activeSession && (
          <div className="empty-state" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <p>Start a new mock interview or select a past session</p>
          </div>
        )}

        {activeSession && (
          <>
            {messages.length > 0 && (
              <div className="coach-history-toolbar">
                <button
                  className="btn-save-history"
                  onClick={() => saveChatHistoryFromServer(api, 'interview_coach', activeSession)}
                  title="Save chat history"
                >
                  Save History
                </button>
              </div>
            )}
            <div className="coach-messages">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`coach-message ${msg.role}`}
                >
                  {msg.role === 'system' && msg.score ? (
                    <div>
                      <div className="coach-score-badges">
                        {['expertise', 'communication', 'relevance', 'star_quality'].map(dim => (
                          <span key={dim} className={scoreBadgeClass(msg.score[dim])}>
                            {dim.replace('_', ' ')}: {msg.score[dim]}/10
                          </span>
                        ))}
                      </div>
                      {msg.score.feedback && <div className="coach-feedback">{msg.score.feedback}</div>}
                      {msg.score.improved_answer && (
                        <div className="coach-improved">
                          <strong>Stronger answer:</strong> {msg.score.improved_answer}
                        </div>
                      )}
                    </div>
                  ) : msg.content}
                </div>
              ))}
              <div ref={messagesEnd} />
            </div>

            {!assessment && (
              <div className="coach-input-row">
                <textarea
                  value={answer}
                  onChange={e => setAnswer(e.target.value)}
                  placeholder="Type your answer..."
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmitAnswer(); } }}
                />
                <button
                  className="btn-search"
                  onClick={handleSubmitAnswer}
                  disabled={loading || !answer.trim()}
                >
                  {loading ? '...' : 'Send'}
                </button>
              </div>
            )}

            {assessment && (
              <div className="coach-assessment">
                <h3>Overall Assessment</h3>
                <div
                  className="coach-assessment-score"
                  style={{
                    color: assessment.overall_score >= 70 ? '#4caf50' : assessment.overall_score >= 50 ? '#ff9800' : '#e53935',
                  }}
                >
                  {assessment.overall_score}/100
                </div>
                {assessment.strengths?.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <strong style={{ color: '#2e7d32' }}>Strengths:</strong>
                    <ul className="coach-assessment-list">
                      {assessment.strengths.map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>
                )}
                {assessment.improvements?.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <strong style={{ color: '#e65100' }}>Areas to Improve:</strong>
                    <ul className="coach-assessment-list">
                      {assessment.improvements.map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>
                )}
                {assessment.recommendation && (
                  <div style={{
                    background: '#f9fafc', padding: 16, borderRadius: 8,
                    lineHeight: 1.6, color: '#444',
                  }}>
                    {assessment.recommendation}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default InterviewCoach;
