import React, { useState, useRef, useEffect } from 'react';
import api from '../services/api';
import { saveChatHistoryFromMessages } from '../utils/chatHistory';
import ExpertComparisonMergedView from './ExpertComparisonMergedView';

/**
 * ExpertComparison — Step 3 add-on panel.
 *
 * Flow:
 *   input → comparing → results → interview → merging → merged
 *
 * Props:
 *   ourText        string — our AI's optimized resume text
 *   jobDescription string — current job description text (optional)
 */
function ExpertComparison({ ourText = '', jobDescription = '' }) {
  const [stage, setStage] = useState('input');
  const [expertText, setExpertText] = useState('');
  const [comparison, setComparison] = useState(null);
  const [error, setError] = useState('');

  // Interview state
  const [history, setHistory] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [currentAnswer, setCurrentAnswer] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [interviewLoading, setInterviewLoading] = useState(false);
  const [suggestedDone, setSuggestedDone] = useState(false);

  // Merge state
  const [mergedData, setMergedData] = useState(null);
  const [mergeError, setMergeError] = useState('');

  // Results rescore state
  const [rescoring, setRescoring] = useState(false);
  const [rescoreData, setRescoreData] = useState(null);

  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // ── Comparison ──────────────────────────────────────────────────────────

  const handleCompare = async () => {
    if (!expertText.trim() || expertText.trim().length < 50) {
      setError('Please paste at least 50 characters of the expert AI version.');
      return;
    }
    setError('');
    setStage('comparing');
    try {
      const result = await api.runExpertComparison({
        ourVersionText: ourText,
        expertVersionText: expertText.trim(),
        jobDescription,
      });
      setComparison(result);
      setStage('results');
    } catch (err) {
      setError(err.response?.data?.error || 'Comparison failed. Please try again.');
      setStage('input');
    }
  };

  // ── Interview ───────────────────────────────────────────────────────────

  const startInterview = () => {
    const questions = comparison?.interview_questions || [];
    const firstQ = questions[0] || 'Tell me about the experience highlighted in these resumes — which version feels more accurate to you?';
    setCurrentQuestion(firstQ);
    setHistory([]);
    setSuggestedDone(false);
    setChatMessages([
      {
        role: 'assistant',
        content:
          "Let's explore these differences together. I'll ask questions to understand your actual experience — there's no fixed number of questions. Answer as much or as little as you like, and click **Finish & Generate My Personalized Resume** whenever you're ready.",
      },
      { role: 'assistant', content: firstQ },
    ]);
    setStage('interview');
  };

  const handleInterviewSend = async (userFinished = false) => {
    const answer = currentAnswer.trim();
    if ((!answer && !userFinished) || interviewLoading) return;

    if (answer) {
      setChatMessages(prev => [...prev, { role: 'user', content: answer }]);
    }
    setCurrentAnswer('');
    setInterviewLoading(true);

    const updatedHistory = answer
      ? [...history, { question: currentQuestion, answer }]
      : history;

    try {
      const result = await api.sendExpertInterviewMessage({
        history: updatedHistory,
        currentQuestion,
        userAnswer: answer || '(finishing interview)',
        userFinished,
        context: {
          job_text: jobDescription,
          disagreements: comparison?.disagreements || [],
          recommendation: comparison?.recommendation || '',
        },
      });

      setHistory(updatedHistory);
      setSuggestedDone(result.suggested_done || false);

      if (answer && result.insight) {
        setChatMessages(prev => [...prev, { role: 'assistant', content: result.insight }]);
      }

      if (userFinished || result.is_complete) {
        // Trigger merge generation
        setChatMessages(prev => [
          ...prev,
          { role: 'assistant', content: 'Generating your personalized resume — this takes a moment…' },
        ]);
        setStage('merging');
        setMergeError('');
        try {
          const mergeResult = await api.generateMergedResume({
            ourText,
            expertText: expertText.trim(),
            interviewHistory: updatedHistory,
            jobDescription,
          });
          setMergedData(mergeResult);
          setStage('merged');
        } catch (mergeErr) {
          setMergeError(
            mergeErr.response?.data?.error || 'Merge generation failed. Please try again.'
          );
          setStage('interview');
          setChatMessages(prev => [
            ...prev,
            { role: 'assistant', content: 'Unable to generate the merged resume right now. Please try again.' },
          ]);
        }
      } else if (result.next_question) {
        setCurrentQuestion(result.next_question);
        setChatMessages(prev => [...prev, { role: 'assistant', content: result.next_question }]);
      }
    } catch (err) {
      setChatMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Unable to process your answer right now. Please try again.' },
      ]);
    } finally {
      setInterviewLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleInterviewSend(false);
    }
  };

  const handleReset = () => {
    setStage('input');
    setComparison(null);
    setHistory([]);
    setChatMessages([]);
    setCurrentQuestion('');
    setCurrentAnswer('');
    setSuggestedDone(false);
    setMergedData(null);
    setMergeError('');
    setRescoreData(null);
  };

  // ── Results rescore ─────────────────────────────────────────────────────

  const handleRescore = async () => {
    setRescoring(true);
    setRescoreData(null);
    try {
      const [ourRes, expRes] = await Promise.all([
        api.scoreResumeText(ourText, jobDescription),
        api.scoreResumeText(expertText, jobDescription),
      ]);
      setRescoreData({ ours: ourRes.ats_score, expert: expRes.ats_score });
    } catch {
      // silently ignore — original scores remain visible
    } finally {
      setRescoring(false);
    }
  };

  // ── Render: input ────────────────────────────────────────────────────────

  if (stage === 'input') {
    return (
      <div className="expert-comparison">
        <p className="expert-comparison-hint">
          Paste the LinkedIn AI or another expert AI's version of your optimized resume below.
          We'll compare ATS scores, identify agreements and disagreements, then guide you through
          an open-ended interview and synthesize a truly personalized resume.
        </p>
        <textarea
          className="expert-text-input"
          placeholder="Paste expert AI resume here…"
          value={expertText}
          onChange={e => setExpertText(e.target.value)}
          rows={12}
        />
        {error && <p className="expert-error">{error}</p>}
        <button
          className="btn-primary expert-compare-btn"
          onClick={handleCompare}
          disabled={!expertText.trim()}
        >
          Analyze &amp; Compare
        </button>
      </div>
    );
  }

  if (stage === 'comparing') {
    return (
      <div className="expert-comparison expert-comparison--loading">
        <div className="spinner" />
        <p>Analyzing both versions against the job description…</p>
      </div>
    );
  }

  if (stage === 'merging') {
    return (
      <div className="expert-comparison expert-comparison--loading">
        <div className="spinner" />
        <p>Synthesizing your personalized resume using both versions, your interview answers, LinkedIn profile, and career knowledge graph…</p>
      </div>
    );
  }

  if (stage === 'merged' && mergedData) {
    return (
      <div className="expert-comparison">
        <ExpertComparisonMergedView
          mergedData={mergedData}
          ourText={ourText}
          jobDescription={jobDescription}
          chatMessages={chatMessages}
          onContinue={() => setStage('interview')}
          onReset={handleReset}
        />
      </div>
    );
  }

  if (!comparison) return null;

  const {
    ats_scores, agreements, disagreements, expert_unique_additions,
    our_unique_additions, recommendation, interview_questions, length_warning,
  } = comparison;

  const displayOurs = rescoreData?.ours ?? ats_scores.ours;
  const displayExpert = rescoreData?.expert ?? ats_scores.expert;
  const ourBetter = displayOurs > displayExpert;
  const scoreDiff = Math.abs(displayOurs - displayExpert);

  // ── Render: results ──────────────────────────────────────────────────────

  if (stage === 'results') {
    return (
      <div className="expert-comparison">

        {length_warning && (
          <div className="ec-length-warning">
            <strong>Length difference detected:</strong> {length_warning}
          </div>
        )}

        <div className="ec-scores">
          <div className={`ec-score-card ${ourBetter ? 'ec-score-card--winner' : ''}`}>
            <div className="ec-score-label">Our AI Version</div>
            <div className="ec-score-value">{displayOurs}<span>/100</span></div>
            {ourBetter && <div className="ec-score-badge">Higher ATS</div>}
          </div>
          <div className="ec-score-divider">vs</div>
          <div className={`ec-score-card ${!ourBetter ? 'ec-score-card--winner' : ''}`}>
            <div className="ec-score-label">Expert AI Version</div>
            <div className="ec-score-value">{displayExpert}<span>/100</span></div>
            {!ourBetter && <div className="ec-score-badge">Higher ATS</div>}
          </div>
        </div>

        <div className="ec-rescore-row">
          <button className="btn-ec-rescore" onClick={handleRescore} disabled={rescoring}>
            {rescoring ? 'Scoring…' : rescoreData ? 'Re-score Again' : 'Re-score Both Versions'}
          </button>
          {rescoreData && (
            <span className="ec-rescore-note">Scores updated against current job description.</span>
          )}
        </div>

        {scoreDiff <= 5 && (
          <p className="ec-tie-note">
            Scores are within 5 points — content quality and accuracy matter more than the raw score here.
          </p>
        )}

        {recommendation && (
          <div className="ec-recommendation">
            <strong>AI Recommendation:</strong> {recommendation}
          </div>
        )}

        {agreements?.length > 0 && (
          <div className="ec-section">
            <h4 className="ec-section-title ec-agree">✓ Agreements</h4>
            <ul className="ec-list">
              {agreements.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          </div>
        )}

        {disagreements?.length > 0 && (
          <div className="ec-section">
            <h4 className="ec-section-title ec-disagree">⚡ Key Differences</h4>
            {disagreements.map((d, i) => (
              <div key={i} className="ec-diff-card">
                <div className="ec-diff-topic">{d.topic}</div>
                <div className="ec-diff-row">
                  <div className="ec-diff-col ec-diff-ours">
                    <span className="ec-diff-col-label">Ours</span>
                    <p>{d.ours}</p>
                  </div>
                  <div className="ec-diff-col ec-diff-expert">
                    <span className="ec-diff-col-label">Expert</span>
                    <p>{d.expert}</p>
                  </div>
                </div>
                {d.expert_rationale && (
                  <p className="ec-diff-rationale">
                    <em>Expert reasoning:</em> {d.expert_rationale}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="ec-unique-row">
          {expert_unique_additions?.length > 0 && (
            <div className="ec-unique">
              <h4 className="ec-section-title">Expert only adds:</h4>
              <ul className="ec-list">
                {expert_unique_additions.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </div>
          )}
          {our_unique_additions?.length > 0 && (
            <div className="ec-unique">
              <h4 className="ec-section-title">We uniquely add:</h4>
              <ul className="ec-list">
                {our_unique_additions.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </div>
          )}
        </div>

        <div className="ec-interview-cta">
          <p>
            Ready to create your personalized resume? Answer a few questions about your
            actual experience and we'll synthesize the best of both versions — tailored to you.
          </p>
          <button className="btn-primary" onClick={startInterview}>
            Start Guided Interview &amp; Build My Resume
          </button>
        </div>

        <button className="btn-secondary ec-reset-btn" onClick={handleReset}>
          Compare a Different Version
        </button>
      </div>
    );
  }

  // ── Render: interview ────────────────────────────────────────────────────

  return (
    <div className="expert-comparison">
      <div className="ec-interview">
        <div className="ec-interview-header">
          <h4 className="ec-interview-title">Guided Interview</h4>
          <div className="ec-interview-header-actions">
            {chatMessages.length > 0 && (
              <button
                className="btn-save-history"
                onClick={() => saveChatHistoryFromMessages(chatMessages, 'Expert Comparison Interview')}
                title="Save chat history"
              >
                Save History
              </button>
            )}
          </div>
        </div>

        {suggestedDone && (
          <div className="ec-suggested-done">
            I have enough context to write a strong personalized recommendation.
            You can keep exploring or finish whenever you're ready.
          </div>
        )}

        <div className="ec-chat">
          {chatMessages.map((m, i) => (
            <div key={i} className={`ec-msg ec-msg--${m.role}`}>
              <p>{m.content}</p>
            </div>
          ))}
          {interviewLoading && (
            <div className="ec-msg ec-msg--assistant">
              <p className="ec-typing">Thinking…</p>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="ec-chat-input-row">
          <textarea
            className="ec-answer-input"
            placeholder="Your answer…"
            value={currentAnswer}
            onChange={e => setCurrentAnswer(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={3}
            disabled={interviewLoading}
          />
          <button
            className="btn-primary ec-send-btn"
            onClick={() => handleInterviewSend(false)}
            disabled={!currentAnswer.trim() || interviewLoading}
          >
            {interviewLoading ? '…' : 'Send'}
          </button>
        </div>

        {mergeError && <p className="expert-error">{mergeError}</p>}

        <div className="ec-finish-row">
          <button
            className="btn-primary ec-finish-btn"
            onClick={() => handleInterviewSend(true)}
            disabled={interviewLoading}
          >
            Finish &amp; Generate My Personalized Resume
          </button>
          <button className="btn-secondary" onClick={() => setStage('results')}>
            ← Back to Comparison
          </button>
        </div>
      </div>
    </div>
  );
}

export default ExpertComparison;
