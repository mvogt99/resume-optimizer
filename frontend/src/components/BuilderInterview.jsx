import React, { useState, useRef, useEffect } from 'react';
import api from '../services/api';
import { saveChatHistoryFromServer } from '../utils/chatHistory';

function BuilderInterview({ sessionId, onComplete, onSkip }) {
  const [interviewSessionId, setInterviewSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [extractedBullets, setExtractedBullets] = useState([]);
  const [gapsRemaining, setGapsRemaining] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const [started, setStarted] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleStart = async () => {
    setLoading(true);
    try {
      const result = await api.startBuilderInterview(sessionId);
      setInterviewSessionId(result.session_id);
      setMessages([{ role: 'assistant', content: result.message }]);
      setGapsRemaining(result.gaps_identified || 0);
      setStarted(true);
    } catch (err) {
      setMessages([{ role: 'assistant', content: 'Failed to start interview. You can skip this step.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const result = await api.sendBuilderInterviewMessage(interviewSessionId, userMessage);
      setMessages(prev => [...prev, { role: 'assistant', content: result.message }]);
      setExtractedBullets(result.extracted_bullets || []);
      setGapsRemaining(result.gaps_remaining || 0);
      setIsComplete(result.is_complete || false);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Something went wrong. Try again or skip this step.',
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

  if (!started) {
    return (
      <div className="builder-interview">
        <div className="interview-intro">
          <h3>Gap-Driven Interview</h3>
          <p>
            An AI career coach will ask you about experience gaps between your
            current resume and the job description. Your answers will be
            converted into resume-ready bullet points.
          </p>
          <div className="interview-intro-actions">
            <button className="btn-primary" onClick={handleStart} disabled={loading}>
              {loading ? 'Starting...' : 'Start Interview'}
            </button>
            <button className="btn-secondary" onClick={onSkip}>
              Skip Interview
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="builder-interview">
      <div className="interview-layout">
        <div className="interview-chat-panel">
          <div className="interview-header">
            <h3>Resume Gap Interview</h3>
            {gapsRemaining > 0 && (
              <span className="gaps-badge">{gapsRemaining} gap{gapsRemaining !== 1 ? 's' : ''} remaining</span>
            )}
            {interviewSessionId && messages.length > 0 && (
              <button
                className="btn-save-history"
                onClick={() => saveChatHistoryFromServer(api, 'builder_interview', interviewSessionId)}
                title="Save chat history"
              >
                Save History
              </button>
            )}
          </div>

          <div className="interview-messages">
            {messages.map((msg, idx) => (
              <div key={idx} className={`interview-message ${msg.role}`}>
                <div className="message-bubble">{msg.content}</div>
              </div>
            ))}
            {loading && (
              <div className="interview-message assistant">
                <div className="message-bubble typing">Thinking...</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {!isComplete ? (
            <div className="interview-input-area">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe your experience..."
                rows={3}
                disabled={loading}
              />
              <button className="btn-send" onClick={handleSend} disabled={loading || !input.trim()}>
                Send
              </button>
            </div>
          ) : (
            <div className="interview-complete-bar">
              <span>Interview complete!</span>
              <button className="btn-primary" onClick={() => onComplete(interviewSessionId)}>
                Continue to Preview
              </button>
            </div>
          )}
        </div>

        <div className="interview-sidebar">
          <h4>Extracted Bullets ({extractedBullets.length})</h4>
          <div className="extracted-list">
            {extractedBullets.length === 0 ? (
              <p className="no-bullets">Bullets will appear here as you share your experience.</p>
            ) : (
              extractedBullets.map((bullet, idx) => (
                <div key={idx} className="extracted-bullet">
                  <span className="bullet-text">{bullet.text}</span>
                  <div className="bullet-skills">
                    {(bullet.related_skills || []).map((skill, si) => (
                      <span key={si} className="skill-tag">{skill}</span>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default BuilderInterview;
