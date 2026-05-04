import React, { useState, useRef, useEffect } from 'react';
import api from '../services/api';
import { saveChatHistoryFromMessages } from '../utils/chatHistory';
import KeywordMatchReview from './KeywordMatchReview';
import KeywordRewriteReview from './KeywordRewriteReview';

/**
 * KeywordEquivalencyPanel — equivalency match review + targeted interview + rewrite flow.
 *
 * Stages:
 *   loading_matches  — fetching + LLM-matching saved equivalencies on mount
 *   confirm_matches  — user confirms/rejects exact + semantic matches, selects unmatched for interview
 *   interview        — open-ended chat (full groups OR targeted to selected keywords)
 *   generating       — rewrite generation spinner
 *   review           — accept/reject rewrite cards
 *
 * Props:
 *   keywordGroups    [{name, keywords}]
 *   resumeText       string
 *   jobDescription   string
 *   onClose          fn()
 *   onResumeUpdated  fn(newText)
 *   onGroupsUpdated  fn(newGroups)
 *   onApplied        fn(newText)  — triggers gap score re-analysis
 */
function KeywordEquivalencyPanel({
  keywordGroups,
  resumeText,
  originalText,
  jobDescription,
  onClose,
  onResumeUpdated,
  onGroupsUpdated,
  onApplied,
}) {
  // ── Stage & match state ───────────────────────────────────────────────────
  const [stage, setStage] = useState('loading_matches');
  const [exactMatches, setExactMatches] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [unmatchedKws, setUnmatchedKws] = useState([]);
  // Sets for user selections in confirm_matches stage
  const [confirmedExact, setConfirmedExact] = useState(new Set());
  const [confirmedSugg, setConfirmedSugg] = useState(new Set());
  const [selectedForInterview, setSelectedForInterview] = useState(new Set());
  const [notApplicable, setNotApplicable] = useState(new Set());

  // ── Interview state ───────────────────────────────────────────────────────
  const [interviewGroups, setInterviewGroups] = useState(keywordGroups); // may be filtered
  const [chatMessages, setChatMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [currentAnswer, setCurrentAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [slowWarning, setSlowWarning] = useState(false);
  const slowTimerRef = useRef(null);
  const [suggestedDone, setSuggestedDone] = useState(false);
  const [allResolved, setAllResolved] = useState([]);

  // ── Rewrite review state ──────────────────────────────────────────────────
  const [rewrites, setRewrites] = useState([]);
  const [rewriteAccepted, setRewriteAccepted] = useState({});
  const [applying, setApplying] = useState(false);
  const [persisting, setPersisting] = useState(false);
  const [persisted, setPersisted] = useState(false);
  const [generatingRewrites, setGeneratingRewrites] = useState(false);
  // Apply confirmation dialog
  const [applyResult, setApplyResult] = useState(null); // {sections: [str], count: int}

  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // ── Load matches on mount ─────────────────────────────────────────────────
  useEffect(() => {
    const allKws = keywordGroups.flatMap(g => g.keywords);
    api.matchEquivalencies(allKws, jobDescription)
      .then(data => {
        const exact = data.exact_matches || [];
        const sugg = data.suggestions || [];
        const unmatched = data.unmatched || [];
        setExactMatches(exact);
        setSuggestions(sugg);
        setUnmatchedKws(unmatched);
        // Pre-confirm all exact matches; pre-confirm suggestions with confidence ≥ 0.7
        setConfirmedExact(new Set(exact.map((_, i) => i)));
        setConfirmedSugg(new Set(
          sugg.map((s, i) => (s.confidence >= 0.7 ? i : null)).filter(i => i !== null)
        ));
        // If nothing at all matched, skip straight to interview
        if (exact.length === 0 && sugg.length === 0 && unmatched.length === 0) {
          _startInterview(keywordGroups);
        } else {
          setStage('confirm_matches');
        }
      })
      .catch(() => {
        // Fall back to full interview if matching endpoint fails
        _startInterview(keywordGroups);
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Interview initialiser (called for full or targeted sets) ─────────────
  const _startInterview = (groups) => {
    setInterviewGroups(groups);
    const allKws = groups.flatMap(g => g.keywords);
    // Build a question that names the specific keywords, not just the group label
    let firstQ;
    if (allKws.length === 1) {
      firstQ = `Let's talk about "${allKws[0]}". Tell me how you've worked with this — what tools, approaches, or projects involved it?`;
    } else if (allKws.length <= 4) {
      const kwList = allKws.map(k => `"${k}"`).join(', ');
      firstQ = `Let's talk about these specific areas: ${kwList}.\n\nStart with whichever feels most relevant — what tools or approaches have you used, and where did you apply them?`;
    } else {
      const firstGroupKws = groups[0]?.keywords || [];
      const kwSample = firstGroupKws.slice(0, 3).map(k => `"${k}"`).join(', ');
      firstQ = `I'll ask about ${allKws.length} missing keywords grouped by theme.\n\nStarting with ${groups[0]?.name || 'the first group'} — specifically ${kwSample}${firstGroupKws.length > 3 ? ' and more' : ''}. Tell me how you've worked with these — what tools and approaches have you used?`;
    }
    setCurrentQuestion(firstQ);
    setChatMessages([
      { role: 'assistant', content: `Let's map your real experience to ${allKws.length === 1 ? 'this missing keyword' : `these ${allKws.length} missing keywords`}. Tell me what you've used and I'll identify where your experience is equivalent. Finish whenever you're ready.` },
      { role: 'assistant', content: firstQ },
    ]);
    setStage('interview');
  };

  // ── confirm_matches handlers ──────────────────────────────────────────────
  const toggleExact = (i) => setConfirmedExact(prev => {
    const s = new Set(prev); s.has(i) ? s.delete(i) : s.add(i); return s;
  });
  const toggleSugg = (i) => setConfirmedSugg(prev => {
    const s = new Set(prev); s.has(i) ? s.delete(i) : s.add(i); return s;
  });
  const toggleInterview = (kw) => setSelectedForInterview(prev => {
    const s = new Set(prev); s.has(kw) ? s.delete(kw) : s.add(kw); return s;
  });
  const markNA = (kw) => {
    setNotApplicable(prev => {
      const s = new Set(prev);
      if (s.has(kw)) { s.delete(kw); return s; }
      s.add(kw);
      setSelectedForInterview(sel => { const t = new Set(sel); t.delete(kw); return t; });
      return s;
    });
  };

  // Build resolved list from confirmed matches for rewrite generation
  const _buildResolvedFromMatches = () => {
    const resolved = [];
    exactMatches.forEach((m, i) => {
      if (confirmedExact.has(i)) resolved.push({ keyword: m.keyword, equivalent: m.equivalent_phrase, confidence: m.confidence, status: m.status || 'equivalent' });
    });
    suggestions.forEach((s, i) => {
      if (confirmedSugg.has(i)) resolved.push({ keyword: s.keyword, equivalent: s.equivalent_phrase, confidence: s.confidence, status: s.status || 'equivalent' });
    });
    return resolved;
  };

  const _saveNAKeywords = async () => {
    if (notApplicable.size === 0) return;
    const naEntries = [...notApplicable].map(kw => ({ keyword: kw, equivalent: 'not_applicable', confidence: 1.0, status: 'not_applicable' }));
    try { await api.saveEquivalencies(naEntries); } catch { /* silent */ }
  };

  const handleGenerateFromMatches = async () => {
    const resolved = _buildResolvedFromMatches();
    if (resolved.length === 0) return;
    await _saveNAKeywords();
    setAllResolved(resolved);
    setPersisted(true);
    setGeneratingRewrites(true);
    try {
      const result = await api.generateEquivalencyRewrites(resolved, resumeText, jobDescription, originalText);
      setRewrites(result.rewrites || []);
      const defaults = {};
      (result.rewrites || []).forEach((_, i) => { defaults[i] = true; });
      setRewriteAccepted(defaults);
      setStage('review');
    } catch { setStage('confirm_matches'); }
    setGeneratingRewrites(false);
  };

  const handleInterviewSelected = async () => {
    await _saveNAKeywords();
    // Pre-populate allResolved with confirmed matches; interview adds more
    setAllResolved(_buildResolvedFromMatches());
    // Build targeted groups from selected keywords
    if (selectedForInterview.size === 0) {
      // Nothing selected — interview about all unmatched keywords
      _startInterview(keywordGroups);
      return;
    }
    const selectedKws = new Set([...selectedForInterview].map(k => k.toLowerCase()));
    const targetedGroups = keywordGroups
      .map(g => ({ ...g, keywords: g.keywords.filter(kw => selectedKws.has(kw.toLowerCase())) }))
      .filter(g => g.keywords.length > 0);
    // If filter matched nothing (unexpected), create a flat group from selected keywords
    if (targetedGroups.length === 0) {
      const flatGroup = { name: 'Selected Keywords', keywords: [...selectedForInterview], description: '' };
      _startInterview([flatGroup]);
    } else {
      _startInterview(targetedGroups);
    }
  };

  // ── Interview turn handler ────────────────────────────────────────────────
  const handleSend = async (userFinished = false) => {
    const answer = currentAnswer.trim();
    if ((!answer && !userFinished) || loading) return;
    if (answer) setChatMessages(prev => [...prev, { role: 'user', content: answer }]);
    setCurrentAnswer('');
    setLoading(true);
    setSlowWarning(false);
    slowTimerRef.current = setTimeout(() => setSlowWarning(true), 15000);
    const updatedHistory = answer ? [...history, { question: currentQuestion, answer, resolved: [] }] : history;

    try {
      const result = await api.sendEquivalencyInterview({ history: updatedHistory, currentQuestion, userAnswer: answer || '(finishing)', keywordGroups: interviewGroups, resumeText, jobDescription, userFinished });
      const newResolved = result.resolved || [];
      const combinedResolved = [...allResolved, ...newResolved];
      setAllResolved(combinedResolved);
      if (updatedHistory.length > 0) updatedHistory[updatedHistory.length - 1].resolved = newResolved;
      setHistory(updatedHistory);
      setSuggestedDone(result.suggested_done || false);
      if (result.insight) setChatMessages(prev => [...prev, { role: 'assistant', content: result.insight }]);
      if (newResolved.length > 0) {
        const resolvedMsg = newResolved.map(r => {
          if (r.status === 'equivalent') return `✓ ${r.keyword} → ${r.equivalent}`;
          if (r.status === 'partial') return `~ ${r.keyword} → ${r.equivalent} (partial)`;
          return `✗ ${r.keyword} — confirmed missing`;
        }).join('\n');
        setChatMessages(prev => [...prev, { role: 'assistant', content: `Keywords resolved:\n${resolvedMsg}` }]);
      }
      if (userFinished || result.is_complete) {
        const equivalents = combinedResolved.filter(r => r.status === 'equivalent' || r.status === 'partial');
        if (equivalents.length > 0) {
          try { await api.saveEquivalencies(combinedResolved); setPersisted(true); } catch { /* silent */ }
          setStage('generating');
          try {
            const rr = await api.generateEquivalencyRewrites(combinedResolved, resumeText, jobDescription, originalText);
            setRewrites(rr.rewrites || []);
            const defaults = {};
            (rr.rewrites || []).forEach((_, i) => { defaults[i] = true; });
            setRewriteAccepted(defaults);
            setStage('review');
          } catch {
            setChatMessages(prev => [...prev, { role: 'assistant', content: 'Failed to generate rewrites. Your equivalencies are still saved.' }]);
            setStage('interview');
          }
        } else {
          setChatMessages(prev => [...prev, { role: 'assistant', content: 'No equivalent experience was found to rewrite. The keywords marked as missing remain gaps to address.' }]);
        }
      } else if (result.next_question) {
        setCurrentQuestion(result.next_question);
        setChatMessages(prev => [...prev, { role: 'assistant', content: result.next_question }]);
      }
    } catch {
      setChatMessages(prev => [...prev, { role: 'assistant', content: 'Something went wrong. Please try again.' }]);
    } finally {
      clearTimeout(slowTimerRef.current);
      setSlowWarning(false);
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(false); } };

  // ── Apply rewrites ────────────────────────────────────────────────────────
  const _findSectionBoundary = (text, startIdx) => {
    const rest = text.slice(startIdx + 40);
    const boundary = rest.match(/\n{2,}(?=[A-Z][A-Z\s&/]+\n)/);
    return boundary ? startIdx + 40 + boundary.index : text.length;
  };

  const handleApplyRewrites = async () => {
    setApplying(true);
    let updatedText = resumeText;
    const appliedSections = [];
    const failedSections = [];
    for (const [idx, rw] of rewrites.entries()) {
      if (!rewriteAccepted[idx] || !rw.original_text || !rw.proposed_text) continue;
      // Tier 1: exact match
      if (updatedText.includes(rw.original_text)) {
        updatedText = updatedText.replaceAll(rw.original_text, rw.proposed_text);
        appliedSections.push(rw.section || `Section ${idx + 1}`);
        continue;
      }
      // Tier 2: anchor match (first 120 chars)
      const anchor = rw.original_text.slice(0, 120);
      const anchorIdx = updatedText.indexOf(anchor);
      if (anchorIdx !== -1) {
        const endIdx = _findSectionBoundary(updatedText, anchorIdx);
        updatedText = updatedText.slice(0, anchorIdx) + rw.proposed_text + updatedText.slice(endIdx);
        appliedSections.push(rw.section || `Section ${idx + 1}`);
        continue;
      }
      // Tier 3: section-name match — find a line containing the section name
      const sectionName = (rw.section || '').trim();
      if (sectionName) {
        // Extract key words from section name (e.g. "PRICEWATERHOUSECOOPERS" from "PWC Experience")
        const escaped = sectionName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        // Try exact section name in a line, or first significant word (>4 chars)
        const nameWords = sectionName.split(/[\s,()-]+/).filter(w => w.length > 3);
        const patterns = [
          new RegExp(`(^|\\n)([^\\n]*${escaped}[^\\n]*)\\n`, 'i'),
          ...nameWords.map(w => new RegExp(`(^|\\n)([^\\n]*${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[^\\n]*)\\n`, 'i')),
        ];
        let matched = false;
        for (const re of patterns) {
          const m = updatedText.match(re);
          if (m) {
            const sectionStart = updatedText.indexOf(m[0]) + (m[1] || '').length;
            const endIdx = _findSectionBoundary(updatedText, sectionStart);
            updatedText = updatedText.slice(0, sectionStart) + rw.proposed_text + updatedText.slice(endIdx);
            appliedSections.push(sectionName);
            matched = true;
            break;
          }
        }
        if (matched) continue;
        // Tier 4: shorter anchor (60 chars) as last resort
        const shortAnchor = rw.original_text.slice(0, 60);
        const shortIdx = updatedText.indexOf(shortAnchor);
        if (shortIdx !== -1) {
          const endIdx = _findSectionBoundary(updatedText, shortIdx);
          updatedText = updatedText.slice(0, shortIdx) + rw.proposed_text + updatedText.slice(endIdx);
          appliedSections.push(sectionName);
          continue;
        }
      }
      failedSections.push(rw.section || `Section ${idx + 1}`);
    }
    if (onResumeUpdated) onResumeUpdated(updatedText);
    if (onApplied) onApplied(updatedText);
    setApplying(false);
    if (appliedSections.length > 0 || failedSections.length > 0) {
      setApplyResult({
        sections: appliedSections,
        count: appliedSections.length,
        failed: failedSections.length > 0 ? failedSections : undefined,
      });
    }
  };

  const handlePersist = async () => {
    setPersisting(true);
    try { await api.saveEquivalencies(allResolved); setPersisted(true); } catch { /* silent */ }
    finally { setPersisting(false); }
  };

  // ── Stage renders ─────────────────────────────────────────────────────────

  if (stage === 'loading_matches') {
    return (
      <div className="keq-panel">
        <div className="keq-generating">
          <div className="spinner" />
          <p>Matching your saved experience to this job's keywords…</p>
        </div>
      </div>
    );
  }

  if (stage === 'confirm_matches') {
    return (
      <KeywordMatchReview
        exactMatches={exactMatches}
        suggestions={suggestions}
        unmatched={unmatchedKws}
        confirmedExact={confirmedExact}
        confirmedSugg={confirmedSugg}
        selectedForInterview={selectedForInterview}
        notApplicable={notApplicable}
        onToggleExact={toggleExact}
        onToggleSugg={toggleSugg}
        onToggleInterview={toggleInterview}
        onMarkNA={markNA}
        onGenerate={handleGenerateFromMatches}
        onInterview={handleInterviewSelected}
        onClose={onClose}
        generating={generatingRewrites}
      />
    );
  }

  if (stage === 'generating') {
    return (
      <div className="keq-panel">
        <div className="keq-generating">
          <div className="spinner" />
          <p>Generating resume section rewrites based on your equivalencies…</p>
        </div>
      </div>
    );
  }

  if (stage === 'review') {
    return (
      <>
        {applyResult && (
          <div className="keq-apply-overlay" onClick={() => setApplyResult(null)}>
            <div className="keq-apply-dialog" onClick={e => e.stopPropagation()}>
              <div className="keq-apply-dialog-icon">✓</div>
              <h4 className="keq-apply-dialog-title">
                {applyResult.count} section{applyResult.count > 1 ? 's' : ''} updated
              </h4>
              <ul className="keq-apply-dialog-sections">
                {applyResult.sections.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
              {applyResult.failed && applyResult.failed.length > 0 && (
                <div className="keq-apply-dialog-failed">
                  <strong>Could not apply ({applyResult.failed.length}):</strong>
                  <ul>
                    {applyResult.failed.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                  <small>These sections may have been edited since the rewrite was generated. Try regenerating rewrites.</small>
                </div>
              )}
              <p className="keq-apply-dialog-note">
                Score is being recalculated — check the Relevance Score chip above.
              </p>
              <button className="btn-primary keq-apply-dialog-ok" onClick={() => setApplyResult(null)}>
                OK
              </button>
            </div>
          </div>
        )}
        <KeywordRewriteReview
          rewrites={rewrites}
          rewriteAccepted={rewriteAccepted}
          setRewriteAccepted={setRewriteAccepted}
          onEditProposed={(idx, newText) =>
            setRewrites(prev => prev.map((rw, i) => i === idx ? { ...rw, proposed_text: newText } : rw))
          }
          persisted={persisted}
          persisting={persisting}
          applying={applying}
          allResolved={allResolved}
          onApply={handleApplyRewrites}
          onPersist={handlePersist}
          onBack={() => setStage('interview')}
          onClose={onClose}
        />
      </>
    );
  }

  // ── Stage: interview ──────────────────────────────────────────────────────
  return (
    <div className="keq-panel">
      <div className="keq-header">
        <h4 className="keq-title">Keyword Equivalency Interview</h4>
        <div className="keq-header-actions">
          <button className="btn-save-history" onClick={() => saveChatHistoryFromMessages(chatMessages, 'Keyword Equivalency Interview')}>
            Save History
          </button>
          <button className="btn-secondary keq-close-btn" onClick={onClose}>✕</button>
        </div>
      </div>

      {allResolved.length > 0 && (
        <div className="keq-resolved-bar">
          <span className="keq-resolved-count">
            {allResolved.filter(r => r.status === 'equivalent').length} equivalent,{' '}
            {allResolved.filter(r => r.status === 'partial').length} partial,{' '}
            {allResolved.filter(r => r.status === 'confirmed_missing').length} confirmed missing
          </span>
        </div>
      )}

      {suggestedDone && (
        <div className="keq-suggested-done">
          I've identified enough equivalencies to generate meaningful rewrites. You can keep going or finish now.
        </div>
      )}

      <div className="keq-chat">
        {chatMessages.map((m, i) => (
          <div key={i} className={`ec-msg ec-msg--${m.role}`}>
            <p style={{ whiteSpace: 'pre-wrap' }}>{m.content}</p>
          </div>
        ))}
        {loading && (
          <div className="ec-msg ec-msg--assistant">
            <p className="ec-typing">
              {slowWarning
                ? 'Taking longer than expected — RTX 5090 is processing your answer. Please wait…'
                : 'Thinking…'}
            </p>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <div className="ec-chat-input-row">
        <textarea
          className="ec-answer-input"
          placeholder="Describe your experience…"
          value={currentAnswer}
          onChange={e => setCurrentAnswer(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
          disabled={loading}
        />
        <button className="btn-primary ec-send-btn" onClick={() => handleSend(false)} disabled={!currentAnswer.trim() || loading}>
          {loading ? '…' : 'Send'}
        </button>
      </div>

      <div className="keq-finish-row">
        <button className="btn-primary ec-finish-btn" onClick={() => handleSend(true)} disabled={loading || allResolved.length === 0}>
          Finish &amp; Generate Rewrites
        </button>
      </div>
    </div>
  );
}

export default KeywordEquivalencyPanel;
