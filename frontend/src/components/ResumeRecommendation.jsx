import React from 'react';

/**
 * ResumeRecommendation — Step 2.5 in the wizard.
 *
 * Shows ranked resume cards with ATS scores, score breakdowns,
 * matching/missing keyword chips, and an LLM-generated rationale.
 * User can accept the top recommendation or override by selecting another.
 *
 * Props:
 *   recommendation: object — response from POST /api/resumes/compare
 *   loading: bool — show spinner while compare API call is in-flight
 *   onSelect: (resume_id, resume_version_id) => void — called when user picks a resume
 *   onRecompare: () => void — called when user wants to go back and re-compare
 *   mode: 'compare' | 'merge' — display mode (default: 'compare')
 *   onModeChange: (mode) => void — optional, fires when mode toggle clicked
 */
function ResumeRecommendation({ recommendation, loading, onSelect, onRecompare, mode = 'compare', onModeChange }) {

  if (loading) {
    return (
      <div className="recommendation-container" data-testid="recommendation-loading">
        <div className="recommendation-header">
          <h2>Analyzing Your Resumes…</h2>
          <p>Scoring each resume against the job description. This may take a moment.</p>
        </div>
        <div className="recommendation-spinner">
          <div className="spinner" />
          <span>Comparing resumes with NLP scoring…</span>
        </div>
      </div>
    );
  }

  if (!recommendation) {
    return null;
  }

  const { rankings = [], recommended_resume_id, recommended_version_id, rationale } = recommendation;

  const handleSelect = (ranking) => {
    onSelect(ranking.resume_id, ranking.resume_version_id ?? null);
  };

  const isRecommended = (ranking) =>
    (recommended_resume_id && ranking.resume_id === recommended_resume_id) ||
    (recommended_version_id && ranking.resume_version_id === recommended_version_id);

  return (
    <div className="recommendation-container">
      {/* Header */}
      <div className="recommendation-header">
        <div className="header-top">
          <h2>Resume Recommendation</h2>
          <span className="mode-badge compare-mode">Compare Mode — Ranked by ATS Score</span>
        </div>
        <p className="header-subtitle">
          {rankings.length === 1
            ? 'Your resume has been scored against the job description.'
            : `${rankings.length} resumes scored and ranked by ATS compatibility.`}
        </p>
      </div>

      {/* LLM Rationale */}
      {rationale && (
        <div className="rationale-block">
          <div className="rationale-label">AI Recommendation</div>
          <p className="rationale-text">{rationale}</p>
        </div>
      )}

      {/* Resume Cards */}
      <div className="rankings-list">
        {rankings.map((ranking, idx) => {
          const recommended = isRecommended(ranking);
          return (
            <div
              key={ranking.resume_id ?? ranking.resume_version_id ?? idx}
              className={`ranking-card ${recommended ? 'ranking-card--recommended' : ''}`}
            >
              {/* Card Header */}
              <div className="card-header">
                <div className="rank-badge">#{ranking.rank}</div>
                <div className="card-title-group">
                  <span className="filename">{ranking.filename}</span>
                  <span className="source-badge">{ranking.source}</span>
                </div>
                {recommended && (
                  <span className="recommended-badge">⭐ Recommended</span>
                )}
              </div>

              {/* Score */}
              <div className="score-section">
                <div className="score-main">
                  <span className="score-value">{ranking.score}</span>
                  <span className="score-max">/100</span>
                  <div className="score-bar">
                    <div
                      className="score-fill"
                      style={{ width: `${ranking.score}%` }}
                    />
                  </div>
                </div>

                {/* Breakdown */}
                {ranking.score_breakdown && (
                  <div className="score-breakdown">
                    {Object.entries(ranking.score_breakdown).map(([key, val]) => (
                      <div key={key} className="breakdown-item">
                        <span className="breakdown-label">
                          {key.replace(/_/g, ' ')}
                        </span>
                        <span className="breakdown-value">{Math.round(val)}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Keywords */}
              <div className="keywords-section">
                {ranking.matching_keywords?.length > 0 && (
                  <div className="keyword-group">
                    <span className="keyword-group-label">Matches:</span>
                    <div className="keyword-chips">
                      {ranking.matching_keywords.slice(0, 6).map((kw) => (
                        <span key={kw} className="keyword-chip keyword-chip--match">{kw}</span>
                      ))}
                      {ranking.matching_keywords.length > 6 && (
                        <span className="keyword-chip keyword-chip--more">
                          +{ranking.matching_keywords.length - 6} more
                        </span>
                      )}
                    </div>
                  </div>
                )}
                {ranking.missing_keywords?.length > 0 && (
                  <div className="keyword-group">
                    <span className="keyword-group-label">Missing:</span>
                    <div className="keyword-chips">
                      {ranking.missing_keywords.slice(0, 4).map((kw) => (
                        <span key={kw} className="keyword-chip keyword-chip--missing">{kw}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Action */}
              <div className="card-actions">
                <button
                  className={`btn-select-resume ${recommended ? 'btn-select-resume--primary' : 'btn-select-resume--secondary'}`}
                  onClick={() => handleSelect(ranking)}
                >
                  {recommended ? '✓ Use This Resume' : 'Select This Resume'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="recommendation-footer">
        <button className="btn-recompare" onClick={onRecompare}>
          ← Back / Re-compare
        </button>
        <p className="footer-note">
          Accept the recommendation or override by selecting any resume above.
          The chosen resume will be optimized for this job description.
        </p>
      </div>
    </div>
  );
}

export default ResumeRecommendation;
