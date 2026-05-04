import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

const RELATIONSHIPS = [
  { value: 'colleague', label: 'Colleague' },
  { value: 'manager', label: 'Manager' },
  { value: 'direct_report', label: 'Direct Report' },
  { value: 'client', label: 'Client' },
  { value: 'mentor', label: 'Mentor' },
];

const emptyForm = { target_name: '', relationship: 'colleague', shared_projects: '', specific_skills: '' };

function RecommendationDrafter() {
  const [drafts, setDrafts] = useState([]);
  const [form, setForm] = useState({ ...emptyForm });
  const [activeDraft, setActiveDraft] = useState(null);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(null);

  const loadDrafts = useCallback(async () => {
    try {
      const res = await api.getLinkedInUpdates();
      const data = res.updates || res;
      setDrafts(Array.isArray(data) ? data : []);
    } catch (err) {
      // Endpoint may not exist yet; start with empty
      setDrafts([]);
    }
  }, []);

  useEffect(() => { loadDrafts(); }, [loadDrafts]);

  const handleFormChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const handleGenerate = async () => {
    if (!form.target_name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.generateLinkedInUpdate();
      const draft = {
        id: res.id || Date.now(),
        target_name: form.target_name,
        relationship: form.relationship,
        subject: res.subject || `Recommendation request for ${form.target_name}`,
        body: res.body || res.content || res.text || '',
        created_at: new Date().toISOString(),
      };
      setDrafts(prev => [draft, ...prev]);
      setActiveDraft(draft);
      setForm({ ...emptyForm });
    } catch (err) {
      setError('Failed to generate draft.');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (draft) => {
    setActiveDraft(draft);
    setEditText(draft.body || '');
    setEditing(true);
  };

  const handleSave = async () => {
    if (!activeDraft) return;
    setLoading(true);
    try {
      if (activeDraft.id && typeof activeDraft.id === 'number' && activeDraft.id > 1000000000) {
        // Local-only draft
        setDrafts(prev => prev.map(d => d.id === activeDraft.id ? { ...d, body: editText } : d));
        setActiveDraft(prev => ({ ...prev, body: editText }));
      } else {
        await api.updateLinkedInSection(activeDraft.id, { body: editText });
        setDrafts(prev => prev.map(d => d.id === activeDraft.id ? { ...d, body: editText } : d));
        setActiveDraft(prev => ({ ...prev, body: editText }));
      }
      setEditing(false);
    } catch (err) {
      setError('Failed to save.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = (draftId) => {
    if (!window.confirm('Delete this draft?')) return;
    setDrafts(prev => prev.filter(d => d.id !== draftId));
    if (activeDraft?.id === draftId) {
      setActiveDraft(null);
      setEditing(false);
    }
  };

  const handleCopy = async (draft) => {
    const text = `${draft.subject || ''}\n\n${draft.body || ''}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(draft.id);
      setTimeout(() => setCopied(null), 2000);
    } catch (err) {
      setError('Clipboard access denied.');
    }
  };

  return (
    <div className="rec-drafter-container">
      <h2>Recommendation Drafter</h2>
      {error && <div className="rec-drafter-error">{error}</div>}

      <div className="rec-drafter-layout">
        {/* Form */}
        <div className="rec-drafter-form-panel">
          <h3>New Request</h3>
          <div className="form-group">
            <label>Target Name *</label>
            <input value={form.target_name} onChange={e => handleFormChange('target_name', e.target.value)}
              placeholder="e.g., Jane Smith" />
          </div>
          <div className="form-group">
            <label>Relationship</label>
            <select value={form.relationship} onChange={e => handleFormChange('relationship', e.target.value)}>
              {RELATIONSHIPS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Shared Projects</label>
            <textarea value={form.shared_projects} onChange={e => handleFormChange('shared_projects', e.target.value)}
              placeholder="Projects you worked on together..." rows={3} />
          </div>
          <div className="form-group">
            <label>Specific Skills to Highlight</label>
            <textarea value={form.specific_skills} onChange={e => handleFormChange('specific_skills', e.target.value)}
              placeholder="Skills you'd like them to mention..." rows={3} />
          </div>
          <button className="btn-primary" onClick={handleGenerate}
            disabled={!form.target_name.trim() || loading}>
            {loading ? 'Generating...' : 'Generate Draft'}
          </button>
        </div>

        {/* Drafts list */}
        <div className="rec-drafter-list-panel">
          <h3>Drafts ({drafts.length})</h3>
          {drafts.length === 0 && <p className="rec-drafter-empty">No drafts yet.</p>}
          {drafts.map(draft => (
            <div key={draft.id} className={`rec-drafter-card ${activeDraft?.id === draft.id ? 'active' : ''}`}
              onClick={() => { setActiveDraft(draft); setEditing(false); }}>
              <div className="rec-drafter-card-header">
                <strong>{draft.target_name || draft.subject || 'Draft'}</strong>
                <span className="rec-drafter-relationship">{draft.relationship || ''}</span>
              </div>
              <p className="rec-drafter-card-preview">
                {(draft.body || '').substring(0, 100)}{(draft.body || '').length > 100 ? '...' : ''}
              </p>
              <div className="rec-drafter-card-actions">
                <button className="btn-small" onClick={(e) => { e.stopPropagation(); handleEdit(draft); }}>Edit</button>
                <button className="btn-small" onClick={(e) => { e.stopPropagation(); handleCopy(draft); }}>
                  {copied === draft.id ? 'Copied!' : 'Copy'}
                </button>
                <button className="btn-small btn-danger" onClick={(e) => { e.stopPropagation(); handleDelete(draft.id); }}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Edit modal area */}
      {editing && activeDraft && (
        <div className="rec-drafter-edit-panel">
          <h3>Editing: {activeDraft.target_name || 'Draft'}</h3>
          <div className="rec-drafter-subject">{activeDraft.subject}</div>
          <textarea className="rec-drafter-edit-area" value={editText}
            onChange={e => setEditText(e.target.value)} rows={12} />
          <div className="rec-drafter-edit-actions">
            <button className="btn-primary" onClick={handleSave} disabled={loading}>Save</button>
            <button className="btn-secondary" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default RecommendationDrafter;
