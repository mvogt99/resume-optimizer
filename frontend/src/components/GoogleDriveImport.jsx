import React, { useState, useEffect } from 'react';
import api from '../services/api';
import '../styles/GoogleDriveImport.css';

function GoogleDriveImport({ onResumeImported }) {
  const [files, setFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [importing, setImporting] = useState(false);
  const [importProgress, setImportProgress] = useState({});
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingVersion, setEditingVersion] = useState(null);
  const [editedText, setEditedText] = useState('');

  const loadFiles = async () => {
    try {
      setLoading(true);
      const response = await api.listGDriveFiles('Resumes');
      setFiles(response.files || []);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load files from Google Drive');
    } finally {
      setLoading(false);
    }
  };

  const loadVersions = async () => {
    try {
      const response = await api.getResumeVersions();
      setVersions(response.versions || []);
    } catch (err) {
      // silently fail — versions are supplementary
    }
  };

  useEffect(() => {
    loadFiles();
    loadVersions();
  }, []);

  const handleFileSelect = (fileId) => {
    const next = new Set(selectedFiles);
    if (next.has(fileId)) next.delete(fileId);
    else next.add(fileId);
    setSelectedFiles(next);
  };

  const handleImport = async () => {
    if (selectedFiles.size === 0) return;
    setImporting(true);

    for (const fileId of selectedFiles) {
      setImportProgress(prev => ({ ...prev, [fileId]: { status: 'importing', message: 'Importing...' } }));
      try {
        const result = await api.importGDriveFile(fileId);
        setImportProgress(prev => ({ ...prev, [fileId]: { status: 'success', message: 'Done' } }));
        if (onResumeImported) onResumeImported(result.resume_id);
      } catch (err) {
        setImportProgress(prev => ({ ...prev, [fileId]: { status: 'error', message: 'Failed' } }));
      }
    }

    setImporting(false);
    setSelectedFiles(new Set());
    loadVersions();
    setTimeout(() => setImportProgress({}), 3000);
  };

  const handleReimport = async (versionId) => {
    setImportProgress(prev => ({ ...prev, [`v-${versionId}`]: { status: 'importing', message: 'Re-importing...' } }));
    try {
      await api.reimportGDriveFile(versionId);
      setImportProgress(prev => ({ ...prev, [`v-${versionId}`]: { status: 'success', message: 'Updated' } }));
      loadVersions();
      setTimeout(() => setImportProgress(prev => { const n = {...prev}; delete n[`v-${versionId}`]; return n; }), 3000);
    } catch (err) {
      setImportProgress(prev => ({ ...prev, [`v-${versionId}`]: { status: 'error', message: 'Failed' } }));
    }
  };

  const handleEditVersion = async (versionId) => {
    try {
      const full = await api.getResumeVersion(versionId);
      setEditingVersion(versionId);
      setEditedText(full.parsed_text || '');
    } catch (err) {
      setError('Failed to load version');
    }
  };

  const handleSaveEdit = async () => {
    try {
      await api.updateResumeVersion(editingVersion, editedText);
      setEditingVersion(null);
      setEditedText('');
      loadVersions();
    } catch (err) {
      setError('Failed to save changes');
    }
  };

  const getFileIcon = (fileType) => {
    const icons = { pdf: '\u{1F4C4}', docx: '\u{1F4DD}', doc: '\u{1F4DD}', gdoc: '\u{1F4D8}', txt: '\u{1F4C3}' };
    return icons[fileType] || '\u{1F4C1}';
  };

  const formatSize = (bytes) => {
    if (!bytes) return '';
    const kb = bytes / 1024;
    return kb > 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${Math.round(kb)} KB`;
  };

  const formatDate = (d) => d ? new Date(d).toLocaleDateString() : '';

  return (
    <div className="gdrive-import">
      <h2>Import from Google Drive</h2>

      {error && <div className="gdrive-error">{error}<button onClick={() => setError(null)}>&times;</button></div>}

      <div className="gdrive-panels">
        {/* File Browser */}
        <div className="gdrive-panel">
          <div className="gdrive-panel-header">
            <h3>Resumes Folder</h3>
            <button
              className="btn-import"
              disabled={selectedFiles.size === 0 || importing}
              onClick={handleImport}
            >
              {importing ? 'Importing...' : `Import (${selectedFiles.size})`}
            </button>
          </div>

          {loading ? (
            <div className="gdrive-loading">Loading files...</div>
          ) : files.length === 0 ? (
            <div className="gdrive-empty">No files found in Resumes folder</div>
          ) : (
            <div className="gdrive-file-list">
              {files.map(f => (
                <label key={f.id} className={`gdrive-file-item ${!f.supported ? 'unsupported' : ''}`}>
                  <input
                    type="checkbox"
                    checked={selectedFiles.has(f.id)}
                    onChange={() => handleFileSelect(f.id)}
                    disabled={!f.supported}
                  />
                  <span className="file-icon">{getFileIcon(f.file_type)}</span>
                  <span className="file-name">{f.name}</span>
                  <span className="file-meta">{formatSize(f.size)} {formatDate(f.modified_time)}</span>
                  {importProgress[f.id] && (
                    <span className={`import-status import-${importProgress[f.id].status}`}>
                      {importProgress[f.id].message}
                    </span>
                  )}
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Imported Versions */}
        <div className="gdrive-panel">
          <h3>Imported Versions</h3>
          {versions.length === 0 ? (
            <div className="gdrive-empty">No imported resumes yet</div>
          ) : (
            <div className="gdrive-versions-list">
              {versions.map(v => (
                <div key={v.id} className="version-item">
                  <div className="version-header">
                    <span className="source-badge">{v.source}</span>
                    <span className="version-name">{v.file_name}</span>
                    <span className="version-type">{v.file_type}</span>
                  </div>
                  <div className="version-preview">{v.text_preview}</div>
                  <div className="version-actions">
                    <button className="btn-edit-version" onClick={() => handleEditVersion(v.id)}>
                      View / Edit
                    </button>
                    {v.source === 'google_drive' && (
                      <button className="btn-reimport" onClick={() => handleReimport(v.id)}>
                        {importProgress[`v-${v.id}`]?.status === 'importing' ? 'Re-importing...' : 'Re-import'}
                      </button>
                    )}
                  </div>
                  {importProgress[`v-${v.id}`] && (
                    <span className={`import-status import-${importProgress[`v-${v.id}`].status}`}>
                      {importProgress[`v-${v.id}`].message}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Edit Modal */}
      {editingVersion && (
        <div className="gdrive-modal-overlay">
          <div className="gdrive-modal">
            <h3>Edit Resume Text</h3>
            <textarea
              value={editedText}
              onChange={e => setEditedText(e.target.value)}
              rows={20}
            />
            <div className="gdrive-modal-actions">
              <button className="btn-save" onClick={handleSaveEdit}>Save</button>
              <button className="btn-cancel" onClick={() => { setEditingVersion(null); setEditedText(''); }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default GoogleDriveImport;
