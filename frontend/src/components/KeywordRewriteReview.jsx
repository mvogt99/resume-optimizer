import React, { useState } from 'react';

/**
 * KeywordRewriteReview — the 'review' stage of the equivalency flow.
 *
 * Props:
 *   rewrites          [{section, original_text, proposed_text, keywords_addressed}]
 *   rewriteAccepted   {[idx]: bool}
 *   setRewriteAccepted fn(updater)
 *   onEditProposed    fn(idx, newText) — called when user edits proposed text
 *   persisted         bool
 *   persisting        bool
 *   applying          bool
 *   allResolved       [{keyword, equivalent, status, ...}]
 *   onApply           fn()
 *   onPersist         fn()
 *   onBack            fn()
 *   onClose           fn()
 */
function KeywordRewriteReview({
  rewrites = [],
  rewriteAccepted = {},
  setRewriteAccepted,
  onEditProposed,
  persisted,
  persisting,
  applying,
  allResolved = [],
  onApply,
  onPersist,
  onBack,
  onClose,
}) {
  const [editingIdx, setEditingIdx] = useState(null);
  const [editDraft, setEditDraft] = useState('');

  const startEdit = (idx) => {
    setEditDraft(rewrites[idx]?.proposed_text || '');
    setEditingIdx(idx);
  };
  const saveEdit = (idx) => {
    if (onEditProposed) onEditProposed(idx, editDraft);
    setEditingIdx(null);
  };
  const cancelEdit = () => setEditingIdx(null);

  return (
    <div className="keq-panel">
      <div className="keq-review-header">
        <h4>Suggested Rewrites</h4>
        <p className="keq-review-hint">
          Each section below shows the current text and a proposed rewrite that
          naturally incorporates job description keywords via your equivalencies.
          Accept or reject each one, or click Edit to adjust the proposed text.
        </p>
      </div>

      {rewrites.map((rw, idx) => (
        <div
          key={idx}
          className={`keq-rewrite-card ${rewriteAccepted[idx] ? 'keq-rw-accepted' : 'keq-rw-rejected'}`}
        >
          <div className="keq-rw-header">
            <span className="keq-rw-section">{rw.section}</span>
            <div className="keq-rw-header-actions">
              <label className="keq-rw-toggle">
                <input
                  type="checkbox"
                  checked={!!rewriteAccepted[idx]}
                  onChange={e =>
                    setRewriteAccepted(prev => ({ ...prev, [idx]: e.target.checked }))
                  }
                />
                {rewriteAccepted[idx] ? 'Accepted' : 'Rejected'}
              </label>
              {editingIdx === idx ? (
                <>
                  <button className="btn-xs keq-edit-save" onClick={() => saveEdit(idx)}>Save</button>
                  <button className="btn-xs keq-edit-cancel" onClick={cancelEdit}>Cancel</button>
                </>
              ) : (
                <button className="btn-xs keq-edit-btn" onClick={() => startEdit(idx)}>Edit</button>
              )}
            </div>
          </div>
          {rw.keywords_addressed?.length > 0 && (
            <div className="keq-rw-keywords">
              {rw.keywords_addressed.map((kw, ki) => (
                <span key={ki} className="chip chip-small chip-equiv">{kw}</span>
              ))}
            </div>
          )}
          <div className="keq-rw-diff">
            <div className="keq-rw-col keq-rw-original">
              <span className="keq-rw-col-label">Current</span>
              <pre>{rw.original_text}</pre>
            </div>
            <div className="keq-rw-col keq-rw-proposed">
              <span className="keq-rw-col-label">Proposed</span>
              {editingIdx === idx ? (
                <textarea
                  className="keq-rw-edit-area"
                  value={editDraft}
                  onChange={e => setEditDraft(e.target.value)}
                  rows={Math.max(6, (editDraft.match(/\n/g) || []).length + 3)}
                />
              ) : (
                <pre>{rw.proposed_text}</pre>
              )}
            </div>
          </div>
        </div>
      ))}

      <div className="keq-review-actions">
        <button
          className="btn-primary keq-apply-btn"
          onClick={onApply}
          disabled={applying || !Object.values(rewriteAccepted).some(Boolean)}
        >
          {applying ? 'Applying…' : 'Apply Accepted Rewrites & Re-analyze Score'}
        </button>

        {!persisted ? (
          <button
            className="btn-secondary keq-persist-btn"
            onClick={onPersist}
            disabled={persisting || allResolved.length === 0}
          >
            {persisting ? 'Saving…' : 'Save Equivalencies for Future Jobs'}
          </button>
        ) : (
          <span className="keq-persisted-badge">Equivalencies saved ✓</span>
        )}

        <button className="btn-secondary" onClick={onBack}>
          ← Back to Interview
        </button>
        <button className="btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}

export default KeywordRewriteReview;
