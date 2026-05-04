import React from 'react';

/**
 * KeywordMatchReview — confirm/select stage for the equivalency match flow.
 *
 * Props:
 *   exactMatches      [{keyword, equivalent_phrase, confidence, status}]
 *   suggestions       [{keyword, saved_keyword, equivalent_phrase, confidence, rationale, status}]
 *   unmatched         [str]
 *   confirmedExact    Set<number>   — indices of accepted exact matches
 *   confirmedSugg     Set<number>   — indices of accepted suggestions
 *   selectedForInterview Set<str>  — unmatched keywords selected for interview
 *   notApplicable     Set<str>      — keywords marked not applicable
 *   onToggleExact     fn(idx)
 *   onToggleSugg      fn(idx)
 *   onToggleInterview fn(kw)
 *   onMarkNA          fn(kw)
 *   onGenerate        fn()          — generate rewrites from confirmed
 *   onInterview       fn()          — generate + interview selected keywords first
 *   onClose           fn()
 *   generating        bool
 */
function KeywordMatchReview({
  exactMatches = [],
  suggestions = [],
  unmatched = [],
  confirmedExact,
  confirmedSugg,
  selectedForInterview,
  notApplicable,
  onToggleExact,
  onToggleSugg,
  onToggleInterview,
  onMarkNA,
  onGenerate,
  onInterview,
  onClose,
  generating = false,
}) {
  const totalConfirmed = [...confirmedExact].length + [...confirmedSugg].length;
  const interviewCount = selectedForInterview.size;  // Set.size, not array.length
  const interviewable = unmatched.filter(kw => !notApplicable.has(kw));

  return (
    <div className="keq-panel">
      <div className="keq-header">
        <h4 className="keq-title">Keyword Match Review</h4>
        <button className="btn-secondary keq-close-btn" onClick={onClose}>✕</button>
      </div>

      <p className="keq-match-intro">
        Review how your saved experience maps to this job's missing keywords.
        Confirm or deselect matches, then select any remaining keywords you'd like
        to address via a focused interview.
      </p>

      {/* ── Exact matches ─────────────────────────────────────────────── */}
      {exactMatches.length > 0 && (
        <div className="keq-match-section">
          <h5 className="keq-match-section-title">
            Exact Matches <span className="keq-match-count">{exactMatches.length}</span>
          </h5>
          {exactMatches.map((m, i) => (
            <div key={i} className={`keq-match-row ${confirmedExact.has(i) ? 'keq-match-confirmed' : 'keq-match-rejected'}`}>
              <label className="keq-match-check">
                <input
                  type="checkbox"
                  checked={confirmedExact.has(i)}
                  onChange={() => onToggleExact(i)}
                />
              </label>
              <div className="keq-match-body">
                <span className="keq-match-kw">{m.keyword}</span>
                <span className="keq-match-arrow">→</span>
                <span className="keq-match-phrase">{m.equivalent_phrase}</span>
              </div>
              <span className="keq-match-conf">{Math.round(m.confidence * 100)}%</span>
            </div>
          ))}
        </div>
      )}

      {/* ── LLM suggestions ───────────────────────────────────────────── */}
      {suggestions.length > 0 && (
        <div className="keq-match-section">
          <h5 className="keq-match-section-title">
            Semantic Matches <span className="keq-match-count keq-match-count--caution">{suggestions.length}</span>
            <span className="keq-match-caveat"> — AI-suggested, please confirm</span>
          </h5>
          {suggestions.map((s, i) => (
            <div key={i} className={`keq-match-row ${confirmedSugg.has(i) ? 'keq-match-confirmed' : 'keq-match-rejected'}`}>
              <label className="keq-match-check">
                <input
                  type="checkbox"
                  checked={confirmedSugg.has(i)}
                  onChange={() => onToggleSugg(i)}
                />
              </label>
              <div className="keq-match-body">
                <span className="keq-match-kw">{s.keyword}</span>
                <span className="keq-match-arrow">→</span>
                <span className="keq-match-phrase">{s.equivalent_phrase}</span>
                {s.rationale && (
                  <span className="keq-match-rationale">{s.rationale}</span>
                )}
              </div>
              <span className="keq-match-conf keq-match-conf--caution">
                ~{Math.round(s.confidence * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Unmatched keywords ────────────────────────────────────────── */}
      {unmatched.length > 0 && (
        <div className="keq-match-section keq-match-section--unmatched">
          <h5 className="keq-match-section-title">
            Unmatched Keywords <span className="keq-match-count keq-match-count--missing">{unmatched.length}</span>
            <span className="keq-match-caveat"> — select to address in a focused interview</span>
          </h5>
          {unmatched.map((kw, i) => {
            const isNA = notApplicable.has(kw);
            const isSelected = selectedForInterview.has(kw);
            return (
              <div key={i} className={`keq-match-row keq-match-row--unmatched ${isNA ? 'keq-match-na' : ''}`}>
                <label className="keq-match-check">
                  <input
                    type="checkbox"
                    checked={isSelected && !isNA}
                    disabled={isNA}
                    onChange={() => onToggleInterview(kw)}
                  />
                </label>
                <div className="keq-match-body">
                  <span className={`keq-match-kw ${isNA ? 'keq-match-kw--na' : ''}`}>{kw}</span>
                  {isNA && <span className="keq-na-badge">Not applicable</span>}
                </div>
                {!isNA ? (
                  <button
                    className="btn-xs keq-na-btn"
                    onClick={() => onMarkNA(kw)}
                    title="Mark as not applicable — won't be asked again"
                  >
                    Skip forever
                  </button>
                ) : (
                  <button
                    className="btn-xs keq-na-btn keq-na-btn--undo"
                    onClick={() => onMarkNA(kw)}
                  >
                    Undo
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Actions ───────────────────────────────────────────────────── */}
      <div className="keq-match-actions">
        <button
          className="btn-primary"
          onClick={onGenerate}
          disabled={generating || totalConfirmed === 0}
        >
          {generating ? 'Generating…' : `Generate Rewrites (${totalConfirmed} matches)`}
        </button>

        {interviewable.length > 0 && (
          <button
            className="btn-secondary"
            onClick={onInterview}
            disabled={generating || interviewCount === 0}
          >
            {interviewCount > 0
              ? `+ Interview me about ${interviewCount} selected keyword${interviewCount > 1 ? 's' : ''}`
              : 'Select keywords above to interview'}
          </button>
        )}

        <button className="btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}

export default KeywordMatchReview;
