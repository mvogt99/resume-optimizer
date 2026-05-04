import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

function BuilderPreview({ sessionId, interviewSessionId, onSave, onBack }) {
  const [preview, setPreview] = useState(null);
  const [editText, setEditText] = useState('');
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [compiling, setCompiling] = useState(false);
  const [compiled, setCompiled] = useState(false);
  const [atsScore, setAtsScore] = useState(0);
  const [scoreBreakdown, setScoreBreakdown] = useState({});
  const [error, setError] = useState('');

  const loadPreview = useCallback(async () => {
    try {
      const data = await api.getBuilderPreview(sessionId);
      setPreview(data);
      setEditText(data.text || '');
      setAtsScore(data.ats_score || 0);
      setScoreBreakdown(data.score_breakdown || {});
    } catch (err) {
      setError('Failed to load preview');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    loadPreview();
  }, [loadPreview]);

  const handleCompile = async () => {
    setCompiling(true);
    setError('');
    try {
      const result = await api.compileBuilderResume(sessionId, interviewSessionId);
      setEditText(result.compiled_text || '');
      setCompiled(true);
    } catch (err) {
      setError('Failed to compile resume');
    } finally {
      setCompiling(false);
    }
  };

  const handleSaveEdit = async () => {
    setError('');
    try {
      const result = await api.editBuilderResume(sessionId, editText);
      setAtsScore(result.ats_score || 0);
      setScoreBreakdown(result.score_breakdown || {});
    } catch (err) {
      setError('Failed to save edits');
    }
    setEditing(false);
  };

  const handleFinalSave = async () => {
    setSaving(true);
    setError('');
    try {
      // Make sure we compile first if not done
      if (!compiled) {
        await api.compileBuilderResume(sessionId, interviewSessionId);
      }
      // Save edits if any
      if (editing || editText !== preview?.text) {
        await api.editBuilderResume(sessionId, editText);
      }
      const result = await api.saveBuilderResume(sessionId);
      onSave(result);
    } catch (err) {
      setError('Failed to save resume');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="builder-preview loading-state">Loading preview...</div>;
  }

  const scoreColor = atsScore >= 70 ? '#4caf50' : atsScore >= 40 ? '#ff9800' : '#f44336';

  return (
    <div className="builder-preview">
      <div className="preview-header">
        <h3>Resume Preview</h3>
        <div className="preview-score" style={{ borderColor: scoreColor }}>
          <span className="preview-score-value" style={{ color: scoreColor }}>{atsScore}%</span>
          <span className="preview-score-label">Relevance Score</span>
        </div>
      </div>

      {error && <div className="preview-error">{error}</div>}

      {Object.keys(scoreBreakdown).length > 0 && (
        <div className="preview-breakdown">
          {Object.entries(scoreBreakdown).map(([key, val]) => (
            <div key={key} className="breakdown-pill">
              <span className="pill-label">{key.replace(/_/g, ' ')}</span>
              <span className="pill-value">{Math.round(val)}%</span>
            </div>
          ))}
        </div>
      )}

      {preview?.sources_used?.length > 0 && (
        <div className="preview-sources">
          <span className="sources-label">Sources:</span>
          {preview.sources_used.map((src, idx) => (
            <span key={idx} className={`source-tag source-${src}`}>{src}</span>
          ))}
        </div>
      )}

      <div className="preview-content">
        {editing ? (
          <textarea
            className="preview-editor"
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            rows={25}
          />
        ) : (
          <pre className="preview-text">{editText || preview?.text || 'No content yet'}</pre>
        )}
      </div>

      <div className="preview-actions">
        {!compiled && (
          <button className="btn-compile" onClick={handleCompile} disabled={compiling}>
            {compiling ? 'Compiling...' : 'Compile Resume'}
          </button>
        )}

        {editing ? (
          <button className="btn-primary" onClick={handleSaveEdit}>Save Edits</button>
        ) : (
          <button className="btn-secondary" onClick={() => setEditing(true)}>Edit</button>
        )}

        <button className="btn-primary" onClick={handleFinalSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save as New Version'}
        </button>

        <button className="btn-secondary" onClick={onBack}>Back</button>
      </div>
    </div>
  );
}

export default BuilderPreview;
