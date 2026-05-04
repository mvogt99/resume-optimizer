import React, { useState } from 'react';

const LINKEDIN_CHAR_LIMIT = 3000;

function PostEditor({ post, campaignId, onSave, onRegenerate, onClose, onNavigateToSource }) {
  const [title, setTitle] = useState(post.title || '');
  const [content, setContent] = useState(post.content || '');
  const [hashtags, setHashtags] = useState(post.hashtags || '');
  const [feedback, setFeedback] = useState('');
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const charCount = content.length;
  const isOverLimit = charCount > LINKEDIN_CHAR_LIMIT;

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(post.id, { title, content, hashtags });
      onClose();
    } catch (err) {
      alert('Failed to save.');
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const result = await onRegenerate(post.id, feedback);
      setTitle(result.title || title);
      setContent(result.content || content);
      setHashtags(result.hashtags || hashtags);
      setFeedback('');
    } catch (err) {
      alert('Failed to regenerate.');
    } finally {
      setRegenerating(false);
    }
  };

  const draftHistory = post.draft_history || [];

  return (
    <div className="post-editor-overlay" onClick={onClose}>
      <div className="post-editor-modal" onClick={e => e.stopPropagation()}>
        <div className="post-editor-header">
          <h3>Edit Post</h3>
          <button className="btn-close" onClick={onClose}>&times;</button>
        </div>

        <div className="post-editor-body">
          <div className="form-group">
            <label>Title (internal reference)</label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Post title"
            />
          </div>

          <div className="form-group">
            <label>
              Content
              <span className={`char-counter ${isOverLimit ? 'over-limit' : ''}`}>
                {charCount}/{LINKEDIN_CHAR_LIMIT}
              </span>
            </label>
            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder="Write your LinkedIn post..."
              rows={12}
              className={isOverLimit ? 'textarea-over-limit' : ''}
            />
          </div>

          <div className="form-group">
            <label>Hashtags</label>
            <input
              value={hashtags}
              onChange={e => setHashtags(e.target.value)}
              placeholder="#LocalAI #EnterpriseArchitecture"
            />
          </div>

          {/* Source References */}
          {post.source_refs && post.source_refs.length > 0 && (
            <div className="post-source-refs">
              <label>Source References</label>
              <div className="post-ref-badges">
                {post.source_refs.map((ref, i) => (
                  <span
                    key={i}
                    className={`post-ref-badge post-ref-${ref.type || 'unknown'} ${onNavigateToSource ? 'post-ref-clickable' : ''}`}
                    onClick={() => onNavigateToSource && onNavigateToSource(ref)}
                    title={onNavigateToSource ? `View in ${ref.type === 'client' ? 'Projects' : 'Journey'} tab` : ''}
                  >
                    {ref.name || ref.type || 'ref'}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Regenerate with Feedback */}
          <div className="post-regenerate-section">
            <label>Regenerate with Feedback</label>
            <div className="post-regen-row">
              <input
                value={feedback}
                onChange={e => setFeedback(e.target.value)}
                placeholder="e.g., Make it more technical, add a personal anecdote..."
              />
              <button
                className="btn-regenerate"
                onClick={handleRegenerate}
                disabled={regenerating}
              >
                {regenerating ? 'Regenerating...' : 'Regenerate'}
              </button>
            </div>
          </div>

          {/* Draft History */}
          {draftHistory.length > 0 && (
            <div className="post-history">
              <button
                className="btn-toggle-history"
                onClick={() => setShowHistory(!showHistory)}
              >
                {showHistory ? 'Hide' : 'Show'} Draft History ({draftHistory.length})
              </button>
              {showHistory && (
                <div className="post-history-list">
                  {draftHistory.map((draft, i) => (
                    <div key={i} className="post-history-item">
                      <div className="post-history-title">
                        Draft {i + 1}: {draft.title || 'Untitled'}
                      </div>
                      <div className="post-history-content">
                        {(draft.content || '').substring(0, 200)}...
                      </div>
                      <button
                        className="btn-restore"
                        onClick={() => {
                          setTitle(draft.title || title);
                          setContent(draft.content || '');
                          setHashtags(draft.hashtags || '');
                        }}
                      >
                        Restore
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="post-editor-footer">
          <button className="btn-cancel" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving || isOverLimit}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default PostEditor;
