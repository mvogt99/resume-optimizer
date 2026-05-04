import React, { useState, useEffect, useRef, useCallback } from 'react';
import api from '../services/api';
import '../styles/DeepAnalysis.css';

function DeepAnalysis() {
  // Profile state
  const [profile, setProfile] = useState(null);
  const [profileMeta, setProfileMeta] = useState(null);
  const [building, setBuilding] = useState(false);

  // Interview state
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [depthAssessment, setDepthAssessment] = useState({});
  const [liveInsights, setLiveInsights] = useState([]);
  const [isComplete, setIsComplete] = useState(false);
  const [suggestions, setSuggestions] = useState([]);

  // Role synthesis state
  const [roleSynthesis, setRoleSynthesis] = useState(null);
  const [roleJobText, setRoleJobText] = useState('');
  const [loadingRole, setLoadingRole] = useState(false);

  // View state
  const [view, setView] = useState('overview'); // 'overview' | 'interview' | 'role'
  const [error, setError] = useState('');

  const messagesEndRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Load existing profile on mount
  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const data = await api.getDeepProfile();
      setProfileMeta(data);
      setProfile(data.profile);
    } catch (err) {
      if (err.response?.status !== 404) {
        console.error('Failed to load deep profile:', err);
      }
    }
  };

  const handleBuildProfile = async () => {
    setBuilding(true);
    setError('');
    try {
      const data = await api.buildDeepProfile();
      setProfile(data.profile);
      setProfileMeta({ profile: data.profile, source_summary: data.source_summary, updated_at: data.updated_at });
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to build profile');
    } finally {
      setBuilding(false);
    }
  };

  const handleStartInterview = async (mode = 'comprehensive', jobText = null) => {
    setError('');
    try {
      const data = await api.startDeepInterview(mode, jobText);
      setSessionId(data.session_id);
      setMessages([{ role: 'assistant', content: data.message }]);
      setDepthAssessment(data.depth_assessment || {});
      setSuggestions(data.suggestions || []);
      setIsComplete(false);
      setLiveInsights([]);
      setView('interview');
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to start interview');
    }
  };

  const handleSendMessage = async (messageText) => {
    const msg = messageText || input.trim();
    if (!msg || !sessionId || sending) return;

    setMessages(prev => [...prev, { role: 'user', content: msg }]);
    setInput('');
    setSending(true);

    try {
      const data = await api.sendDeepInterviewMessage(sessionId, msg);
      setMessages(prev => [...prev, { role: 'assistant', content: data.message }]);
      setDepthAssessment(data.depth_assessment || depthAssessment);
      setSuggestions(data.suggestions || []);
      setIsComplete(data.is_complete || false);

      if (data.updated_insights?.length > 0) {
        setLiveInsights(prev => [...prev, ...data.updated_insights.map(i => ({ ...i, isNew: true }))]);
        // Remove "new" flag after animation
        setTimeout(() => {
          setLiveInsights(prev => prev.map(i => ({ ...i, isNew: false })));
        }, 2000);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const handleFinalize = async () => {
    if (!sessionId) return;
    setSending(true);
    try {
      const data = await api.finalizeDeepInterview(sessionId);
      setProfile(data.profile);
      if (data.role_synthesis) {
        setRoleSynthesis(data.role_synthesis);
      }
      setView('overview');
      setSessionId(null);
      await loadProfile();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to finalize');
    } finally {
      setSending(false);
    }
  };

  const handleRoleSynthesis = async () => {
    if (!roleJobText || roleJobText.length < 50) {
      setError('Job description must be at least 50 characters');
      return;
    }
    setLoadingRole(true);
    setError('');
    try {
      const data = await api.getRoleSynthesis(roleJobText);
      setRoleSynthesis(data);
      setView('role');
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to generate role synthesis');
    } finally {
      setLoadingRole(false);
    }
  };

  const renderProgressRing = (percent) => {
    const radius = 54;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percent / 100) * circumference;
    const color = percent >= 70 ? '#22c55e' : percent >= 40 ? '#f59e0b' : '#ef4444';
    return (
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="#333" strokeWidth="8" />
        <circle
          cx="70" cy="70" r={radius} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 70 70)"
        />
        <text x="70" y="70" textAnchor="middle" dominantBaseline="central"
          fontSize="28" fontWeight="bold" fill={color}>
          {percent}
        </text>
        <text x="70" y="90" textAnchor="middle" fontSize="12" fill="#888">fit score</text>
      </svg>
    );
  };

  const renderDepthBar = () => {
    const areas = Object.entries(depthAssessment);
    if (areas.length === 0) return null;
    return (
      <div className="depth-assessment-bar">
        {areas.map(([area, status]) => (
          <div key={area} className="depth-segment-wrapper">
            <div className={`depth-segment ${status}`}>
              <div className="depth-fill" />
            </div>
            <span className="depth-label">{area.replace(/_/g, ' ')}</span>
          </div>
        ))}
      </div>
    );
  };

  // --- Profile Overview ---
  const renderProfileOverview = () => {
    if (!profile) {
      return (
        <div className="deep-analysis-container">
          <div className="deep-profile-header">
            <h2>Deep Professional Analysis</h2>
          </div>
          <div className="profile-summary-card" style={{ textAlign: 'center', padding: '40px' }}>
            <h3>No deep profile yet</h3>
            <p style={{ color: '#888', margin: '16px 0' }}>
              Build a comprehensive profile by aggregating all your data sources:
              LinkedIn, project analyses, journey mining, experience sessions, and skills interviews.
            </p>
            <button className="build-profile-btn" onClick={handleBuildProfile} disabled={building}>
              {building ? 'Building Profile...' : 'Build Deep Profile'}
            </button>
          </div>
        </div>
      );
    }

    return (
      <div className="deep-analysis-container">
        <div className="deep-profile-header">
          <div>
            <h2>Deep Professional Profile</h2>
            {profileMeta?.source_summary && (
              <span className="source-summary">{profileMeta.source_summary}</span>
            )}
          </div>
          <div className="header-actions">
            <button className="build-profile-btn" onClick={handleBuildProfile} disabled={building}>
              {building ? 'Rebuilding...' : 'Rebuild Profile'}
            </button>
            <button className="start-interview-btn" onClick={() => handleStartInterview('comprehensive')}>
              Deepen with Interview
            </button>
            <button className="start-interview-btn" onClick={() => setView('role')}>
              Role Analysis
            </button>
          </div>
        </div>

        {/* Professional Summary */}
        <div className="profile-summary-card">
          <h3>Professional Summary</h3>
          <p>{profile.professional_summary}</p>
        </div>

        <div className="deep-profile-overview">
          {/* Career Arc */}
          {profile.career_arc?.phases?.length > 0 && (
            <div className="career-arc-section">
              <h3>Career Arc {profile.career_arc.trajectory && <span className="trajectory-badge">{profile.career_arc.trajectory}</span>}</h3>
              <div className="career-arc-timeline">
                {profile.career_arc.phases.map((phase, i) => (
                  <div key={i} className="career-phase">
                    <div className="phase-period">{phase.period}</div>
                    <div className="phase-title">{phase.title}</div>
                    <div className="phase-focus">{phase.focus}</div>
                    {phase.key_achievements?.map((ach, j) => (
                      <div key={j} className="phase-achievement">- {ach}</div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Technology Mastery */}
          {profile.technology_mastery?.length > 0 && (
            <div className="tech-mastery-section">
              <h3>Technology Mastery</h3>
              <div className="tech-mastery-grid">
                {profile.technology_mastery.slice(0, 12).map((tech, i) => (
                  <div key={i} className="tech-mastery-card">
                    <div className="tech-header">
                      <span className="tech-name">{tech.name}</span>
                      <span className={`proficiency-badge ${tech.proficiency}`}>
                        {tech.proficiency}
                      </span>
                    </div>
                    {tech.years_approx > 0 && (
                      <div className="tech-years">{tech.years_approx}+ years</div>
                    )}
                    {tech.contexts?.length > 0 && (
                      <div className="tech-contexts">{tech.contexts.join(', ')}</div>
                    )}
                    <div className="tech-evidence">
                      <span className="evidence-count">
                        {tech.evidence?.length || 0} evidence sources
                      </span>
                      {tech.endorsement_count > 0 && (
                        <span className="endorsement-badge">{tech.endorsement_count} endorsements</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Higher-Order Skills */}
          {profile.higher_order_skills?.length > 0 && (
            <div className="higher-order-skills-section">
              <h3>Higher-Order Skills</h3>
              <div className="tech-mastery-grid">
                {profile.higher_order_skills.map((skill, i) => (
                  <div key={i} className="tech-mastery-card">
                    <div className="tech-header">
                      <span className="tech-name">{skill.skill}</span>
                      <span className={`proficiency-badge ${skill.proficiency}`}>
                        {skill.proficiency}
                      </span>
                    </div>
                    {skill.demonstrated_in?.length > 0 && (
                      <div className="tech-contexts">{skill.demonstrated_in.join(', ')}</div>
                    )}
                    <div className="tech-evidence">
                      <span className="evidence-count">
                        {skill.evidence?.length || 0} evidence sources
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Business Impacts */}
          {profile.business_impacts?.length > 0 && (
            <div className="business-impacts-section">
              <h3>Business Impacts</h3>
              <div className="business-impact-list">
                {profile.business_impacts.map((impact, i) => (
                  <div key={i} className="business-impact-item">
                    <div className="impact-title">{impact.title}</div>
                    <div className="impact-context">{impact.context} — {impact.scope}</div>
                    {impact.metrics && (
                      <div className="impact-metrics">
                        {impact.metrics.before && <span>Before: {impact.metrics.before}</span>}
                        {impact.metrics.after && <span>After: {impact.metrics.after}</span>}
                        {impact.metrics.improvement && <span className="improvement">{impact.metrics.improvement}</span>}
                      </div>
                    )}
                    {impact.star_bullet && (
                      <div className="star-bullet">{impact.star_bullet}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Leadership */}
          {profile.leadership_profile?.team_scope && (
            <div className="leadership-section">
              <h3>Leadership Profile</h3>
              <div className="leadership-scope">Team scope: {profile.leadership_profile.team_scope}</div>
              {profile.leadership_profile.mentoring_evidence?.length > 0 && (
                <div className="leadership-list">
                  <h4>Mentoring</h4>
                  {profile.leadership_profile.mentoring_evidence.map((e, i) => (
                    <div key={i} className="leadership-item">{e}</div>
                  ))}
                </div>
              )}
              {profile.leadership_profile.decision_examples?.length > 0 && (
                <div className="leadership-list">
                  <h4>Key Decisions</h4>
                  {profile.leadership_profile.decision_examples.map((e, i) => (
                    <div key={i} className="leadership-item">{e}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Differentiators */}
          {profile.differentiators?.length > 0 && (
            <div className="differentiators-section">
              <h3>What Sets You Apart</h3>
              <div className="differentiators-grid">
                {profile.differentiators.map((diff, i) => (
                  <div key={i} className="differentiator-card">
                    <div className="diff-theme">{diff.theme}</div>
                    <div className="diff-narrative">{diff.narrative}</div>
                    {diff.evidence?.length > 0 && (
                      <div className="diff-evidence">
                        {diff.evidence.map((e, j) => (
                          <span key={j} className="insight-badge">{e}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Knowledge Gaps */}
          {profile.knowledge_gaps?.length > 0 && (
            <div className="knowledge-gaps-section">
              <h3>Areas for Development</h3>
              {profile.knowledge_gaps.map((gap, i) => (
                <div key={i} className="gap-item">
                  <span className="gap-area">{gap.area}</span>
                  <span className="gap-level">{gap.current_level}</span>
                  <span className="gap-evidence">{gap.evidence}</span>
                </div>
              ))}
            </div>
          )}

          {/* Cross-Source Insights */}
          {profile.cross_source_insights?.length > 0 && (
            <div className="cross-source-section">
              <h3>Cross-Source Insights</h3>
              {profile.cross_source_insights.map((insight, i) => (
                <div key={i} className="cross-source-banner">
                  <div className="insight-text">{insight.insight}</div>
                  <div className="insight-sources">
                    {insight.sources?.map((s, j) => (
                      <span key={j} className="insight-badge">{s}</span>
                    ))}
                  </div>
                  <div className="insight-significance">{insight.significance}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  // --- Interview Panel ---
  const renderInterviewPanel = () => (
    <div className="deep-interview-container">
      <div className="deep-chat-panel">
        {renderDepthBar()}

        <div className="deep-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`deep-message ${msg.role}`}>
              <div className="message-content">{msg.content}</div>
            </div>
          ))}
          {sending && (
            <div className="deep-message assistant">
              <div className="message-content typing">Thinking...</div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {suggestions.length > 0 && !isComplete && (
          <div className="suggestion-chips">
            {suggestions.map((s, i) => (
              <button key={i} className="suggestion-chip" onClick={() => handleSendMessage(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        {isComplete ? (
          <div className="completion-banner">
            <span>Interview complete! Your profile has been enriched.</span>
            <button className="finalize-btn" onClick={handleFinalize} disabled={sending}>
              {sending ? 'Finalizing...' : 'Finalize & Save Profile'}
            </button>
          </div>
        ) : (
          <div className="deep-input-row">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="Share your experience..."
              disabled={sending}
            />
            <button onClick={() => handleSendMessage()} disabled={sending || !input.trim()}>
              Send
            </button>
          </div>
        )}
      </div>

      <div className="deep-insights-sidebar">
        <h3>Live Insights</h3>
        {liveInsights.length === 0 ? (
          <div className="no-insights">Insights will appear here as the conversation progresses</div>
        ) : (
          liveInsights.map((insight, i) => (
            <div key={i} className={`insight-card ${insight.isNew ? 'new' : ''}`}>
              <span className="insight-area-badge">{insight.area}</span>
              <div className="insight-text">{insight.insight_text}</div>
              <div className="insight-source">{insight.evidence_source}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );

  // --- Role Targeting View ---
  const renderRoleTargeting = () => (
    <div className="role-synthesis-panel">
      {!roleSynthesis ? (
        <div className="role-input-section">
          <h3>Role-Specific Analysis</h3>
          <p className="role-description">
            Paste a job description to see how your deep profile maps to the role's requirements.
          </p>
          <textarea
            value={roleJobText}
            onChange={(e) => setRoleJobText(e.target.value)}
            placeholder="Paste the full job description here (min 50 characters)..."
            rows={8}
            className="role-textarea"
          />
          <div className="role-actions">
            <button className="build-profile-btn" onClick={handleRoleSynthesis}
              disabled={loadingRole || roleJobText.length < 50}>
              {loadingRole ? 'Analyzing...' : 'Analyze Fit'}
            </button>
            <button className="start-interview-btn"
              onClick={() => handleStartInterview('role_specific', roleJobText)}
              disabled={roleJobText.length < 50}>
              Deep Dive Interview
            </button>
          </div>
        </div>
      ) : (
        <div className="role-results">
          <div className="fit-score-container">
            {renderProgressRing(roleSynthesis.fit_score || 0)}
            {(roleSynthesis.strengths?.length > 0 || roleSynthesis.gaps?.length > 0) && (
              <div className="fit-tags-row" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginTop: 12 }}>
                {(roleSynthesis.strengths || []).map((s, i) => (
                  <span key={`s-${i}`} style={{
                    background: '#e8f5e9', color: '#2e7d32', borderRadius: 12,
                    padding: '4px 12px', fontSize: 12, fontWeight: 500,
                  }}>{typeof s === 'string' ? s : s.skill || s.area || JSON.stringify(s)}</span>
                ))}
                {(roleSynthesis.gaps || []).map((g, i) => (
                  <span key={`g-${i}`} style={{
                    background: '#fce4ec', color: '#c62828', borderRadius: 12,
                    padding: '4px 12px', fontSize: 12, fontWeight: 500,
                  }}>{typeof g === 'string' ? g : g.skill || g.area || JSON.stringify(g)}</span>
                ))}
              </div>
            )}
          </div>

          {roleSynthesis.top_angles?.length > 0 && (
            <div className="top-angles-section">
              <h3>Top Angles</h3>
              <div className="top-angles-list">
                {roleSynthesis.top_angles.map((angle, i) => (
                  <div key={i} className="angle-card">
                    <span className={`strength-indicator ${angle.strength}`} />
                    <div className="angle-content">
                      <div className="angle-title">{angle.angle}</div>
                      <div className="angle-evidence">{angle.evidence}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {roleSynthesis.tailored_bullets?.length > 0 && (
            <div className="tailored-bullets-section">
              <h3>Tailored Resume Bullets</h3>
              <div className="tailored-bullets-list">
                {roleSynthesis.tailored_bullets.map((item, i) => (
                  <div key={i} className="tailored-bullet">
                    <span className={`relevance-badge ${item.relevance}`}>{item.relevance}</span>
                    <span>{item.bullet}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {roleSynthesis.gap_mitigation?.length > 0 && (
            <div className="gap-mitigation-section">
              <h3>Gap Mitigation</h3>
              <div className="gap-mitigation-list">
                {roleSynthesis.gap_mitigation.map((item, i) => (
                  <div key={i} className="gap-mitigation-item">
                    <div className="gap-name">{item.gap}</div>
                    <div className="gap-mitigation-text">{item.mitigation}</div>
                    {item.transferable_skill && (
                      <div className="transferable-skill">Transferable: {item.transferable_skill}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {roleSynthesis.interview_talking_points?.length > 0 && (
            <div className="talking-points-section">
              <h3>Interview Talking Points</h3>
              {roleSynthesis.interview_talking_points.map((point, i) => (
                <div key={i} className="talking-point-card">
                  <div className="tp-topic">{point.topic}</div>
                  <div className="tp-story">{point.story}</div>
                  <div className="tp-connection">{point.connection_to_role}</div>
                </div>
              ))}
            </div>
          )}

          <div className="role-actions" style={{ marginTop: '20px' }}>
            <button className="start-interview-btn" onClick={() => {
              setRoleSynthesis(null);
            }}>
              Analyze Different Role
            </button>
            <button className="start-interview-btn"
              onClick={() => handleStartInterview('role_specific', roleJobText)}>
              Refine with Interview
            </button>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div>
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError('')}>×</button>
        </div>
      )}

      <div className="view-toggle">
        <button className={view === 'overview' ? 'active' : ''} onClick={() => setView('overview')}>
          Profile Overview
        </button>
        <button className={view === 'interview' ? 'active' : ''} onClick={() => {
          if (!sessionId) handleStartInterview();
          else setView('interview');
        }}>
          Deep Interview
        </button>
        <button className={view === 'role' ? 'active' : ''} onClick={() => setView('role')}>
          Role Analysis
        </button>
      </div>

      {building && (
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Building deep profile from all sources...</span>
        </div>
      )}

      {view === 'overview' && renderProfileOverview()}
      {view === 'interview' && sessionId && renderInterviewPanel()}
      {view === 'role' && renderRoleTargeting()}
    </div>
  );
}

export default DeepAnalysis;
