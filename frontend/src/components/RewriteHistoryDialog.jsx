import React, { useState, useEffect } from 'react';
import api from '../services/api';

/**
 * RewriteHistoryDialog — browse and re-apply past equivalency rewrite suggestions.
 *
 * Props:
 *   resumeText       string — current resume text
 *   onClose          fn()
 *   onResumeUpdated  fn(text)
 *   onApplied        fn(text)
 */
function RewriteHistoryDialog({ resumeText, onClose, onResumeUpdated, onApplied }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [applying, setApplying] = useState(false);
  const [applySuccess, setApplySuccess] = useState(null);

  useEffect(() => {
    api.getRewriteHistory()
      .then(data => setHistory(data.history || []))
      .catch(() => setError('Failed to load rewrite history.'))
      .finally(() => setLoading(false));
  }, []);

  const handleApply = async (rewrites) => {
    setApplying(true);
    setApplySuccess(null);
    let updatedText = resumeText;
    const applied = [];
    for (const rw of rewrites) {
      if (!rw.original_text || !rw.proposed_text) continue;
      if (updatedText.includes(rw.original_text)) {
        updatedText = updatedText.replaceAll(rw.original_text, rw.proposed_text);
        applied.push(rw.section || 'Section');
      } else {
        const anchor = rw.original_text.slice(0, 120);
        const idx = updatedText.indexOf(anchor);
        if (idx !== -1) {
          const after = updatedText.slice(idx);
          const boundary = after.match(/\n{2,}(?=[A-Z][A-Z\s&/]+\n)/);
          const end = boundary ? idx + boundary.index : idx + Math.max(rw.original_text.length + 300, 600);
          updatedText = updatedText.slice(0, idx) + rw.proposed_text + updatedText.slice(end);
          applied.push(rw.section || 'Section');
        }
      }
    }
    if (applied.length > 0) {
      if (onResumeUpdated) onResumeUpdated(updatedText);
      if (onApplied) onApplied(updatedText);
      setApplySuccess(`Applied ${applied.length} rewrite${applied.length > 1 ? 's' : ''}: ${applied.join(', ')}`);
    } else {
      setApplySuccess('No rewrites could be applied — resume text may have changed.');
    }
    setApplying(false);
  };

  const fmt = (iso) => {
    try {
      return new Date(iso).toLocaleString();
    } catch { return iso; }
  };

  return (
    <div className="rh-overlay" onClick={onClose}>
      <div className="rh-dialog" onClick={e => e.stopPropagation()}>
        <div className="rh-header">
          <h4 className="rh-title">Rewrite History</h4>
          <button className="btn-secondary rh-close" onClick={onClose}>✕</button>
        </div>

        {loading && <p className="rh-loading">Loading history…</p>}
        {error && <p className="rh-error">{error}</p>}

        {!loading && !error && history.length === 0 && (
          <p className="rh-empty">No rewrite suggestions have been generated yet.</p>
        )}

        {applySuccess && (
          <div className="rh-apply-success">{applySuccess}</div>
        )}

        <div className="rh-list">
          {history.map(entry => (
            <div key={entry.id} className="rh-entry">
              <div className="rh-entry-header" onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}>
                <span className="rh-entry-date">{fmt(entry.created_at)}</span>
                <span className="rh-entry-meta">
                  {entry.rewrite_count} rewrite{entry.rewrite_count !== 1 ? 's' : ''}
                  {entry.keywords_addressed.length > 0 && (
                    <> · {entry.keywords_addressed.slice(0, 3).join(', ')}{entry.keywords_addressed.length > 3 ? ` +${entry.keywords_addressed.length - 3}` : ''}</>
                  )}
                </span>
                <span className="rh-entry-toggle">{expandedId === entry.id ? '▲' : '▼'}</span>
              </div>

              {expandedId === entry.id && (
                <div className="rh-entry-body">
                  {entry.rewrites.map((rw, i) => (
                    <div key={i} className="rh-rewrite-card">
                      <div className="rh-rewrite-section">{rw.section || 'Resume Section'}</div>
                      <div className="rh-rewrite-kws">
                        {(rw.keywords_addressed || []).map((kw, ki) => (
                          <span key={ki} className="chip chip-xs chip-added">{kw}</span>
                        ))}
                      </div>
                      <pre className="rh-rewrite-preview">{(rw.proposed_text || '').slice(0, 300)}{(rw.proposed_text || '').length > 300 ? '…' : ''}</pre>
                    </div>
                  ))}
                  <button
                    className="btn-primary rh-apply-btn"
                    disabled={applying}
                    onClick={() => handleApply(entry.rewrites)}
                  >
                    {applying ? 'Applying…' : 'Apply These Rewrites'}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default RewriteHistoryDialog;
