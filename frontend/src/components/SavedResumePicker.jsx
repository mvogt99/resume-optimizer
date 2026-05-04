import React, { useState, useEffect } from 'react';
import api from '../services/api';

const SOURCE_LABELS = {
  google_drive: 'Google Drive',
  linkedin: 'LinkedIn',
  upload: 'Uploaded',
  local_file: 'Local File',
  builder: 'Builder',
  experience_chat: 'Experience',
  agent_tailor: 'AI Tailor',
};

const SOURCE_COLORS = {
  google_drive: '#4285f4',
  linkedin: '#0a66c2',
  upload: '#6b7280',
  local_file: '#ea580c',
  builder: '#7c3aed',
  experience_chat: '#059669',
  agent_tailor: '#0891b2',
};

function SourceBadge({ source }) {
  const label = SOURCE_LABELS[source] || source;
  const color = SOURCE_COLORS[source] || '#6b7280';
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: '12px',
      fontSize: '11px',
      fontWeight: 600,
      color: '#fff',
      backgroundColor: color,
      marginRight: '6px',
    }}>
      {label}
    </span>
  );
}

function SavedResumePicker({ onSelect }) {
  const [versions, setVersions] = useState([]);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    api.getResumeVersions()
      .then(data => {
        if (!cancelled) setVersions(data.versions || []);
      })
      .catch(() => {
        if (!cancelled) setError('Failed to load saved resumes.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const toggleId = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleUse = () => {
    if (selectedIds.size === 0) return;
    onSelect([...selectedIds]);
  };

  if (loading) {
    return <p style={{ color: '#666', padding: '16px' }}>Loading saved resumes…</p>;
  }

  if (error) {
    return <p style={{ color: '#dc2626', padding: '16px' }}>{error}</p>;
  }

  if (versions.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>
        <p>No saved resumes found.</p>
        <p style={{ fontSize: '13px' }}>Import a resume using Upload File, Google Drive, or LinkedIn first.</p>
      </div>
    );
  }

  const selectedCount = selectedIds.size;
  const btnLabel = selectedCount >= 2
    ? `Compare ${selectedCount} Resumes`
    : selectedCount === 1
      ? 'Use Selected Resume'
      : 'Select a Resume';

  return (
    <div className="saved-resume-picker">
      <p className="picker-hint">
        Select one resume to optimize, or multiple to compare and get a recommendation.
      </p>
      <ul className="version-list">
        {versions.map(v => {
          const isSelected = selectedIds.has(v.id);
          return (
            <li
              key={v.id}
              className={`version-item ${isSelected ? 'selected' : ''}`}
              onClick={() => toggleId(v.id)}
            >
              <div className="version-checkbox">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleId(v.id)}
                  onClick={e => e.stopPropagation()}
                />
              </div>
              <div className="version-info">
                <div className="version-header">
                  <SourceBadge source={v.source} />
                  <span className="version-filename">{v.file_name}</span>
                </div>
                {v.text_preview && (
                  <p className="version-preview">{v.text_preview}</p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <button
        className="btn-primary btn-use-selected"
        onClick={handleUse}
        disabled={selectedCount === 0}
      >
        {btnLabel}
      </button>
    </div>
  );
}

export default SavedResumePicker;
