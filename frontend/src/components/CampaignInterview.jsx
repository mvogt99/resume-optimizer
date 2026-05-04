import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';
import { saveChatHistoryFromServer } from '../utils/chatHistory';

const STAGES = ['theme', 'audience', 'tone', 'storyline', 'post_count', 'content_seeds', 'review'];
const STAGE_LABELS = {
  theme: 'Theme',
  audience: 'Audience',
  tone: 'Tone',
  storyline: 'Storyline',
  post_count: 'Posts',
  content_seeds: 'Seeds',
  review: 'Review',
};

function CampaignInterview({ onCampaignCreated, onBack, initialTheme: initialThemeProp = '' }) {
  const [sessionId, setSessionId] = useState(null);
  const [stage, setStage] = useState('theme');
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [context, setContext] = useState({});
  const [suggestions, setSuggestions] = useState([]);
  const [isReview, setIsReview] = useState(false);
  const [creating, setCreating] = useState(false);
  const [initialTheme, setInitialTheme] = useState(initialThemeProp);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleStart = async (e) => {
    e.preventDefault();
    try {
      const res = await api.startCampaignInterview(initialTheme.trim());
      setSessionId(res.session_id);
      setStage(res.stage);
      setMessages([{ id: Date.now(), role: 'assistant', text: res.message }]);
      if (res.suggestions) setSuggestions(res.suggestions);
    } catch (err) {
      setMessages([{
        id: Date.now(),
        role: 'assistant',
        text: 'Failed to start interview. Please try again.',
      }]);
    }
  };

  const handleSend = async (text) => {
    const msg = text || inputValue.trim();
    if (!msg || !sessionId || sending) return;
    setInputValue('');
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: msg }]);
    setSending(true);

    try {
      const res = await api.sendCampaignMessage(sessionId, msg);
      setStage(res.stage);
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        text: res.message,
      }]);
      if (res.context) setContext(res.context);
      if (res.suggestions) setSuggestions(res.suggestions);
      if (res.is_review) setIsReview(true);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        text: 'Something went wrong. Please try again.',
      }]);
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

  const handleSuggestionClick = (suggestion) => {
    const text = suggestion.theme || suggestion.name || suggestion.title || String(suggestion);
    handleSend(text);
  };

  const handleCreateCampaign = async () => {
    if (!sessionId) return;
    setCreating(true);
    try {
      const res = await api.createCampaignFromInterview(sessionId);
      if (onCampaignCreated) onCampaignCreated(res.campaign_id);
    } catch (err) {
      alert('Failed to create campaign. Please try again.');
    } finally {
      setCreating(false);
    }
  };

  // Stage progress bar
  const currentIdx = STAGES.indexOf(stage);
  const renderStages = () => (
    <div className="campaign-stages">
      {STAGES.map((s, i) => (
        <div
          key={s}
          className={`campaign-stage ${i < currentIdx ? 'done' : ''} ${i === currentIdx ? 'active' : ''}`}
        >
          <span className="campaign-stage-dot">{i < currentIdx ? '\u2713' : i + 1}</span>
          <span className="campaign-stage-label">{STAGE_LABELS[s]}</span>
        </div>
      ))}
    </div>
  );

  // Start form
  if (!sessionId) {
    return (
      <div className="campaign-interview">
        <div className="campaign-interview-header">
          <button className="btn-back" onClick={onBack}>&larr; Back</button>
          <h2>New Campaign</h2>
        </div>
        <p className="campaign-subtitle">
          Plan a LinkedIn content campaign through a guided interview.
          We'll use your knowledge graph to ground suggestions in real experience.
        </p>
        <form onSubmit={handleStart} className="campaign-start-form">
          <div className="form-group">
            <label>Starting Theme (optional)</label>
            <input
              value={initialTheme}
              onChange={e => setInitialTheme(e.target.value)}
              placeholder="e.g., Local AI Deployment, Enterprise Architecture"
            />
          </div>
          <button type="submit" className="btn-primary">
            Start Campaign Interview
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="campaign-interview">
      <div className="campaign-interview-header">
        <button className="btn-back" onClick={onBack}>&larr; Back</button>
        <h2>Campaign Interview{context.theme ? ` — ${context.theme}` : ''}</h2>
        {sessionId && messages.length > 0 && (
          <button
            className="btn-save-history"
            onClick={() => saveChatHistoryFromServer(api, 'campaign', sessionId)}
            title="Save chat history"
          >
            Save History
          </button>
        )}
      </div>

      {renderStages()}

      <div className="campaign-layout">
        {/* Chat Panel */}
        <div className="campaign-chat-panel">
          <div className="campaign-messages">
            {messages.map(msg => (
              <div key={msg.id} className={`campaign-message campaign-message-${msg.role}`}>
                <div className="campaign-bubble">{msg.text}</div>
              </div>
            ))}
            {sending && (
              <div className="campaign-message campaign-message-assistant">
                <div className="campaign-bubble campaign-typing">Thinking...</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggestions */}
          {suggestions.length > 0 && !isReview && (
            <div className="campaign-suggestions">
              {suggestions.slice(0, 5).map((s, i) => {
                const label = s.theme || s.name || s.title || String(s);
                return (
                  <button
                    key={i}
                    className="campaign-suggestion-chip"
                    onClick={() => handleSuggestionClick(s)}
                    disabled={sending}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          )}

          {!isReview ? (
            <div className="campaign-input-row">
              <input
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your response..."
                disabled={sending}
              />
              <button
                onClick={() => handleSend()}
                disabled={!inputValue.trim() || sending}
                className="btn-send"
              >
                Send
              </button>
            </div>
          ) : (
            <div className="campaign-review-bar">
              <span>Campaign plan ready!</span>
              <button
                className="btn-primary"
                onClick={handleCreateCampaign}
                disabled={creating}
              >
                {creating ? 'Creating...' : 'Create Campaign'}
              </button>
            </div>
          )}
        </div>

        {/* Context Sidebar */}
        <div className="campaign-sidebar">
          <h3>Campaign Plan</h3>
          {context.theme && (
            <div className="campaign-ctx-field">
              <label>Theme</label>
              <div className="campaign-ctx-value">{context.theme}</div>
            </div>
          )}
          {context.audience && (
            <div className="campaign-ctx-field">
              <label>Audience</label>
              <div className="campaign-ctx-value">{context.audience}</div>
            </div>
          )}
          {context.tone && (
            <div className="campaign-ctx-field">
              <label>Tone</label>
              <div className="campaign-ctx-value">{context.tone}</div>
            </div>
          )}
          {context.storyline && (
            <div className="campaign-ctx-field">
              <label>Storyline</label>
              <div className="campaign-ctx-value">{context.storyline}</div>
            </div>
          )}
          {context.post_count > 0 && (
            <div className="campaign-ctx-field">
              <label>Posts</label>
              <div className="campaign-ctx-value">{context.post_count}</div>
            </div>
          )}
          {context.seeds && context.seeds.length > 0 && (
            <div className="campaign-ctx-field">
              <label>Post Ideas ({context.seeds.length})</label>
              <ul className="campaign-seed-list">
                {context.seeds.map((s, i) => (
                  <li key={i}>{s.title || `Post ${i + 1}`}</li>
                ))}
              </ul>
            </div>
          )}
          {!context.theme && (
            <p className="campaign-empty-sidebar">
              Campaign details will appear here as you answer questions.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default CampaignInterview;
