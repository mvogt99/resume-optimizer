import React, { useState, useEffect } from 'react';
import SourceSelector from './SourceSelector';
import BuilderInterview from './BuilderInterview';
import BuilderPreview from './BuilderPreview';
import api from '../services/api';
import '../styles/ResumeBuilder.css';

const STEPS = [
  { id: 'base', label: 'Base Resume' },
  { id: 'sources', label: 'Choose Sources' },
  { id: 'interview', label: 'Interview' },
  { id: 'preview', label: 'Preview & Edit' },
  { id: 'done', label: 'Saved' },
];

function ResumeBuilder() {
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Step 1: Base resume
  const [versions, setVersions] = useState([]);
  const [selectedVersionId, setSelectedVersionId] = useState(null);
  const [jobText, setJobText] = useState('');

  // Step 2: Sources
  const [availableSources, setAvailableSources] = useState({});
  const [selectedSources, setSelectedSources] = useState([]);

  // Session
  const [sessionId, setSessionId] = useState(null);
  const [interviewSessionId, setInterviewSessionId] = useState(null);

  // Step 5: Result
  const [savedResult, setSavedResult] = useState(null);

  useEffect(() => {
    loadVersions();
    loadSources();
  }, []);

  const loadVersions = async () => {
    try {
      const data = await api.getResumeVersions();
      setVersions(data.versions || data || []);
    } catch {
      // No versions yet
    }
  };

  const loadSources = async () => {
    try {
      const data = await api.getBuilderSources();
      setAvailableSources(data);
    } catch {
      // Sources endpoint not available
    }
  };

  const handleToggleSource = (key) => {
    setSelectedSources(prev =>
      prev.includes(key) ? prev.filter(s => s !== key) : [...prev, key]
    );
  };

  const handleStartSession = async () => {
    if (!jobText || jobText.length < 50) {
      setError('Job description must be at least 50 characters.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await api.startBuilderSession(selectedVersionId, jobText, selectedSources);
      setSessionId(result.session_id);
      setStep(2); // Go to interview step
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to start builder session.');
    } finally {
      setLoading(false);
    }
  };

  const handleInterviewComplete = (intSessionId) => {
    setInterviewSessionId(intSessionId);
    setStep(3); // Go to preview
  };

  const handleInterviewSkip = () => {
    setStep(3); // Skip to preview
  };

  const handleSaved = (result) => {
    setSavedResult(result);
    setStep(4);
  };

  const handleStartOver = () => {
    setStep(0);
    setSessionId(null);
    setInterviewSessionId(null);
    setSelectedVersionId(null);
    setJobText('');
    setSelectedSources([]);
    setSavedResult(null);
    setError('');
  };

  return (
    <div className="resume-builder">
      <h2>Resume Builder</h2>

      {/* Step indicator */}
      <div className="builder-steps">
        {STEPS.map((s, idx) => (
          <div
            key={s.id}
            className={`builder-step ${idx === step ? 'active' : ''} ${idx < step ? 'completed' : ''}`}
          >
            <span className="builder-step-num">{idx < step ? '\u2713' : idx + 1}</span>
            <span className="builder-step-label">{s.label}</span>
          </div>
        ))}
      </div>

      {error && (
        <div className="builder-error">
          {error}
          <button onClick={() => setError('')}>x</button>
        </div>
      )}

      {/* Step 0: Base resume + job description */}
      {step === 0 && (
        <div className="builder-step-content">
          <div className="builder-base-section">
            <h3>Select Base Resume (optional)</h3>
            <p>Choose an existing resume version as a starting point, or start blank.</p>
            <div className="version-list">
              <div
                className={`version-card ${selectedVersionId === null ? 'selected' : ''}`}
                onClick={() => setSelectedVersionId(null)}
              >
                <span className="version-icon">+</span>
                <span>Start Blank</span>
              </div>
              {versions.map(v => (
                <div
                  key={v.id}
                  className={`version-card ${selectedVersionId === v.id ? 'selected' : ''}`}
                  onClick={() => setSelectedVersionId(v.id)}
                >
                  <span className="version-icon">D</span>
                  <div>
                    <div className="version-name">{v.file_name || v.source || 'Resume'}</div>
                    <div className="version-meta">{v.source} | {v.created_at?.split('T')[0]}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="builder-job-section">
            <h3>Paste Job Description</h3>
            <textarea
              className="job-textarea"
              value={jobText}
              onChange={(e) => setJobText(e.target.value)}
              placeholder="Paste the full job description here (minimum 50 characters)..."
              rows={8}
            />
            <div className="char-count">{jobText.length} characters</div>
          </div>

          <button
            className="btn-primary btn-next"
            onClick={() => setStep(1)}
            disabled={jobText.length < 50}
          >
            Next: Choose Sources
          </button>
        </div>
      )}

      {/* Step 1: Source selection */}
      {step === 1 && (
        <div className="builder-step-content">
          <SourceSelector
            availableSources={availableSources}
            selectedSources={selectedSources}
            onToggle={handleToggleSource}
          />

          <div className="builder-nav">
            <button className="btn-secondary" onClick={() => setStep(0)}>Back</button>
            <button
              className="btn-primary"
              onClick={handleStartSession}
              disabled={loading}
            >
              {loading ? 'Starting...' : 'Next: Interview'}
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Gap interview */}
      {step === 2 && sessionId && (
        <BuilderInterview
          sessionId={sessionId}
          onComplete={handleInterviewComplete}
          onSkip={handleInterviewSkip}
        />
      )}

      {/* Step 3: Preview & edit */}
      {step === 3 && sessionId && (
        <BuilderPreview
          sessionId={sessionId}
          interviewSessionId={interviewSessionId}
          onSave={handleSaved}
          onBack={() => setStep(2)}
        />
      )}

      {/* Step 4: Done */}
      {step === 4 && (
        <div className="builder-step-content builder-done">
          <div className="done-icon">&#10003;</div>
          <h3>Resume Saved!</h3>
          <p>Your resume has been saved as a new version.</p>
          {savedResult && (
            <div className="done-details">
              <div>Version ID: {savedResult.version_id}</div>
              <div>Resume ID: {savedResult.resume_id}</div>
            </div>
          )}
          <p className="done-hint">
            Switch to the <strong>Optimize Resume</strong> tab to run ATS optimization
            on your new resume.
          </p>
          <button className="btn-primary" onClick={handleStartOver}>
            Build Another Resume
          </button>
        </div>
      )}
    </div>
  );
}

export default ResumeBuilder;
