import React, { useState } from 'react';
import api from '../services/api';
import { saveChatHistoryFromMessages } from '../utils/chatHistory';

/**
 * ExpertComparisonMergedView
 *
 * Shown after the user finishes the expert comparison interview.
 * Displays: merge decisions, full editable resume, rescore, save to library, download.
 *
 * Props:
 *   mergedData      {merged_text, decisions}  — from /expert-compare/merge
 *   ourText         string  — our AI version (for rescore comparison)
 *   jobDescription  string
 *   chatMessages    array   — interview chat (for history export)
 *   onContinue      fn      — go back to interview
 *   onReset         fn      — start over from input
 */
function ExpertComparisonMergedView({
  mergedData,
  ourText = '',
  jobDescription = '',
  chatMessages = [],
  onContinue,
  onReset,
}) {
  const [editedText, setEditedText] = useState(mergedData?.merged_text || '');
  const [showDecisions, setShowDecisions] = useState(true);
  const [rescoring, setRescoring] = useState(false);
  const [scoreResult, setScoreResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState(null);
  const [downloadingFmt, setDownloadingFmt] = useState(null);
  const [label, setLabel] = useState('Expert Comparison Merged');

  const decisions = mergedData?.decisions || [];

  const handleRescore = async () => {
    setRescoring(true);
    setScoreResult(null);
    try {
      const [mergedRes, ourRes] = await Promise.all([
        api.scoreResumeText(editedText, jobDescription),
        api.scoreResumeText(ourText, jobDescription),
      ]);
      setScoreResult({
        merged: mergedRes.ats_score,
        original: ourRes.ats_score,
        delta: mergedRes.ats_score - ourRes.ats_score,
      });
    } catch {
      setScoreResult({ error: 'Scoring failed — please try again.' });
    } finally {
      setRescoring(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await api.saveMergedResume(editedText, label);
      setSavedId(res.version_id);
    } catch {
      alert('Save failed. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = (format) => {
    setDownloadingFmt(format);
    api.exportResumeText(editedText, format)
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${label}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(() => alert('Download failed. Please try again.'))
      .finally(() => setDownloadingFmt(null));
  };

  const handleSaveHistory = () => {
    const exportMessages = [
      ...chatMessages,
      { role: 'assistant', content: `[Merged Resume]\n${editedText}` },
      ...decisions.map(d => ({
        role: 'assistant',
        content: `[Decision: ${d.section}] Use ${d.choice} — ${d.reason}`,
      })),
    ];
    saveChatHistoryFromMessages(exportMessages, 'Expert Comparison + Merge');
  };

  const choiceLabel = { ours: 'Our AI', expert: 'Expert AI', hybrid: 'Hybrid' };
  const choiceClass = { ours: 'ec-dec-ours', expert: 'ec-dec-expert', hybrid: 'ec-dec-hybrid' };

  return (
    <div className="ec-merged-view">

      {/* Header */}
      <div className="ec-merged-header">
        <h3 className="ec-merged-title">Your Personalized Resume</h3>
        <div className="ec-merged-header-actions">
          <button className="btn-save-history" onClick={handleSaveHistory}>
            Save Full History
          </button>
          <button className="btn-secondary ec-continue-btn" onClick={onContinue}>
            ← Continue Interview
          </button>
        </div>
      </div>

      {/* Merge decisions */}
      {decisions.length > 0 && (
        <div className="ec-decisions">
          <button
            className="ec-decisions-toggle"
            onClick={() => setShowDecisions(v => !v)}
          >
            {showDecisions ? '▾' : '▸'} Merge Decisions ({decisions.length} sections)
          </button>
          {showDecisions && (
            <div className="ec-decisions-list">
              {decisions.map((d, i) => (
                <div key={i} className="ec-decision-row">
                  <span className="ec-dec-section">{d.section}</span>
                  <span className={`ec-dec-badge ${choiceClass[d.choice] || ''}`}>
                    {choiceLabel[d.choice] || d.choice}
                  </span>
                  <span className="ec-dec-reason">{d.reason}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Editable resume */}
      <div className="ec-merged-editor-section">
        <label className="ec-merged-editor-label">
          Edit your personalized resume below before saving:
        </label>
        <textarea
          className="ec-merged-textarea"
          value={editedText}
          onChange={e => setEditedText(e.target.value)}
          rows={28}
        />
      </div>

      {/* ATS rescore */}
      <div className="ec-merged-rescore-row">
        <button
          className="btn-ec-rescore"
          onClick={handleRescore}
          disabled={rescoring}
        >
          {rescoring ? 'Scoring…' : 'Score This Resume vs Job'}
        </button>
        {scoreResult && !scoreResult.error && (
          <div className="ec-merged-score-result">
            <span className="ec-merged-score-val">{scoreResult.merged}/100</span>
            <span className={`ec-merged-score-delta ${scoreResult.delta >= 0 ? 'positive' : 'negative'}`}>
              {scoreResult.delta >= 0 ? '+' : ''}{scoreResult.delta} vs original
            </span>
          </div>
        )}
        {scoreResult?.error && (
          <span className="ec-merged-score-err">{scoreResult.error}</span>
        )}
      </div>

      {/* Save + download actions */}
      <div className="ec-merged-actions">
        <div className="ec-merged-save-row">
          <input
            className="ec-merged-label-input"
            value={label}
            onChange={e => setLabel(e.target.value)}
            placeholder="Version label…"
          />
          {!savedId ? (
            <button
              className="btn-primary ec-merged-save-btn"
              onClick={handleSave}
              disabled={saving || !editedText.trim()}
            >
              {saving ? 'Saving…' : 'Save to Resume Library'}
            </button>
          ) : (
            <span className="ec-merged-saved-badge">Saved to library ✓</span>
          )}
        </div>

        <div className="ec-merged-download-row">
          {['pdf', 'docx', 'txt'].map(fmt => (
            <button
              key={fmt}
              className="btn-secondary ec-merged-dl-btn"
              onClick={() => handleDownload(fmt)}
              disabled={downloadingFmt === fmt || !editedText.trim()}
            >
              {downloadingFmt === fmt ? '…' : fmt.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <button className="btn-secondary ec-reset-btn" onClick={onReset}>
        Compare a Different Version
      </button>
    </div>
  );
}

export default ExpertComparisonMergedView;
