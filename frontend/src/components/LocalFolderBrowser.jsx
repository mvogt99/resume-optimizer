import React, { useState, useEffect } from 'react';
import api from '../services/api';

const FILE_ICONS = { pdf: '📄', docx: '📝', doc: '📝', txt: '📃' };

function Breadcrumb({ currentPath, homePath, onNavigate }) {
  if (!currentPath) return null;

  const relative = currentPath.startsWith(homePath)
    ? currentPath.slice(homePath.length).replace(/^\//, '')
    : currentPath;
  const parts = relative ? relative.split('/') : [];

  const crumbs = [{ label: '~', path: homePath }];
  let built = homePath;
  for (const part of parts) {
    built = built.replace(/\/$/, '') + '/' + part;
    crumbs.push({ label: part, path: built });
  }

  return (
    <nav className="folder-breadcrumb">
      {crumbs.map((crumb, i) => (
        <React.Fragment key={crumb.path}>
          {i > 0 && <span className="breadcrumb-sep">/</span>}
          {i < crumbs.length - 1 ? (
            <button className="breadcrumb-link" onClick={() => onNavigate(crumb.path)}>
              {crumb.label}
            </button>
          ) : (
            <span className="breadcrumb-current">{crumb.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}

function LocalFolderBrowser({ onImport, onClose }) {
  const [currentPath, setCurrentPath] = useState('');
  const [homePath, setHomePath] = useState('');
  const [dirs, setDirs] = useState([]);
  const [files, setFiles] = useState([]);
  const [selectedPaths, setSelectedPaths] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importProgress, setImportProgress] = useState('');
  const [error, setError] = useState('');

  const loadFolder = async (path) => {
    setLoading(true);
    setError('');
    setSelectedPaths(new Set());
    try {
      const data = await api.browseLocalFolder(path || '');
      setCurrentPath(data.path);
      setDirs(data.dirs || []);
      setFiles(data.files || []);
      if (data.home_path && !homePath) setHomePath(data.home_path);
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to load folder. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFolder('');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const togglePath = (filePath) => {
    setSelectedPaths(prev => {
      const next = new Set(prev);
      if (next.has(filePath)) next.delete(filePath);
      else next.add(filePath);
      return next;
    });
  };

  const handleImport = async () => {
    if (selectedPaths.size === 0) return;
    setImporting(true);
    setError('');

    const paths = [...selectedPaths];
    const versionIds = [];
    const fileNames = [];

    for (let i = 0; i < paths.length; i++) {
      setImportProgress(`Importing ${i + 1} of ${paths.length}…`);
      try {
        const result = await api.importLocalFile(paths[i]);
        versionIds.push(result.version_id);
        fileNames.push(result.file_name);
      } catch (err) {
        const name = paths[i].split('/').pop();
        setError(`Failed to import "${name}": ${err.response?.data?.error || 'unknown error'}`);
        setImporting(false);
        setImportProgress('');
        return;
      }
    }

    setImporting(false);
    setImportProgress('');
    onImport(versionIds, fileNames);
  };

  const selectedCount = selectedPaths.size;
  const btnLabel = importing
    ? importProgress
    : selectedCount >= 2
      ? `Import & Compare ${selectedCount} Resumes`
      : selectedCount === 1
        ? 'Import Selected'
        : 'Select Files to Import';

  const ext = (name) => name.split('.').pop().toLowerCase();
  const icon = (name) => FILE_ICONS[ext(name)] || '📄';

  return (
    <div className="local-folder-browser">
      <Breadcrumb
        currentPath={currentPath}
        homePath={homePath}
        onNavigate={(p) => loadFolder(p)}
      />

      {error && <p className="browser-error">{error}</p>}

      {loading ? (
        <p className="browser-loading">Loading…</p>
      ) : (
        <div className="browser-entries">
          {dirs.length === 0 && files.length === 0 && (
            <p className="browser-empty">No resume files (.pdf, .docx, .doc, .txt) found here.</p>
          )}
          {dirs.map(d => (
            <div
              key={d.path}
              className="browser-entry browser-dir"
              onClick={() => loadFolder(d.path)}
            >
              <span className="entry-icon">📁</span>
              <span className="entry-name">{d.name}</span>
            </div>
          ))}
          {files.map(f => (
            <div
              key={f.path}
              className={`browser-entry browser-file ${selectedPaths.has(f.path) ? 'selected' : ''}`}
              onClick={() => togglePath(f.path)}
            >
              <input
                type="checkbox"
                checked={selectedPaths.has(f.path)}
                onChange={() => togglePath(f.path)}
                onClick={e => e.stopPropagation()}
                style={{ flexShrink: 0 }}
              />
              <span className="entry-icon">{icon(f.name)}</span>
              <span className="entry-name">{f.name}</span>
              <span className="entry-size">{f.size_kb} KB</span>
            </div>
          ))}
        </div>
      )}

      <div className="browser-footer">
        <button className="btn-secondary" onClick={onClose} disabled={importing}>
          Cancel
        </button>
        <button
          className="btn-primary"
          onClick={handleImport}
          disabled={selectedCount === 0 || importing}
        >
          {btnLabel}
        </button>
      </div>
    </div>
  );
}

export default LocalFolderBrowser;
