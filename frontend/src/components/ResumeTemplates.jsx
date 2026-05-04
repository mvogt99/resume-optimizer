import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

const ROLE_TYPES = ['architect', 'manager', 'ic', 'consultant', 'executive', 'general'];

export default function ResumeTemplates() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [editId, setEditId] = useState(null);
  const [customizeId, setCustomizeId] = useState(null);
  const [customizeResult, setCustomizeResult] = useState(null);
  const [customizeLoading, setCustomizeLoading] = useState(false);
  const [error, setError] = useState('');

  // Form state
  const [name, setName] = useState('');
  const [roleType, setRoleType] = useState('general');
  const [baseContent, setBaseContent] = useState('');
  const [jobDescription, setJobDescription] = useState('');

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.getTemplates();
      setTemplates(resp.data?.templates || []);
    } catch (e) {
      setError('Failed to load templates');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await api.createTemplate({ name, role_type: roleType, base_content: baseContent });
      setShowCreate(false);
      setName(''); setRoleType('general'); setBaseContent('');
      loadTemplates();
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to create template');
    }
  };

  const handleUpdate = async (id) => {
    setError('');
    try {
      await api.updateTemplate(id, { name, role_type: roleType, base_content: baseContent });
      setEditId(null);
      loadTemplates();
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to update');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this template?')) return;
    try {
      await api.deleteTemplate(id);
      loadTemplates();
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to delete');
    }
  };

  const handleCustomize = async (id) => {
    if (!jobDescription || jobDescription.length < 50) {
      setError('Job description must be at least 50 characters');
      return;
    }
    setCustomizeLoading(true);
    setError('');
    try {
      const resp = await api.customizeTemplate(id, { job_description: jobDescription });
      setCustomizeResult(resp.data);
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to customize');
    } finally {
      setCustomizeLoading(false);
    }
  };

  const handleDownload = async (fmt) => {
    if (!customizeResult?.optimized_text) return;
    try {
      const resp = await api.downloadTemplate(customizeId, fmt, customizeResult.optimized_text);
      const blob = new Blob([resp.data], {
        type: fmt === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `resume.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError('Download failed');
    }
  };

  const startEdit = (t) => {
    setEditId(t.id);
    setName(t.name);
    setRoleType(t.role_type);
    setBaseContent(t.base_content);
  };

  const roleLabel = (rt) => rt.charAt(0).toUpperCase() + rt.slice(1);

  return (
    <div className="resume-templates">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2>Resume Templates</h2>
        <button className="btn-primary" onClick={() => { setShowCreate(true); setEditId(null); setName(''); setRoleType('general'); setBaseContent(''); }}>
          + New Template
        </button>
      </div>

      {error && <div className="error-message" style={{ color: '#e74c3c', marginBottom: 12 }}>{error}</div>}

      {/* Create/Edit Modal */}
      {(showCreate || editId !== null) && (
        <div style={{ background: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: 8, padding: 16, marginBottom: 16 }}>
          <h3>{editId ? 'Edit Template' : 'Create Template'}</h3>
          <form onSubmit={editId ? (e) => { e.preventDefault(); handleUpdate(editId); } : handleCreate}>
            <div style={{ marginBottom: 8 }}>
              <label>Name: </label>
              <input value={name} onChange={e => setName(e.target.value)} required style={{ width: '100%', padding: 6 }} />
            </div>
            <div style={{ marginBottom: 8 }}>
              <label>Role Type: </label>
              <select value={roleType} onChange={e => setRoleType(e.target.value)} style={{ padding: 6 }}>
                {ROLE_TYPES.map(rt => <option key={rt} value={rt}>{roleLabel(rt)}</option>)}
              </select>
            </div>
            <div style={{ marginBottom: 8 }}>
              <label>Resume Content: </label>
              <textarea value={baseContent} onChange={e => setBaseContent(e.target.value)} rows={10}
                style={{ width: '100%', fontFamily: 'monospace', fontSize: 12, padding: 8 }} required />
            </div>
            <button type="submit" className="btn-primary">{editId ? 'Save' : 'Create'}</button>
            <button type="button" style={{ marginLeft: 8 }} onClick={() => { setShowCreate(false); setEditId(null); }}>Cancel</button>
          </form>
        </div>
      )}

      {/* Template List */}
      {loading ? (
        <div className="agent-loading"><div className="agent-spinner" /><span>Loading...</span></div>
      ) : templates.length === 0 ? (
        <div className="empty-state"><p>No templates yet. Create one to get started!</p></div>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {templates.map(t => (
            <div key={t.id} style={{ border: '1px solid #dee2e6', borderRadius: 8, padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong>{t.name}</strong>
                  <span className="status-badge" style={{
                    marginLeft: 8, padding: '2px 8px', borderRadius: 12, fontSize: 12,
                    background: '#e3f2fd', color: '#1565c0'
                  }}>
                    {roleLabel(t.role_type)}
                  </span>
                </div>
                <div>
                  <button onClick={() => startEdit(t)} style={{ marginRight: 6 }}>Edit</button>
                  <button onClick={() => {
                    setCustomizeId(t.id === customizeId ? null : t.id);
                    setCustomizeResult(null);
                    setJobDescription('');
                  }} style={{ marginRight: 6 }}>
                    {customizeId === t.id ? 'Close' : 'Customize'}
                  </button>
                  <button onClick={() => handleDelete(t.id)} style={{ color: '#e74c3c' }}>Delete</button>
                </div>
              </div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                {t.base_content?.substring(0, 150)}...
              </div>

              {/* Customize Panel */}
              {customizeId === t.id && (
                <div style={{ marginTop: 12, padding: 12, background: '#f0f4f8', borderRadius: 6 }}>
                  <textarea value={jobDescription} onChange={e => setJobDescription(e.target.value)}
                    placeholder="Paste job description here (min 50 chars)..." rows={6}
                    style={{ width: '100%', marginBottom: 8, padding: 8 }} />
                  <button className="btn-primary" onClick={() => handleCustomize(t.id)} disabled={customizeLoading}>
                    {customizeLoading ? 'Customizing...' : 'Customize for Job'}
                  </button>

                  {customizeResult && (
                    <div style={{ marginTop: 12 }}>
                      <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
                        <span><strong>ATS Score:</strong> {customizeResult.score}</span>
                        <button onClick={() => handleDownload('pdf')}>Download PDF</button>
                        <button onClick={() => handleDownload('docx')}>Download DOCX</button>
                      </div>
                      {customizeResult.matching_keywords?.length > 0 && (
                        <div style={{ marginBottom: 8 }}>
                          <strong>Matching: </strong>
                          {customizeResult.matching_keywords.slice(0, 10).join(', ')}
                        </div>
                      )}
                      <pre style={{ maxHeight: 300, overflow: 'auto', background: '#fff', padding: 12, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                        {customizeResult.optimized_text}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
