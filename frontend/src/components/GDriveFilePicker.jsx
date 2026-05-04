import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import '../styles/ResumeUpload.css';

function GDriveFilePicker({ onImport, onClose }) {
  const [items, setItems] = useState([]);
  const [selectedFileId, setSelectedFileId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState('');
  // Breadcrumb trail: [{id, name}, ...] — first entry is root
  const [breadcrumb, setBreadcrumb] = useState([{ id: null, name: 'My Drive' }]);

  const currentFolderId = breadcrumb[breadcrumb.length - 1].id;

  const loadFolder = useCallback(async (folderId) => {
    setLoading(true);
    setError('');
    setSelectedFileId(null);
    try {
      const data = folderId
        ? await api.listGDriveFiles(null, folderId)
        : await api.listGDriveFiles();
      setItems(data.files || []);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load Google Drive files.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFolder(currentFolderId);
  }, [currentFolderId, loadFolder]);

  const navigateInto = (folder) => {
    setBreadcrumb((prev) => [...prev, { id: folder.id, name: folder.name }]);
  };

  const navigateTo = (index) => {
    setBreadcrumb((prev) => prev.slice(0, index + 1));
  };

  const handleImport = async () => {
    if (!selectedFileId) return;
    setImporting(true);
    setError('');
    try {
      const result = await api.importGDriveFile(selectedFileId);
      onImport(result.resume_id);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to import file.');
    } finally {
      setImporting(false);
    }
  };

  const typeIcon = (item) => {
    if (item.isFolder) return '\uD83D\uDCC1';
    const mime = item.mimeType || '';
    if (mime.includes('pdf')) return '\uD83D\uDCD5';
    if (mime.includes('word') || mime.includes('document')) return '\uD83D\uDCD8';
    if (mime.includes('text')) return '\uD83D\uDCDD';
    if (mime.includes('presentation')) return '\uD83D\uDCCA';
    if (mime.includes('spreadsheet') || mime.includes('excel')) return '\uD83D\uDCCA';
    return '\uD83D\uDCC4';
  };

  const formatSize = (bytes) => {
    if (!bytes) return '\u2014';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (isoStr) => {
    if (!isoStr) return '\u2014';
    const d = new Date(isoStr);
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
      + ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  };

  const handleItemClick = (item) => {
    if (item.isFolder) {
      navigateInto(item);
    } else {
      setSelectedFileId(item.id);
    }
  };

  return (
    <div className="gdrive-picker-overlay" onClick={onClose}>
      <div className="gdrive-picker-modal" onClick={(e) => e.stopPropagation()}>
        <div className="gdrive-picker-header">
          <h3>Select Resume from Google Drive</h3>
          <button className="gdrive-picker-close" onClick={onClose}>&times;</button>
        </div>

        <div className="gdrive-picker-breadcrumb">
          {breadcrumb.map((crumb, i) => (
            <span key={crumb.id || 'root'}>
              {i > 0 && <span className="gdrive-picker-breadcrumb-sep">/</span>}
              <button
                className={`gdrive-picker-breadcrumb-btn ${i === breadcrumb.length - 1 ? 'current' : ''}`}
                onClick={() => navigateTo(i)}
                disabled={i === breadcrumb.length - 1}
              >
                {crumb.name}
              </button>
            </span>
          ))}
        </div>

        {error && <div className="gdrive-picker-error">{error}</div>}

        <div className="gdrive-picker-body">
          {loading ? (
            <div className="gdrive-picker-loading">
              <div className="spinner"></div>
              <p>Loading...</p>
            </div>
          ) : items.length === 0 ? (
            <p className="gdrive-picker-empty">This folder is empty.</p>
          ) : (
            <>
              <div className="gdrive-picker-colheader">
                <span className="gdrive-picker-col-name">Name</span>
                <span className="gdrive-picker-col-size">Size</span>
                <span className="gdrive-picker-col-date">Modified</span>
              </div>
              <ul className="gdrive-picker-list">
                {items.map((item) => (
                  <li
                    key={item.id}
                    className={
                      `gdrive-picker-item` +
                      (selectedFileId === item.id ? ' selected' : '') +
                      (item.isFolder ? ' folder' : '') +
                      (!item.isFolder && !item.supported ? ' unsupported' : '')
                    }
                    onClick={() => item.supported ? handleItemClick(item) : null}
                    onDoubleClick={() => item.isFolder ? navigateInto(item) : null}
                    title={!item.supported ? 'Unsupported file type' : ''}
                  >
                    <span className="gdrive-picker-col-name">
                      <span className="gdrive-picker-icon">{typeIcon(item)}</span>
                      <span className="gdrive-picker-name">{item.name}</span>
                    </span>
                    <span className="gdrive-picker-col-size">{item.isFolder ? '\u2014' : formatSize(item.size)}</span>
                    <span className="gdrive-picker-col-date">{formatDate(item.modifiedTime)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        <div className="gdrive-picker-footer">
          <button className="btn-cancel" onClick={onClose}>Cancel</button>
          <button
            className="btn-gdrive"
            onClick={handleImport}
            disabled={!selectedFileId || importing}
          >
            {importing ? 'Importing...' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default GDriveFilePicker;
