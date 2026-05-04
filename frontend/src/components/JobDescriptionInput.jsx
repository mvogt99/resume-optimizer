import React, { useState } from 'react';
import '../styles/JobDescriptionInput.css';

function JobDescriptionInput({ onSubmit, onBack, initialText }) {
  const [jobDescription, setJobDescription] = useState(initialText || '');
  const [pasteMode, setPasteMode] = useState(true);

  const handleSubmit = () => {
    if (jobDescription.trim().length < 50) {
      alert('Please enter a more detailed job description (at least 50 characters)');
      return;
    }
    onSubmit(jobDescription);
  };

  return (
    <div className="job-description-input">
      <h2>Enter Job Description</h2>
      <p className="subtitle">
        Paste the job description from the position you're applying for
      </p>

      <div className="input-mode-toggle">
        <button
          className={`mode-btn ${pasteMode ? 'active' : ''}`}
          onClick={() => setPasteMode(true)}
        >
          📋 Paste Text
        </button>
        <button
          className={`mode-btn ${!pasteMode ? 'active' : ''}`}
          onClick={() => setPasteMode(false)}
        >
          📁 Upload File
        </button>
      </div>

      {pasteMode ? (
        <div className="textarea-container">
          <textarea
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the complete job description here...

Example:
Position: Senior Software Engineer

We are seeking an experienced Software Engineer with:
- 5+ years of Python development
- Experience with Flask/Django frameworks
- Strong background in REST API development
- Knowledge of Docker and containerization
- Database design (PostgreSQL preferred)
- Git version control
..."
            rows={15}
          />
          <div className="char-count">
            {jobDescription.length} characters
            {jobDescription.length > 0 && jobDescription.length < 50 && (
              <span className="warning"> (minimum 50 required)</span>
            )}
          </div>
        </div>
      ) : (
        <div className="upload-container">
          <div className="upload-box">
            <p>📄 Upload job description file</p>
            <input type="file" accept=".txt,.pdf,.doc,.docx" />
            <p className="hint">Supported: TXT, PDF, DOC, DOCX</p>
          </div>
        </div>
      )}

      <div className="button-group">
        <button onClick={onBack} className="btn-secondary">
          ← Back
        </button>
        <button
          onClick={handleSubmit}
          className="btn-primary"
          disabled={jobDescription.trim().length < 50}
        >
          Optimize Resume →
        </button>
      </div>
    </div>
  );
}

export default JobDescriptionInput;
