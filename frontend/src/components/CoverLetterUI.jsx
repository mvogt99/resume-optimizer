import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

function CoverLetterUI() {
  const [postings, setPostings] = useState([]);
  const [activeLetter, setActiveLetter] = useState(null);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState('');
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const loadPostings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.scoutListPostings(null, 0, 100);
      setPostings(res.postings || []);
    } catch (err) {
      setError('Failed to load postings.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadPostings(); }, [loadPostings]);

  const handleGenerate = async (postingId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.generateCoverLetter(postingId);
      setActiveLetter(res);
      setEditing(false);
    } catch (err) {
      setError('Failed to generate cover letter.');
    } finally {
      setLoading(false);
    }
  };

  const handleLoadLetter = async (postingId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getCoverLetterForPosting(postingId);
      setActiveLetter(res);
      setEditing(false);
    } catch (err) {
      // No letter exists yet
      setActiveLetter(null);
      handleGenerate(postingId);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = () => {
    setEditText(activeLetter.body || '');
    setEditing(true);
  };

  const handleSave = async () => {
    if (!activeLetter) return;
    setLoading(true);
    try {
      const res = await api.updateCoverLetter(activeLetter.id, { body: editText });
      setActiveLetter(res);
      setEditing(false);
    } catch (err) {
      setError('Failed to save.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (!activeLetter) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.regenerateCoverLetter(activeLetter.id, feedback);
      setActiveLetter(res);
      setShowFeedback(false);
      setFeedback('');
    } catch (err) {
      setError('Failed to regenerate.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!activeLetter) return;
    const full = [activeLetter.subject, '', activeLetter.greeting, '', activeLetter.body, '', activeLetter.closing].filter(Boolean).join('\n');
    try {
      await navigator.clipboard.writeText(full);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      setError('Clipboard access denied.');
    }
  };

  return (
    <div className="cover-letter-container">
      <h2>Cover Letters</h2>
      {error && <div className="cover-letter-error">{error}</div>}

      <div className="cover-letter-layout">
        {/* Posting list */}
        <div className="cover-letter-sidebar">
          <h3>Job Postings</h3>
          {loading && postings.length === 0 && <p>Loading...</p>}
          <div className="cover-letter-posting-list">
            {postings.map(p => (
              <div key={p.id} className="cover-letter-posting-item" onClick={() => handleLoadLetter(p.id)}>
                <span className="cover-letter-posting-title">{p.title || 'Untitled'}</span>
                <span className="cover-letter-posting-company">{p.company || ''}</span>
              </div>
            ))}
            {postings.length === 0 && !loading && <p className="cover-letter-empty">No postings found.</p>}
          </div>
        </div>

        {/* Letter preview */}
        <div className="cover-letter-main">
          {activeLetter ? (
            <div className="cover-letter-preview">
              {activeLetter.subject && <div className="cover-letter-subject">{activeLetter.subject}</div>}
              {activeLetter.greeting && <div className="cover-letter-greeting">{activeLetter.greeting}</div>}

              {editing ? (
                <textarea className="cover-letter-edit-area" value={editText}
                  onChange={e => setEditText(e.target.value)} rows={16} />
              ) : (
                <div className="cover-letter-body">
                  {(activeLetter.body || '').split('\n').map((line, i) => <p key={i}>{line || '\u00A0'}</p>)}
                </div>
              )}

              {activeLetter.closing && !editing && (
                <div className="cover-letter-closing">{activeLetter.closing}</div>
              )}

              <div className="cover-letter-actions">
                {editing ? (
                  <>
                    <button className="btn-primary" onClick={handleSave} disabled={loading}>Save</button>
                    <button className="btn-secondary" onClick={() => setEditing(false)}>Cancel</button>
                  </>
                ) : (
                  <>
                    <button className="btn-primary" onClick={handleEdit}>Edit</button>
                    <button className="btn-primary" onClick={() => setShowFeedback(true)}>Regenerate</button>
                    <button className="btn-primary" onClick={handleCopy}>
                      {copied ? 'Copied!' : 'Copy'}
                    </button>
                  </>
                )}
              </div>

              {showFeedback && (
                <div className="cover-letter-feedback">
                  <textarea placeholder="Optional feedback for regeneration..."
                    value={feedback} onChange={e => setFeedback(e.target.value)} rows={3} />
                  <div className="cover-letter-feedback-actions">
                    <button className="btn-primary" onClick={handleRegenerate} disabled={loading}>
                      {loading ? 'Regenerating...' : 'Regenerate'}
                    </button>
                    <button className="btn-secondary" onClick={() => setShowFeedback(false)}>Cancel</button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="cover-letter-empty-main">
              <h3>Cover Letter Generator</h3>
              <p>Select a job posting to generate or view a cover letter.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default CoverLetterUI;
