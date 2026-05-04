import React, { useState, useRef, useEffect } from 'react';
import GDriveFilePicker from './GDriveFilePicker';
import SavedResumePicker from './SavedResumePicker';
import LocalFolderBrowser from './LocalFolderBrowser';
import '../styles/ResumeUpload.css';

const VALID_TYPES = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
];
const MAX_SIZE = 16 * 1024 * 1024;
const MAX_FILES = 10;

function ResumeUpload({
  onUpload,
  onMultiUpload,
  onLinkedInImport,
  onLinkedInFileUpload,
  onGDriveImport,
  onModeChange,
  loading,
  onSavedResumeSelect,
  onLocalImport,
}) {
  const [activeSource, setActiveSource] = useState('upload');
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);   // unified file list
  const [mode, setMode] = useState('compare');
  const [showGDrivePicker, setShowGDrivePicker] = useState(false);
  const [showLinkedInUpload, setShowLinkedInUpload] = useState(false);
  const [linkedInFile, setLinkedInFile] = useState(null);
  const [uploadingLinkedIn, setUploadingLinkedIn] = useState(false);
  const fileInputRef = useRef(null);
  const linkedInFileRef = useRef(null);

  // Notify parent of mode whenever file count or mode changes
  useEffect(() => {
    if (onModeChange) onModeChange(selectedFiles.length >= 2 ? mode : 'merge');
  }, [selectedFiles, mode, onModeChange]);

  // ── File validation and merge ────────────────────────────────────────────

  const addFiles = (incoming) => {
    const valid = [];
    const skipped = [];
    for (const f of Array.from(incoming)) {
      if (!VALID_TYPES.includes(f.type)) { skipped.push(f.name); continue; }
      if (f.size > MAX_SIZE)             { skipped.push(f.name); continue; }
      valid.push(f);
    }
    if (skipped.length) alert(`${skipped.length} file(s) skipped (unsupported type or > 16 MB).`);
    setSelectedFiles(prev => {
      const names = new Set(prev.map(f => f.name));
      const deduped = valid.filter(f => !names.has(f.name));
      return [...prev, ...deduped].slice(0, MAX_FILES);
    });
  };

  const removeFile = (idx) => setSelectedFiles(prev => prev.filter((_, i) => i !== idx));

  // ── Drag-and-drop ────────────────────────────────────────────────────────

  const handleDrag = (e) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(e.type === 'dragenter' || e.type === 'dragover');
  };

  const handleDrop = (e) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  };

  // ── File input ───────────────────────────────────────────────────────────

  const handleChange = (e) => {
    if (e.target.files?.length) addFiles(e.target.files);
    e.target.value = '';          // reset so same file can be re-added after remove
  };

  // ── Submit ───────────────────────────────────────────────────────────────

  const handleSubmit = () => {
    if (selectedFiles.length === 0) return;
    if (selectedFiles.length === 1) {
      onUpload(selectedFiles[0]);
    } else {
      onMultiUpload(selectedFiles[0], selectedFiles.slice(1));
    }
  };

  // ── LinkedIn file upload ─────────────────────────────────────────────────

  const handleLinkedInFileUpload = async () => {
    if (!linkedInFile || !onLinkedInFileUpload) return;
    setUploadingLinkedIn(true);
    try {
      await onLinkedInFileUpload(linkedInFile);
      setLinkedInFile(null);
      setShowLinkedInUpload(false);
    } catch {
      alert('Failed to upload LinkedIn profile. Please try again.');
    } finally {
      setUploadingLinkedIn(false);
    }
  };

  const linkedInValidTypes = [
    'application/json', 'text/xml', 'application/xml',
    'application/pdf', 'text/plain',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
  ];

  // ── Derived labels ───────────────────────────────────────────────────────

  const n = selectedFiles.length;
  const continueBtnLabel = n === 0
    ? 'Continue'
    : n === 1
      ? 'Continue'
      : mode === 'compare'
        ? `Compare ${n} Resumes`
        : `Continue with ${n} Resumes`;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="resume-upload">
      <h2>Select Your Resume</h2>
      <p className="subtitle">Choose a source to get started</p>

      {/* Source tab bar */}
      <div className="source-tabs">
        {['upload', 'saved', 'local'].map(src => (
          <button
            key={src}
            className={`source-tab ${activeSource === src ? 'active' : ''}`}
            onClick={() => setActiveSource(src)}
          >
            {src === 'upload' ? 'Upload File' : src === 'saved' ? 'Saved Resumes' : 'Local Folder'}
          </button>
        ))}
      </div>

      {/* Saved Resumes tab */}
      {activeSource === 'saved' && (
        <SavedResumePicker
          onSelect={(ids) => onSavedResumeSelect && onSavedResumeSelect(ids)}
        />
      )}

      {/* Local Folder tab */}
      {activeSource === 'local' && (
        <LocalFolderBrowser
          onImport={(versionIds) => onLocalImport && onLocalImport(versionIds)}
          onClose={() => setActiveSource('upload')}
        />
      )}

      {/* Upload File tab */}
      {activeSource === 'upload' && (
        <div className="upload-options">

          {/* Drop zone */}
          <div
            className={`upload-area ${dragActive ? 'drag-active' : ''} ${n > 0 ? 'has-file' : ''}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleChange}
              accept=".pdf,.doc,.docx,.txt"
              className="hidden"
            />
            <p className="upload-text">
              <strong>Click to upload</strong> or drag and drop
            </p>
            <p className="upload-hint">PDF, DOCX, DOC, TXT · Up to {MAX_FILES} files · Max 16 MB each</p>
          </div>

          {/* Selected file list */}
          {n > 0 && (
            <ul className="upload-file-list">
              {selectedFiles.map((f, i) => (
                <li key={f.name + i} className="upload-file-item">
                  <span className="upload-file-name">{f.name}</span>
                  <span className="upload-file-size">{(f.size / 1024).toFixed(1)} KB</span>
                  <button
                    className="btn-remove-small"
                    onClick={() => removeFile(i)}
                    title="Remove"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* Mode toggle — visible when 2+ files */}
          {n >= 2 && (
            <div className="mode-toggle-section">
              <p className="mode-label">How would you like to handle these resumes?</p>
              <div className="mode-options">
                {[
                  { value: 'compare', label: 'Compare Mode', hint: 'Rank resumes by ATS score and get a recommendation' },
                  { value: 'merge',   label: 'Merge Mode',   hint: 'Combine resumes for richer optimization context' },
                ].map(opt => (
                  <label key={opt.value} className="mode-radio">
                    <input
                      type="radio"
                      name="resume-mode"
                      value={opt.value}
                      checked={mode === opt.value}
                      onChange={() => {
                        setMode(opt.value);
                        if (onModeChange) onModeChange(opt.value);
                      }}
                    />
                    <span className="mode-label-text">
                      <strong>{opt.label}</strong>
                      <small>{opt.hint}</small>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="divider"><span>or</span></div>

          <div className="import-buttons">
            <button className="btn-linkedin" onClick={onLinkedInImport} disabled={loading}>
              {loading ? 'Importing...' : 'Import from LinkedIn'}
            </button>
            <button
              className="btn-linkedin-upload"
              onClick={() => setShowLinkedInUpload(!showLinkedInUpload)}
              disabled={loading}
            >
              Upload LinkedIn Profile
            </button>
            <button className="btn-gdrive" onClick={() => setShowGDrivePicker(true)} disabled={loading}>
              Browse Google Drive
            </button>
          </div>

          {showLinkedInUpload && (
            <div className="linkedin-upload-section">
              <p className="linkedin-upload-hint">
                Upload your LinkedIn profile export (JSON, XML, DOCX, PDF, or TXT)
              </p>
              <input
                ref={linkedInFileRef}
                type="file"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f && !linkedInValidTypes.includes(f.type)) {
                    alert('Accepted formats: JSON, XML, DOCX, PDF, TXT');
                    return;
                  }
                  setLinkedInFile(f || null);
                }}
                accept=".json,.xml,.docx,.doc,.pdf,.txt"
                className="hidden"
              />
              <div className="linkedin-upload-controls">
                <button className="btn-choose-file" onClick={() => linkedInFileRef.current?.click()}>
                  {linkedInFile ? linkedInFile.name : 'Choose File'}
                </button>
                {linkedInFile && (
                  <button
                    className="btn-upload-linkedin"
                    onClick={handleLinkedInFileUpload}
                    disabled={uploadingLinkedIn}
                  >
                    {uploadingLinkedIn ? 'Uploading...' : 'Upload & Import'}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Google Drive picker modal */}
      {showGDrivePicker && (
        <GDriveFilePicker
          onImport={(resumeId) => { setShowGDrivePicker(false); onGDriveImport(resumeId); }}
          onClose={() => setShowGDrivePicker(false)}
        />
      )}

      {/* Continue button — Upload tab only */}
      {activeSource === 'upload' && n > 0 && (
        <button onClick={handleSubmit} className="btn-primary btn-next">
          {continueBtnLabel}
        </button>
      )}
    </div>
  );
}

export default ResumeUpload;
