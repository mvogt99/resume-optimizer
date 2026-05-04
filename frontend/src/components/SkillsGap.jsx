import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';
import '../styles/SkillsGap.css';

function SkillsGap({ resumeId, onClose }) {
  const [skillsData, setSkillsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Feedback state
  const [confirmedSkills, setConfirmedSkills] = useState([]);
  const [removedSkills, setRemovedSkills] = useState([]);
  const [addedSkills, setAddedSkills] = useState([]);
  const [newSkillInput, setNewSkillInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [rescoring, setRescoring] = useState(false);

  // Skills interview state
  const [interviewSessionId, setInterviewSessionId] = useState(null);
  const [interviewMessages, setInterviewMessages] = useState([]);
  const [interviewInput, setInterviewInput] = useState('');
  const [interviewSkills, setInterviewSkills] = useState([]);
  const [interviewLoading, setInterviewLoading] = useState(false);
  const [interviewResults, setInterviewResults] = useState(null);
  const [selectedBatchSkills, setSelectedBatchSkills] = useState([]);
  const [batchMode, setBatchMode] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    const fetchSkillsGap = async () => {
      try {
        const response = await api.getSkillsGap(resumeId);
        setSkillsData(response);
      } catch (err) {
        setError('Failed to fetch skills gap data');
      } finally {
        setLoading(false);
      }
    };
    fetchSkillsGap();
  }, [resumeId]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [interviewMessages]);

  const handleConfirmSkill = (skill) => {
    if (!confirmedSkills.includes(skill)) {
      setConfirmedSkills([...confirmedSkills, skill]);
    }
  };

  const handleUnconfirmSkill = (skill) => {
    setConfirmedSkills(confirmedSkills.filter(s => s !== skill));
  };

  const handleRemoveSkill = (skill) => {
    if (!removedSkills.includes(skill)) {
      setRemovedSkills([...removedSkills, skill]);
    }
  };

  const handleUnremoveSkill = (skill) => {
    setRemovedSkills(removedSkills.filter(s => s !== skill));
  };

  const handleAddSkill = () => {
    const skill = newSkillInput.trim();
    if (skill && !addedSkills.includes(skill)) {
      setAddedSkills([...addedSkills, skill]);
      setNewSkillInput('');
    }
  };

  const handleRemoveAddedSkill = (skill) => {
    setAddedSkills(addedSkills.filter(s => s !== skill));
  };

  const handleRescore = async () => {
    setRescoring(true);
    try {
      const response = await api.rescoreSkillsGap(
        resumeId, confirmedSkills, removedSkills, addedSkills
      );
      setSkillsData(response);
      setIsEditing(false);
    } catch (err) {
      setError('Failed to re-score skills gap');
    } finally {
      setRescoring(false);
    }
  };

  // --- Skills interview handlers ---

  const startInterview = async (skills) => {
    setInterviewLoading(true);
    setInterviewResults(null);
    setInterviewMessages([]);
    setInterviewSkills(skills);
    try {
      const data = await api.startSkillsInterview(resumeId, skills);
      setInterviewSessionId(data.session_id);
      setInterviewMessages([{ role: 'assistant', content: data.message }]);
    } catch (err) {
      setError('Failed to start skills interview');
    } finally {
      setInterviewLoading(false);
    }
  };

  const sendInterviewMessage = async () => {
    if (!interviewInput.trim() || interviewLoading) return;
    const msg = interviewInput.trim();
    setInterviewInput('');
    setInterviewMessages(prev => [...prev, { role: 'user', content: msg }]);
    setInterviewLoading(true);
    try {
      const data = await api.sendSkillsInterviewMessage(interviewSessionId, msg);
      setInterviewMessages(prev => [...prev, { role: 'assistant', content: data.message }]);
    } catch (err) {
      setError('Failed to send message');
    } finally {
      setInterviewLoading(false);
    }
  };

  const finalizeInterview = async () => {
    setInterviewLoading(true);
    try {
      const data = await api.finalizeSkillsInterview(interviewSessionId);
      setInterviewResults(data.results || []);
    } catch (err) {
      setError('Failed to finalize interview');
    } finally {
      setInterviewLoading(false);
    }
  };

  const applyInterviewResults = async () => {
    if (!interviewResults) return;
    const validatedSkills = interviewResults
      .filter(r => r.has_skill)
      .map(r => r.skill);
    if (validatedSkills.length > 0) {
      const newConfirmed = [...new Set([...confirmedSkills, ...validatedSkills])];
      setConfirmedSkills(newConfirmed);
      // Auto-rescore
      setRescoring(true);
      try {
        const response = await api.rescoreSkillsGap(
          resumeId, newConfirmed, removedSkills, addedSkills
        );
        setSkillsData(response);
      } catch (err) {
        setError('Failed to re-score after interview');
      } finally {
        setRescoring(false);
      }
    }
    closeInterview();
  };

  const closeInterview = () => {
    setInterviewSessionId(null);
    setInterviewMessages([]);
    setInterviewResults(null);
    setInterviewSkills([]);
    setSelectedBatchSkills([]);
    setBatchMode(false);
  };

  const toggleBatchSkill = (skill) => {
    setSelectedBatchSkills(prev =>
      prev.includes(skill) ? prev.filter(s => s !== skill) : [...prev, skill]
    );
  };

  const hasChanges = confirmedSkills.length > 0 || removedSkills.length > 0 || addedSkills.length > 0;

  if (loading) {
    return (
      <div className="skills-gap">
        <div className="skills-gap-loading">Loading skills analysis...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="skills-gap">
        <div className="skills-gap-error">{error}</div>
      </div>
    );
  }

  const { skills_gap, relevant_accomplishments, relevant_recommendations } = skillsData;
  const coverage = skills_gap.coverage_percent;

  const renderProgressRing = (percent) => {
    const radius = 54;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (percent / 100) * circumference;
    const color = percent >= 60 ? '#4caf50' : percent >= 30 ? '#ff9800' : '#f44336';

    return (
      <div className="progress-ring-container">
        <svg width="140" height="140" viewBox="0 0 140 140">
          <circle cx="70" cy="70" r={radius} fill="none" stroke="#e8e8e8" strokeWidth="10" />
          <circle
            cx="70" cy="70" r={radius} fill="none"
            stroke={color} strokeWidth="10" strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform="rotate(-90 70 70)"
            style={{ transition: 'stroke-dashoffset 0.8s ease' }}
          />
        </svg>
        <div className="progress-ring-text">
          <span className="progress-ring-value">{Math.round(percent)}%</span>
          <span className="progress-ring-label">Coverage</span>
        </div>
      </div>
    );
  };

  const renderInterviewPanel = () => {
    if (!interviewSessionId) return null;
    return (
      <div className="skill-interview-panel">
        <div className="interview-header">
          <h4>Skills Interview: {interviewSkills.join(', ')}</h4>
          <button className="btn-close-interview" onClick={closeInterview}>&times;</button>
        </div>
        <div className="interview-messages">
          {interviewMessages.map((m, i) => (
            <div key={i} className={`interview-msg ${m.role}`}>
              {m.content}
            </div>
          ))}
          {interviewLoading && (
            <div className="interview-msg assistant">Thinking...</div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {interviewResults ? (
          <div className="interview-results">
            <h4>Results</h4>
            {interviewResults.map((r, i) => (
              <div key={i} className={`interview-result ${r.has_skill ? 'has-skill' : 'no-skill'}`}>
                <div className="result-header">
                  <span className="result-skill">{r.skill}</span>
                  <span className={`result-badge confidence-${r.confidence}`}>
                    {r.has_skill ? 'Validated' : 'Not confirmed'} ({r.confidence})
                  </span>
                </div>
                {r.star_bullet && <div className="result-bullet">{r.star_bullet}</div>}
                {r.evidence_summary && <div className="result-evidence">{r.evidence_summary}</div>}
              </div>
            ))}
            <button className="btn-apply-results" onClick={applyInterviewResults}>
              Apply Validated Skills & Re-Score
            </button>
          </div>
        ) : (
          <div className="interview-input-row">
            <input
              type="text"
              value={interviewInput}
              onChange={e => setInterviewInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendInterviewMessage()}
              placeholder="Describe your experience..."
              disabled={interviewLoading}
            />
            <button onClick={sendInterviewMessage} disabled={interviewLoading || !interviewInput.trim()}>
              Send
            </button>
            <button className="btn-finalize-interview" onClick={finalizeInterview} disabled={interviewLoading}>
              Finalize
            </button>
          </div>
        )}
      </div>
    );
  };

  const renderSkillList = (skills, type) => {
    if (!skills || skills.length === 0) {
      return <div className="skills-empty">None</div>;
    }
    return (
      <div className="skills-list">
        {type === 'red' && skills.length > 1 && !interviewSessionId && (
          <div className="batch-controls">
            <label className="batch-toggle">
              <input type="checkbox" checked={batchMode} onChange={() => {
                setBatchMode(!batchMode);
                setSelectedBatchSkills([]);
              }} />
              Batch select
            </label>
            {batchMode && selectedBatchSkills.length > 0 && (
              <button
                className="btn-discuss-batch"
                onClick={() => startInterview(selectedBatchSkills)}
              >
                Discuss Selected ({selectedBatchSkills.length})
              </button>
            )}
          </div>
        )}
        {skills.map((s, i) => {
          const isRemoved = removedSkills.includes(s.skill);
          const isConfirmed = confirmedSkills.includes(s.skill);
          if (isRemoved && !isEditing) return null;

          return (
            <div key={i} className={`skill-chip skill-chip-${type} ${isRemoved ? 'skill-removed' : ''} ${isConfirmed ? 'skill-confirmed' : ''}`}>
              {type === 'red' && batchMode && (
                <input
                  type="checkbox"
                  className="batch-select-checkbox"
                  checked={selectedBatchSkills.includes(s.skill)}
                  onChange={() => toggleBatchSkill(s.skill)}
                />
              )}
              <span className="skill-name">{s.skill}</span>
              {s.endorsements > 0 && (
                <span className="endorsement-badge">{s.endorsements}</span>
              )}
              {s.evidence_source && (
                <span className="evidence-badge" title={s.evidence_source}>P</span>
              )}
              {!interviewSessionId && (type === 'amber' || type === 'red') && (
                <button
                  className="skill-action-btn discuss"
                  title="Discuss this skill with AI"
                  onClick={() => startInterview([s.skill])}
                >?</button>
              )}
              {isEditing && (
                <div className="skill-actions">
                  {type === 'amber' && !isConfirmed && (
                    <button
                      className="skill-action-btn confirm"
                      title="I have this skill - add to resume"
                      onClick={() => handleConfirmSkill(s.skill)}
                    >+</button>
                  )}
                  {type === 'amber' && isConfirmed && (
                    <button
                      className="skill-action-btn undo"
                      title="Undo confirm"
                      onClick={() => handleUnconfirmSkill(s.skill)}
                    >-</button>
                  )}
                  {!isRemoved && (
                    <button
                      className="skill-action-btn remove"
                      title="Not relevant - remove from analysis"
                      onClick={() => handleRemoveSkill(s.skill)}
                    >&times;</button>
                  )}
                  {isRemoved && (
                    <button
                      className="skill-action-btn undo"
                      title="Restore skill"
                      onClick={() => handleUnremoveSkill(s.skill)}
                    >&#x21A9;</button>
                  )}
                </div>
              )}
              {!isEditing && s.tip && <div className="skill-tip">{s.tip}</div>}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="skills-gap">
      <div className="skills-gap-header">
        <h2>Skills Gap Analysis</h2>
        <div className="skills-gap-header-actions">
          {!isEditing ? (
            <button className="btn-edit-skills" onClick={() => setIsEditing(true)}>
              Adjust Skills
            </button>
          ) : (
            <>
              <button
                className="btn-rescore"
                onClick={handleRescore}
                disabled={!hasChanges || rescoring}
              >
                {rescoring ? 'Re-scoring...' : 'Re-Score'}
              </button>
              <button className="btn-cancel-edit" onClick={() => {
                setIsEditing(false);
                setConfirmedSkills([]);
                setRemovedSkills([]);
                setAddedSkills([]);
              }}>
                Cancel
              </button>
            </>
          )}
          {onClose && <button className="btn-close" onClick={onClose}>&times;</button>}
        </div>
      </div>

      <div className="skills-gap-overview">
        {renderProgressRing(coverage)}
        <div className="gap-stats">
          <div className="stat"><span className="stat-num">{skills_gap.total_job_keywords}</span><span className="stat-lbl">Job Keywords</span></div>
          <div className="stat stat-green"><span className="stat-num">{skills_gap.gap_summary.shown}</span><span className="stat-lbl">In Resume</span></div>
          <div className="stat stat-amber"><span className="stat-num">{skills_gap.gap_summary.can_add}</span><span className="stat-lbl">Can Add</span></div>
          <div className="stat stat-red"><span className="stat-num">{skills_gap.gap_summary.need_to_learn}</span><span className="stat-lbl">To Learn</span></div>
        </div>
      </div>

      {isEditing && (
        <div className="skills-feedback-bar">
          <div className="feedback-instructions">
            Click <strong>+</strong> to confirm skills you have, <strong>&times;</strong> to mark irrelevant skills, or add your own below.
          </div>
          <div className="add-skill-row">
            <input
              type="text"
              className="add-skill-input"
              placeholder="Add a skill you have..."
              value={newSkillInput}
              onChange={(e) => setNewSkillInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddSkill()}
            />
            <button className="btn-add-skill" onClick={handleAddSkill} disabled={!newSkillInput.trim()}>
              Add
            </button>
          </div>
          {addedSkills.length > 0 && (
            <div className="added-skills-list">
              {addedSkills.map((s, i) => (
                <span key={i} className="skill-chip skill-chip-added">
                  {s}
                  <button className="skill-remove-x" onClick={() => handleRemoveAddedSkill(s)}>&times;</button>
                </span>
              ))}
            </div>
          )}
          {hasChanges && (
            <div className="feedback-summary">
              {confirmedSkills.length > 0 && <span className="fb-confirmed">{confirmedSkills.length} confirmed</span>}
              {removedSkills.length > 0 && <span className="fb-removed">{removedSkills.length} removed</span>}
              {addedSkills.length > 0 && <span className="fb-added">{addedSkills.length} added</span>}
            </div>
          )}
        </div>
      )}

      {renderInterviewPanel()}

      <div className="skills-columns">
        <div className="skills-column">
          <h3 className="col-header col-green">Already in Resume</h3>
          {renderSkillList(skills_gap.skills_already_shown, 'green')}
        </div>
        <div className="skills-column">
          <h3 className="col-header col-amber">Add from LinkedIn</h3>
          {renderSkillList(skills_gap.skills_to_emphasize, 'amber')}
        </div>
        <div className="skills-column">
          <h3 className="col-header col-red">Skills to Learn</h3>
          {renderSkillList(skills_gap.skills_to_acquire, 'red')}
        </div>
      </div>

      {relevant_accomplishments && relevant_accomplishments.length > 0 && (
        <div className="accomplishments-section">
          <h3>Relevant Accomplishments</h3>
          {relevant_accomplishments.map((acc, i) => (
            <div key={i} className="accomplishment-item">
              <div className="acc-text">{acc.text}</div>
              <div className="acc-meta">
                <span className="acc-source">{acc.source_title} at {acc.source_company}</span>
                <span className="acc-score">{acc.relevance_score}%</span>
              </div>
              <div className="relevance-bar">
                <div className="relevance-fill" style={{ width: `${acc.relevance_score}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {relevant_recommendations && relevant_recommendations.length > 0 && (
        <div className="recommendations-section">
          <h3>Relevant Recommendations</h3>
          {relevant_recommendations.map((rec, i) => (
            <div key={i} className="recommendation-item">
              <div className="rec-text">"{rec.text}"</div>
              <div className="rec-author">
                <strong>{rec.author}</strong> &mdash; {rec.relationship}
              </div>
              <div className="relevance-bar">
                <div className="relevance-fill" style={{ width: `${rec.relevance_score}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default SkillsGap;
