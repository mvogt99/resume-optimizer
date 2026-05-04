import React, { useState } from 'react';
import api from '../services/api';

const ARTIFACT_ORDER = [
  'tailored_resume',
  'cover_letter',
  'gap_report',
  'keyword_map',
  'interview_seeds',
  'linkedin_summary',
  'one_pager',
];

const ARTIFACT_LABELS = {
  tailored_resume:  'Tailored Resume',
  cover_letter:     'Cover Letter',
  gap_report:       'Gap Report',
  keyword_map:      'Keyword Map',
  interview_seeds:  'Interview Seeds',
  linkedin_summary: 'LinkedIn Summary',
  one_pager:        'One-Pager',
};

const ARTIFACT_ICONS = {
  tailored_resume:  '📄',
  cover_letter:     '✉️',
  gap_report:       '📊',
  keyword_map:      '🗺️',
  interview_seeds:  '💬',
  linkedin_summary: '🔗',
  one_pager:        '📋',
};

function ArtifactContent({ artifact }) {
  const [copied, setCopied] = useState(false);

  if (!artifact) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(artifact.content || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="artifact-content">
      {artifact.error && (
        <div className="artifact-content-error">
          Generation failed: {artifact.error}
        </div>
      )}
      {artifact.content ? (
        <>
          <div className="artifact-content-toolbar">
            <span className="artifact-word-count">
              {artifact.word_count} words
            </span>
            <button className="btn-artifact-copy" onClick={handleCopy}>
              {copied ? 'Copied \u2713' : 'Copy'}
            </button>
          </div>
          <pre className="artifact-content-text">{artifact.content}</pre>
        </>
      ) : !artifact.error ? (
        <div className="artifact-content-empty">No content generated.</div>
      ) : null}
    </div>
  );
}

function ArtifactPanel({ resumeId, jobDescText }) {
  const [artifacts, setArtifacts] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('tailored_resume');
  const [summary, setSummary] = useState(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await api.generateAlignmentArtifacts(resumeId, jobDescText);
      setArtifacts(result.artifacts || {});
      setSummary(result.summary || null);
      // default to first available tab
      const first = ARTIFACT_ORDER.find(t => result.artifacts?.[t]);
      if (first) setActiveTab(first);
    } catch (err) {
      setError(
        err.response?.data?.error ||
        err.message ||
        'Failed to generate documents.'
      );
    } finally {
      setLoading(false);
    }
  };

  if (!artifacts) {
    return (
      <div className="artifact-panel artifact-panel-empty">
        <div className="artifact-generate-prompt">
          <div className="artifact-prompt-body">
            <span className="artifact-prompt-icon">&#128196;</span>
            <div>
              <h4>Generate Career Documents</h4>
              <p>
                Create 7 tailored documents: resume rewrite, cover letter,
                gap report, ATS keyword map, interview prep seeds,
                LinkedIn summary, and executive one-pager.
              </p>
            </div>
          </div>
          <button
            className="btn-generate-artifacts"
            onClick={handleGenerate}
            disabled={loading || !resumeId || !jobDescText}
          >
            {loading ? (
              <><span className="artifact-spinner" /> Generating&hellip;</>
            ) : (
              'Generate Documents'
            )}
          </button>
        </div>
        {error && <div className="artifact-error">{error}</div>}
      </div>
    );
  }

  const availableTabs = ARTIFACT_ORDER.filter(t => artifacts[t]);

  return (
    <div className="artifact-panel">
      {summary && (
        <div className="artifact-summary-bar">
          <span>{summary.generated_count}/{summary.total} generated</span>
          {summary.failed_count > 0 && (
            <span className="artifact-summary-failed">
              &nbsp;&bull;&nbsp;{summary.failed_count} failed
            </span>
          )}
          <span className="artifact-summary-words">
            &nbsp;&bull;&nbsp;{summary.total_word_count.toLocaleString()} total words
          </span>
        </div>
      )}

      <div className="artifact-tabs" role="tablist">
        {availableTabs.map(t => {
          const art = artifacts[t];
          return (
            <button
              key={t}
              role="tab"
              aria-selected={activeTab === t}
              className={[
                'artifact-tab',
                activeTab === t ? 'active' : '',
                art?.error ? 'has-error' : '',
              ].join(' ')}
              onClick={() => setActiveTab(t)}
              title={ARTIFACT_LABELS[t]}
            >
              <span className="artifact-tab-icon">
                {ARTIFACT_ICONS[t]}
              </span>
              <span className="artifact-tab-label">
                {ARTIFACT_LABELS[t]}
              </span>
              {art?.word_count > 0 && (
                <span className="artifact-tab-wc">{art.word_count}w</span>
              )}
              {art?.error && (
                <span className="artifact-tab-err" title={art.error}>!</span>
              )}
            </button>
          );
        })}
      </div>

      <ArtifactContent key={activeTab} artifact={artifacts[activeTab]} />
    </div>
  );
}

export default ArtifactPanel;
