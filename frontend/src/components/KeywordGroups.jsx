import React, { useState, useEffect, useCallback, useRef } from 'react';
import api from '../services/api';
import KeywordEquivalencyPanel from './KeywordEquivalencyPanel';
import RewriteHistoryDialog from './RewriteHistoryDialog';

/**
 * KeywordGroups — replaces flat keyword chip list with semantic grouping.
 *
 * Props:
 *   matchingKeywords  string[]  — keywords found in both resume and job
 *   missingKeywords   string[]  — keywords in job but not in resume
 *   jobDescription    string    — job description text
 *   resumeText        string    — current optimized resume text
 *   onResumeUpdated   fn(text)  — called when resume text is updated via rewrite
 */
const MATCHING_INITIAL_LIMIT = 30;

function KeywordGroups({
  matchingKeywords = [],
  missingKeywords = [],
  jobDescription = '',
  resumeText = '',
  originalText = '',
  onResumeUpdated,
  onApplied,
}) {
  const [groups, setGroups] = useState(null);
  const [autoResolved, setAutoResolved] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [editingGroup, setEditingGroup] = useState(null);
  const [editName, setEditName] = useState('');
  const [showEquivalency, setShowEquivalency] = useState(false);
  const [moveKeyword, setMoveKeyword] = useState(null); // {keyword, fromGroup}
  // Dispute state: {keyword, status: 'evaluating'|'covered'|'not_covered'|'needs_interview', rationale, equivalent}
  const [disputeState, setDisputeState] = useState({});
  const [showRewriteHistory, setShowRewriteHistory] = useState(false);
  // Matching keyword display cap (null = show all)
  const [matchingLimit, setMatchingLimit] = useState(MATCHING_INITIAL_LIMIT);
  // Persist-ignore feedback: set of keywords currently being saved (for spinner)
  const [ignoringSaving, setIgnoringSaving] = useState(new Set());
  // Track the keyword list that was last used to fetch groups so we can detect changes
  const lastFetchedKeyRef = useRef(null);

  const fetchGroups = useCallback(async () => {
    if (!missingKeywords.length) return;
    const fetchKey = missingKeywords.slice().sort().join('|');
    lastFetchedKeyRef.current = fetchKey;
    setLoading(true);
    setError('');
    try {
      const result = await api.groupKeywords(missingKeywords, jobDescription);
      setGroups(result.groups || []);
      setAutoResolved(result.auto_resolved || []);
    } catch {
      setError('Failed to group keywords. Showing flat list.');
      setGroups([{ name: 'Missing Keywords', keywords: missingKeywords, description: '' }]);
    } finally {
      setLoading(false);
    }
  }, [missingKeywords, jobDescription]);

  // Fetch groups on first load, or when missingKeywords changes substantially
  // (e.g., after user rescores and liveMissingKeywords replaces addedKeywords).
  useEffect(() => {
    if (!missingKeywords.length) return;
    const fetchKey = missingKeywords.slice().sort().join('|');
    // Re-fetch if: no groups yet, OR the keyword list changed from what we last fetched
    if (!groups || (lastFetchedKeyRef.current && lastFetchedKeyRef.current !== fetchKey)) {
      setGroups(null); // clear stale groups before re-fetch
      fetchGroups();
    }
  }, [missingKeywords, groups, fetchGroups]);

  const handleRenameStart = (idx) => {
    setEditingGroup(idx);
    setEditName(groups[idx].name);
  };

  const handleRenameConfirm = () => {
    if (editingGroup === null || !editName.trim()) return;
    const updated = [...groups];
    updated[editingGroup] = { ...updated[editingGroup], name: editName.trim() };
    setGroups(updated);
    setEditingGroup(null);
    setEditName('');
  };

  const handleMoveKeyword = (keyword, fromGroupIdx, toGroupIdx) => {
    const updated = groups.map((g, i) => {
      if (i === fromGroupIdx) {
        return { ...g, keywords: g.keywords.filter(k => k !== keyword) };
      }
      if (i === toGroupIdx) {
        return { ...g, keywords: [...g.keywords, keyword] };
      }
      return g;
    }).filter(g => g.keywords.length > 0);
    setGroups(updated);
    setMoveKeyword(null);
  };

  // Dismiss an entire group from the UI only (ephemeral)
  const handleDismissGroup = (gIdx) => {
    setGroups(prev => prev.filter((_, i) => i !== gIdx));
  };

  // Ignore an entire group — removes from UI AND persists to DB so it's excluded from scoring
  const handleIgnoreGroup = async (gIdx) => {
    const group = groups[gIdx];
    const keywords = group.keywords || [];
    // Remove from UI immediately
    setGroups(prev => prev.filter((_, i) => i !== gIdx));
    // Persist to DB (best-effort, don't block UI)
    if (keywords.length > 0) {
      try {
        await api.ignoreKeywords(keywords);
      } catch {
        // ignore save failure — UI already dismissed
      }
    }
  };

  // Ignore an individual keyword — removes from its group AND persists to DB
  const handleIgnoreKeyword = async (keyword, gIdx) => {
    const saving = new Set(ignoringSaving);
    saving.add(keyword);
    setIgnoringSaving(saving);

    // Remove from UI
    setGroups(prev => prev.map((g, i) => {
      if (i !== gIdx) return g;
      return { ...g, keywords: g.keywords.filter(k => k !== keyword) };
    }).filter(g => g.keywords.length > 0));

    // Persist
    try {
      await api.ignoreKeywords([keyword]);
    } catch {
      // best-effort
    } finally {
      setIgnoringSaving(prev => {
        const next = new Set(prev);
        next.delete(keyword);
        return next;
      });
    }
  };

  // User disputes a keyword as already covered — asks AI to evaluate
  const handleDisputeKeyword = async (keyword) => {
    setDisputeState(prev => ({ ...prev, [keyword]: { status: 'evaluating' } }));
    try {
      const result = await api.disputeKeyword(keyword, resumeText, jobDescription);
      if (result.covered && !result.needs_interview) {
        // AI agrees it's covered — remove from all groups
        setGroups(prev => prev.map(g => ({
          ...g,
          keywords: g.keywords.filter(k => k !== keyword),
        })).filter(g => g.keywords.length > 0));
        if (result.suggested_equivalent) {
          setAutoResolved(prev => [...prev, {
            keyword,
            equivalent: result.suggested_equivalent,
            confidence: result.confidence,
          }]);
        }
      }
      setDisputeState(prev => ({
        ...prev,
        [keyword]: {
          status: result.covered ? 'covered' : result.needs_interview ? 'needs_interview' : 'not_covered',
          rationale: result.rationale,
          equivalent: result.suggested_equivalent,
          confidence: result.confidence,
        },
      }));
    } catch {
      setDisputeState(prev => ({ ...prev, [keyword]: { status: 'error' } }));
    }
  };

  // Count total still-missing keywords (exclude employer groups from count)
  const totalMissing = groups
    ? groups.filter(g => !g.employer_group).reduce((sum, g) => sum + g.keywords.length, 0)
    : missingKeywords.length;

  const visibleMatching = matchingLimit ? matchingKeywords.slice(0, matchingLimit) : matchingKeywords;

  return (
    <div className="kw-groups-container">

      {/* Matching keywords */}
      {matchingKeywords.length > 0 && (
        <div className="keyword-group">
          <h4 className="kw-group-title kw-group-match">
            Matching Keywords ({matchingKeywords.length})
          </h4>
          <div className="keyword-chips">
            {visibleMatching.map((kw, i) => (
              <span key={i} className="chip chip-success">{kw}</span>
            ))}
          </div>
          {matchingKeywords.length > MATCHING_INITIAL_LIMIT && (
            <button
              className="btn-xs kw-show-more-btn"
              onClick={() => setMatchingLimit(matchingLimit ? null : MATCHING_INITIAL_LIMIT)}
            >
              {matchingLimit
                ? `Show all ${matchingKeywords.length} matching keywords`
                : 'Show fewer'}
            </button>
          )}
        </div>
      )}

      {/* Auto-resolved from persisted equivalencies */}
      {autoResolved.length > 0 && (
        <div className="kw-auto-resolved">
          <h4 className="kw-group-title kw-group-auto">
            Auto-Resolved ({autoResolved.length})
            <span className="kw-auto-hint">from your past equivalency mappings</span>
          </h4>
          <div className="keyword-chips">
            {autoResolved.map((r, i) => (
              <span key={i} className="chip chip-auto-resolved" title={`Your equivalent: ${r.equivalent}`}>
                {r.keyword} ≈ {r.equivalent}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Grouped missing keywords */}
      <div className="kw-missing-section">
        <div className="kw-missing-header">
          <h4 className="kw-group-title kw-group-missing">
            Missing Keywords ({totalMissing})
          </h4>
          <button
            className="btn-xs kw-history-btn"
            onClick={() => setShowRewriteHistory(true)}
            title="Browse past rewrite suggestions"
          >
            Rewrite History
          </button>
        </div>

        {loading && (
          <div className="kw-loading">
            <div className="spinner" style={{ width: 18, height: 18 }} />
            <span>Analyzing keyword categories…</span>
          </div>
        )}

        {error && <p className="kw-error">{error}</p>}

        {groups && groups.map((group, gIdx) => (
          <div
            key={gIdx}
            className={`kw-group-card ${group.employer_group ? 'kw-group-card--employer' : ''}`}
          >
            <div className="kw-card-header">
              {editingGroup === gIdx ? (
                <div className="kw-rename-row">
                  <input
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleRenameConfirm()}
                    autoFocus
                    className="kw-rename-input"
                  />
                  <button className="kw-rename-ok" onClick={handleRenameConfirm}>✓</button>
                  <button className="kw-rename-cancel" onClick={() => setEditingGroup(null)}>✕</button>
                </div>
              ) : (
                <span
                  className="kw-card-name"
                  onClick={() => !group.employer_group && handleRenameStart(gIdx)}
                  title={group.employer_group ? '' : 'Click to rename this group'}
                >
                  {group.name}
                  <span className="kw-card-count">({group.keywords.length})</span>
                  {group.employer_group && (
                    <span className="kw-employer-badge" title="These describe employer perks/culture, not your skills">
                      employer description
                    </span>
                  )}
                </span>
              )}
              <div className="kw-card-actions">
                {!group.employer_group && (
                  <button
                    className="btn-xs kw-dismiss-group-btn"
                    onClick={() => handleDismissGroup(gIdx)}
                    title="Hide this group for this session only"
                  >
                    Dismiss
                  </button>
                )}
                <button
                  className="btn-xs kw-ignore-group-btn"
                  onClick={() => handleIgnoreGroup(gIdx)}
                  title={group.employer_group
                    ? 'Remove permanently — these are employer descriptions, not skill gaps'
                    : 'Ignore permanently — exclude from keyword matching and scoring'}
                >
                  {group.employer_group ? 'Not my responsibility' : 'Ignore permanently'}
                </button>
              </div>
            </div>
            {group.employer_group && (
              <p className="kw-employer-note">
                These items describe what the employer offers, not skills you need.
                Ignore them to keep your missing keywords list focused.
              </p>
            )}
            {!group.employer_group && group.description && (
              <p className="kw-card-desc">{group.description}</p>
            )}
            <div className="keyword-chips">
              {group.keywords.map((kw, kIdx) => {
                const ds = disputeState[kw];
                return (
                  <span
                    key={kIdx}
                    className={`chip chip-added kw-chip-disputeable
                      ${moveKeyword?.keyword === kw ? 'chip-moving' : ''}
                      ${ds?.status === 'covered' ? 'chip-dispute-covered' : ''}
                      ${ds?.status === 'evaluating' ? 'chip-dispute-evaluating' : ''}
                    `}
                    onClick={() => {
                      if (!ds && groups.length > 1) {
                        setMoveKeyword(moveKeyword?.keyword === kw ? null : { keyword: kw, fromGroup: gIdx });
                      }
                    }}
                    title={ds?.rationale || (groups.length > 1 ? 'Click to move group | Use "?" to dispute coverage' : '')}
                  >
                    {kw}
                    {!group.employer_group && !ds && (
                      <>
                        <button
                          className="kw-dispute-btn"
                          onClick={e => { e.stopPropagation(); handleDisputeKeyword(kw); }}
                          title="Ask AI: is this already covered by your experience?"
                        >
                          ?
                        </button>
                        <button
                          className="kw-ignore-kw-btn"
                          onClick={e => { e.stopPropagation(); handleIgnoreKeyword(kw, gIdx); }}
                          title="Ignore permanently — not applicable to this role"
                        >
                          ✕
                        </button>
                      </>
                    )}
                    {group.employer_group && (
                      <button
                        className="kw-ignore-kw-btn"
                        onClick={e => { e.stopPropagation(); handleIgnoreKeyword(kw, gIdx); }}
                        title="Ignore permanently"
                      >
                        ✕
                      </button>
                    )}
                    {ds?.status === 'evaluating' && <span className="kw-dispute-spinner" />}
                    {ds?.status === 'needs_interview' && (
                      <span className="kw-dispute-flag" title={ds.rationale}>⚠</span>
                    )}
                    {ds?.status === 'covered' && <span className="kw-dispute-ok" title={ds.rationale}>✓</span>}
                  </span>
                );
              })}
            </div>
            {/* Move target buttons */}
            {moveKeyword && moveKeyword.fromGroup === gIdx && (
              <div className="kw-move-targets">
                <span className="kw-move-label">Move to:</span>
                {groups.map((targetG, tIdx) => (
                  tIdx !== gIdx && (
                    <button
                      key={tIdx}
                      className="kw-move-target-btn"
                      onClick={() => handleMoveKeyword(moveKeyword.keyword, gIdx, tIdx)}
                    >
                      {targetG.name}
                    </button>
                  )
                ))}
                <button className="kw-move-cancel" onClick={() => setMoveKeyword(null)}>Cancel</button>
              </div>
            )}
            {/* Dispute result feedback */}
            {group.keywords.some(kw => disputeState[kw]?.status === 'needs_interview') && (
              <div className="kw-dispute-interview-cta">
                <span>⚠ Some keywords need more context.</span>
                <button
                  className="btn-xs"
                  onClick={() => setShowEquivalency(true)}
                  style={{ marginLeft: 8 }}
                >
                  Open Interview
                </button>
              </div>
            )}
          </div>
        ))}

        {/* Resolve missing keywords CTA */}
        {groups && totalMissing > 0 && !showEquivalency && (
          <div className="kw-resolve-cta">
            <p>
              Have experience with these keywords using different terminology?
              Walk through a quick interview to map your real experience to these
              job requirements — then we'll rewrite your resume to bridge the gap.
            </p>
            <button className="btn-primary kw-resolve-btn" onClick={() => setShowEquivalency(true)}>
              Resolve Missing Keywords
            </button>
          </div>
        )}

        {/* All keywords resolved — offer rewrite generation */}
        {totalMissing === 0 && autoResolved.length > 0 && !showEquivalency && (
          <div className="kw-resolve-cta kw-all-resolved-cta">
            <p>
              All keywords mapped via your equivalency mappings.
              Generate resume rewrites to weave job description terminology
              into your resume for maximum ATS score.
            </p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn-primary kw-resolve-btn" onClick={() => setShowEquivalency(true)}>
                Generate Rewrites
              </button>
              <button
                className="btn-xs kw-history-btn"
                onClick={() => setShowRewriteHistory(true)}
              >
                View Past Rewrites
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Equivalency interview panel */}
      {showEquivalency && groups && (
        <KeywordEquivalencyPanel
          keywordGroups={groups.filter(g => !g.employer_group)}
          resumeText={resumeText}
          originalText={originalText}
          jobDescription={jobDescription}
          onClose={() => setShowEquivalency(false)}
          onResumeUpdated={onResumeUpdated}
          onGroupsUpdated={(newGroups) => setGroups(newGroups)}
          onApplied={onApplied}
        />
      )}

      {/* Rewrite history browser */}
      {showRewriteHistory && (
        <RewriteHistoryDialog
          resumeText={resumeText}
          onClose={() => setShowRewriteHistory(false)}
          onResumeUpdated={onResumeUpdated}
          onApplied={onApplied}
        />
      )}
    </div>
  );
}

export default KeywordGroups;
