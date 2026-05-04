import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

function ResumeTailor({ postingId, onComplete }) {
  const [result, setResult] = useState(null);
  const [existing, setExisting] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [applying, setApplying] = useState(false);
  const [downloadingFmt, setDownloadingFmt] = useState(null);

  const checkExisting = useCallback(async () => {
    if (!postingId) return;
    try {
      const data = await api.getTailoredResume(postingId);
      setExisting(data);
    } catch {
      setExisting(null);
    }
  }, [postingId]);

  useEffect(() => { checkExisting(); }, [checkExisting]);

  useEffect(() => {
    (async () => {
      try {
        const resp = await api.getTemplates();
        setTemplates(resp?.data?.templates || []);
      } catch {
        // templates optional
      }
    })();
  }, []);

  const handleTailor = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await api.tailorResume(postingId);
      if (data.error) {
        setError(data.error);
      } else {
        setResult(data);
        if (onComplete) onComplete(data);
      }
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to tailor resume');
    } finally {
      setLoading(false);
    }
  };

  const handleApplyToJob = async () => {
    setApplying(true);
    try {
      await api.applyToJob(postingId, selectedTemplate || undefined);
      alert('Application submitted successfully');
    } catch (err) {
      alert('Apply failed: ' + (err?.response?.data?.error || err.message));
    } finally {
      setApplying(false);
    }
  };

  const handleDownload = async (fmt) => {
    if (!selectedTemplate || !displayData?.optimized_text) return;
    setDownloadingFmt(fmt);
    try {
      const resp = await api.downloadTemplate(selectedTemplate, fmt, displayData.optimized_text);
      const blob = resp instanceof Blob ? resp : resp.data;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `resume.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Download failed: ' + (err?.response?.data?.error || err.message));
    } finally {
      setDownloadingFmt(null);
    }
  };

  const displayData = result || (existing && existing.parsed_text ? {
    optimized_text: existing.parsed_text,
    ats_score: existing.metadata?.ats_score || 0,
    score_breakdown: existing.metadata?.score_breakdown || {},
    version_id: existing.id,
  } : null);

  return (
    <div className="tailor-container">
      {!postingId && (
        <div className="empty-state">
          <p>Select a job posting to tailor your resume</p>
        </div>
      )}

      {postingId && (
        <>
          <div className="criteria-actions">
            <button
              className="btn-search"
              onClick={handleTailor}
              disabled={loading}
            >
              {loading ? 'Tailoring...' : existing ? 'Re-Tailor Resume' : 'Tailor Resume'}
            </button>
            {loading && <div className="agent-spinner" />}
          </div>

          {error && <div className="text-error mb-12">{error}</div>}

          {result?.profile_stale && (
            <div
              data-testid="stale-warning"
              style={{
                background: '#fffbeb',
                border: '1px solid #f59e0b',
                borderRadius: 6,
                padding: '10px 14px',
                marginBottom: 12,
                fontSize: 14,
                color: '#92400e',
              }}
            >
              <span>
                ⚠ Your career profile may be outdated
                {result.stale_reason ? ` (${result.stale_reason})` : ''}.
              </span>
              {' '}
              <a href="/deep-profile" data-testid="stale-build-now" style={{ color: '#b45309', fontWeight: 600 }}>
                Rebuild your deep profile
              </a>
            </div>
          )}

          {displayData && (
            <div className="tailor-result">
              <div className="postings-header">
                <h3>Tailored Resume</h3>
                <div className="score-bar">
                  <span
                    className="score-value"
                    style={{
                      fontSize: 24,
                      color: displayData.ats_score >= 70 ? '#4caf50' : displayData.ats_score >= 50 ? '#ff9800' : '#e53935',
                    }}
                  >
                    {displayData.ats_score}
                  </span>
                  <span className="score-label">Relevance Score</span>
                </div>
              </div>

              {displayData.score_breakdown && (
                <div className="posting-scores">
                  {Object.entries(displayData.score_breakdown).map(([key, val]) => (
                    <div className="posting-score-item" key={key}>
                      <div className="score-value">{Math.round(val)}</div>
                      <div className="score-label">{key.replace(/_/g, ' ')}</div>
                    </div>
                  ))}
                </div>
              )}

              {displayData.matching_keywords?.length > 0 && (
                <div className="tailor-keywords">
                  <h4>Matching Keywords:</h4>
                  <div className="skills-tags">
                    {displayData.matching_keywords.slice(0, 20).map((kw, i) => (
                      <span className="skill-tag overlap" key={i}>{kw}</span>
                    ))}
                  </div>
                </div>
              )}

              {displayData.added_keywords?.length > 0 && (
                <div className="tailor-keywords">
                  <h4>Added Keywords:</h4>
                  <div className="skills-tags">
                    {displayData.added_keywords.slice(0, 15).map((kw, i) => (
                      <span className="skill-tag missing" key={i}>{kw}</span>
                    ))}
                  </div>
                </div>
              )}

              <div className="tailor-text-preview">
                {displayData.optimized_text}
              </div>

              <button
                className="btn-copy"
                onClick={() => {
                  navigator.clipboard.writeText(displayData.optimized_text);
                }}
              >
                Copy to Clipboard
              </button>

              {/* Template & Download */}
              <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                {templates.length > 0 && (
                  <select
                    value={selectedTemplate}
                    onChange={e => setSelectedTemplate(e.target.value)}
                    style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd' }}
                    data-testid="template-selector"
                  >
                    <option value="">Select Template</option>
                    {templates.map(t => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                )}
                <button
                  className="btn-save-criteria"
                  onClick={() => handleDownload('pdf')}
                  disabled={!selectedTemplate || downloadingFmt === 'pdf'}
                >
                  {downloadingFmt === 'pdf' ? 'Downloading...' : 'Download PDF'}
                </button>
                <button
                  className="btn-save-criteria"
                  onClick={() => handleDownload('docx')}
                  disabled={!selectedTemplate || downloadingFmt === 'docx'}
                >
                  {downloadingFmt === 'docx' ? 'Downloading...' : 'Download DOCX'}
                </button>
                <button
                  className="btn-search"
                  onClick={handleApplyToJob}
                  disabled={applying}
                >
                  {applying ? 'Applying...' : 'Apply to Job'}
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default ResumeTailor;
