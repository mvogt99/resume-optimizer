import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

function CoverLetter({ postingId }) {
  const [letter, setLetter] = useState(null);
  const [loading, setLoading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [feedback, setFeedback] = useState('');

  const loadExisting = useCallback(async () => {
    if (!postingId) return;
    try {
      const data = await api.getCoverLetterForPosting(postingId);
      setLetter(data);
    } catch {
      setLetter(null);
    }
  }, [postingId]);

  useEffect(() => { loadExisting(); }, [loadExisting]);

  const handleGenerate = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.generateCoverLetter(postingId);
      if (data.error) {
        setError(data.error);
      } else {
        setLetter(data);
      }
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to generate cover letter');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (!letter?.id) return;
    setRegenerating(true);
    setError('');
    try {
      const data = await api.regenerateCoverLetter(letter.id, feedback);
      if (data.error) {
        setError(data.error);
      } else {
        setLetter(data);
        setFeedback('');
      }
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to regenerate');
    } finally {
      setRegenerating(false);
    }
  };

  const handleSave = async () => {
    if (!letter?.id) return;
    try {
      const data = await api.updateCoverLetter(letter.id, editData);
      setLetter(data);
      setEditing(false);
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to save');
    }
  };

  const handleDelete = async () => {
    if (!letter?.id || !window.confirm('Delete this cover letter?')) return;
    try {
      await api.deleteCoverLetter(letter.id);
      setLetter(null);
    } catch {
      setError('Failed to delete');
    }
  };

  const startEdit = () => {
    setEditData({
      subject: letter.subject || '',
      greeting: letter.greeting || '',
      body: letter.body || '',
      closing: letter.closing || '',
    });
    setEditing(true);
  };

  const copyAll = () => {
    const text = [letter.greeting, '', letter.body, '', letter.closing].join('\n');
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="cover-letter-container">
      {!postingId && (
        <div className="empty-state">
          <p>Select a job posting to generate a cover letter</p>
        </div>
      )}

      {postingId && !letter && (
        <div className="criteria-actions">
          <button className="btn-search" onClick={handleGenerate} disabled={loading}>
            {loading ? 'Generating...' : 'Generate Cover Letter'}
          </button>
          {loading && <div className="agent-spinner" />}
        </div>
      )}

      {error && <div className="text-error" style={{ margin: '12px 0' }}>{error}</div>}

      {letter && !editing && (
        <div className="cover-letter-display">
          <div className="postings-header">
            <h3>Cover Letter</h3>
            <div className="posting-actions">
              <button className="btn-icon" onClick={startEdit}>Edit</button>
              <button className="btn-icon" onClick={copyAll}>Copy</button>
              <button className="btn-icon" onClick={handleDelete} style={{ color: '#e53935' }}>Delete</button>
            </div>
          </div>

          {letter.subject && (
            <div className="cover-letter-field">
              <label>Subject</label>
              <div className="field-value" style={{ fontWeight: 600, color: '#667eea' }}>{letter.subject}</div>
            </div>
          )}

          <div style={{
            background: '#f9fafc', padding: 20, borderRadius: 8, lineHeight: 1.7,
          }}>
            {letter.greeting && (
              <p style={{ fontWeight: 500, marginBottom: 12 }}>{letter.greeting}</p>
            )}
            <div style={{ whiteSpace: 'pre-wrap', color: '#444' }}>{letter.body}</div>
            {letter.closing && (
              <p style={{ marginTop: 16, fontStyle: 'italic' }}>{letter.closing}</p>
            )}
          </div>

          <div className="cover-letter-regenerate">
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <label style={{ fontSize: 13, color: '#666', display: 'block', marginBottom: 4 }}>
                  Feedback for regeneration:
                </label>
                <input
                  type="text"
                  value={feedback}
                  onChange={e => setFeedback(e.target.value)}
                  placeholder="e.g., make it more enthusiastic, mention Python experience..."
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, boxSizing: 'border-box' }}
                />
              </div>
              <button
                className="btn-search"
                onClick={handleRegenerate}
                disabled={regenerating}
              >
                {regenerating ? 'Regenerating...' : 'Regenerate'}
              </button>
              <button
                className="btn-search btn-orange"
                onClick={handleGenerate}
                disabled={loading}
              >
                {loading ? 'Generating...' : 'Generate New'}
              </button>
            </div>
          </div>
        </div>
      )}

      {letter && editing && (
        <div className="cover-letter-display">
          <h3>Edit Cover Letter</h3>
          <div className="form-row">
            <label>Subject</label>
            <input
              value={editData.subject}
              onChange={e => setEditData(d => ({ ...d, subject: e.target.value }))}
            />
          </div>
          <div className="form-row">
            <label>Greeting</label>
            <input
              value={editData.greeting}
              onChange={e => setEditData(d => ({ ...d, greeting: e.target.value }))}
            />
          </div>
          <div className="form-row">
            <label>Body</label>
            <textarea
              value={editData.body}
              onChange={e => setEditData(d => ({ ...d, body: e.target.value }))}
              style={{ minHeight: 200 }}
            />
          </div>
          <div className="form-row">
            <label>Closing</label>
            <input
              value={editData.closing}
              onChange={e => setEditData(d => ({ ...d, closing: e.target.value }))}
            />
          </div>
          <div className="cover-letter-actions">
            <button className="btn-search" onClick={handleSave}>Save</button>
            <button className="btn-save-criteria" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default CoverLetter;
