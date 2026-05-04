import React, { useState } from 'react';
import api from '../services/api';

function CareerAdvisor() {
  const [analysis, setAnalysis] = useState(null);
  const [roadmap, setRoadmap] = useState(null);
  const [roles, setRoles] = useState(null);
  const [loading, setLoading] = useState('');
  const [error, setError] = useState('');
  const [targetRole, setTargetRole] = useState('');
  const [marketInsights, setMarketInsights] = useState(null);
  const [feedbackAnalysis, setFeedbackAnalysis] = useState(null);
  const [salaryInsights, setSalaryInsights] = useState(null);

  const handleAnalyze = async () => {
    setLoading('analyze');
    setError('');
    try {
      const data = await api.advisorAnalyze();
      if (data.error) setError(data.error);
      else setAnalysis(data);
    } catch (err) {
      setError(err?.response?.data?.error || 'Analysis failed');
    } finally {
      setLoading('');
    }
  };

  const handleRoadmap = async () => {
    if (!targetRole.trim()) return;
    setLoading('roadmap');
    setError('');
    try {
      const data = await api.advisorSkillsRoadmap(targetRole);
      if (data.error) setError(data.error);
      else setRoadmap(data);
    } catch (err) {
      setError(err?.response?.data?.error || 'Roadmap generation failed');
    } finally {
      setLoading('');
    }
  };

  const handleMarketInsights = async () => {
    setLoading('market');
    setError('');
    try {
      const resp = await api.getMarketInsights();
      setMarketInsights(resp);
    } catch (err) {
      setError(err?.response?.data?.error || 'Market insights failed');
    } finally {
      setLoading('');
    }
  };

  const handleFeedbackAnalysis = async () => {
    setLoading('feedback');
    setError('');
    try {
      const resp = await api.getFeedbackAnalysis();
      setFeedbackAnalysis(resp);
    } catch (err) {
      setError(err?.response?.data?.error || 'Feedback analysis failed');
    } finally {
      setLoading('');
    }
  };

  const handleSalaryInsights = async () => {
    setLoading('salary');
    setError('');
    try {
      const data = await api.advisorSalaryInsights();
      setSalaryInsights(data);
    } catch (err) {
      setError(err?.response?.data?.error || 'Salary insights failed');
    } finally {
      setLoading('');
    }
  };

  const handleRoles = async () => {
    setLoading('roles');
    setError('');
    try {
      const data = await api.advisorRoleRecommendations();
      if (data.error) setError(data.error);
      else setRoles(data);
    } catch (err) {
      setError(err?.response?.data?.error || 'Recommendations failed');
    } finally {
      setLoading('');
    }
  };

  return (
    <div className="advisor-container">
      {/* Action buttons */}
      <div className="advisor-actions">
        <button className="btn-search" onClick={handleAnalyze} disabled={!!loading}>
          {loading === 'analyze' ? 'Analyzing...' : 'Career Analysis'}
        </button>
        <button className="btn-search btn-orange" onClick={handleRoles} disabled={!!loading}>
          {loading === 'roles' ? 'Generating...' : 'Role Recommendations'}
        </button>
        <button className="btn-search" onClick={handleMarketInsights} disabled={!!loading} style={{ background: '#5c6bc0' }}>
          {loading === 'market' ? 'Loading...' : 'Market Insights'}
        </button>
        <button className="btn-search" onClick={handleFeedbackAnalysis} disabled={!!loading} style={{ background: '#00897b' }}>
          {loading === 'feedback' ? 'Loading...' : "What's Working"}
        </button>
        <button className="btn-search" onClick={handleSalaryInsights} disabled={!!loading} style={{ background: '#e65100' }}>
          {loading === 'salary' ? 'Loading...' : 'Salary Intelligence'}
        </button>
        <div className="advisor-target-role">
          <div>
            <label>Target Role</label>
            <input
              type="text"
              value={targetRole}
              onChange={e => setTargetRole(e.target.value)}
              placeholder="e.g., VP of Engineering"
            />
          </div>
          <button className="btn-search btn-green" onClick={handleRoadmap} disabled={!!loading || !targetRole.trim()}>
            {loading === 'roadmap' ? 'Building...' : 'Skills Roadmap'}
          </button>
        </div>
        {loading && <div className="agent-spinner" />}
      </div>

      {error && <div className="text-error">{error}</div>}

      {/* Career Analysis */}
      {analysis && (
        <div className="postings-section">
          <h3>Career Analysis</h3>

          {analysis.career_trajectory && (
            <div className="advisor-trajectory">
              <div className="advisor-trajectory-badges">
                <span className="status-badge status-applied">{analysis.career_trajectory.current_phase}</span>
                <span className="status-badge status-bookmarked">{analysis.career_trajectory.momentum}</span>
              </div>
              <p>{analysis.career_trajectory.summary}</p>
            </div>
          )}

          <div className="advisor-grid">
            {analysis.strengths?.length > 0 && (
              <div className="advisor-strengths">
                <h4>Strengths</h4>
                {analysis.strengths.map((s, i) => (
                  <div key={i} className="advisor-strength-item">
                    <strong className="item-title">{s.area}</strong>
                    <div className="item-detail">{s.evidence}</div>
                    <div className="item-action">{s.leverage}</div>
                  </div>
                ))}
              </div>
            )}
            {analysis.growth_areas?.length > 0 && (
              <div className="advisor-growth">
                <h4>Growth Areas</h4>
                {analysis.growth_areas.map((g, i) => (
                  <div key={i} className="advisor-growth-item">
                    <div className="item-header">
                      <strong className="item-title">{g.area}</strong>
                      <span className={`advisor-priority-badge ${g.priority}`}>{g.priority}</span>
                    </div>
                    <div className="item-detail">{g.action}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {analysis.market_alignment && (
            <div className="advisor-market">
              <h4>Market Alignment: {analysis.market_alignment.score}/100</h4>
              <div className="advisor-market-cols">
                {analysis.market_alignment.trending_skills?.length > 0 && (
                  <div className="advisor-market-col">
                    <span>Trending Skills You Have:</span>
                    <div className="skills-tags">
                      {analysis.market_alignment.trending_skills.map((s, i) => (
                        <span className="skill-tag overlap" key={i}>{s}</span>
                      ))}
                    </div>
                  </div>
                )}
                {analysis.market_alignment.emerging_gaps?.length > 0 && (
                  <div className="advisor-market-col">
                    <span>Emerging Gaps:</span>
                    <div className="skills-tags">
                      {analysis.market_alignment.emerging_gaps.map((s, i) => (
                        <span className="skill-tag missing" key={i}>{s}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {analysis.recommended_learning?.length > 0 && (
            <div className="advisor-learning">
              <h4>Recommended Learning</h4>
              <div className="advisor-learning-grid">
                {analysis.recommended_learning.map((l, i) => (
                  <div key={i} className="advisor-learning-card">
                    <div className="card-topic">{l.topic}</div>
                    <div className="card-why">{l.why}</div>
                    <span className="status-badge status-tailored">{l.format}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Role Recommendations */}
      {roles?.recommendations?.length > 0 && (
        <div className="postings-section">
          <h3>Recommended Next Roles</h3>
          {roles.recommendations.map((r, i) => (
            <div key={i} className="advisor-role-card">
              <div className="role-header">
                <div>
                  <div className="role-title">{r.title}</div>
                  <div className="role-industry">{r.industry} {r.salary_range && `\u2022 ${r.salary_range}`}</div>
                </div>
                <div className="role-fit">{r.fit_score}</div>
              </div>
              <div className="role-reasoning">{r.reasoning}</div>
              {r.key_requirements?.length > 0 && (
                <div className="skills-tags">
                  {r.key_requirements.map((req, j) => (
                    <span className="skill-tag overlap" key={j}>{req}</span>
                  ))}
                </div>
              )}
              {r.gaps_to_address?.length > 0 && (
                <div className="skills-tags">
                  {r.gaps_to_address.map((gap, j) => (
                    <span className="skill-tag missing" key={j}>{gap}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Skills Roadmap */}
      {roadmap && (
        <div className="postings-section">
          <h3>
            Skills Roadmap: {roadmap.target_role}
            <span style={{ fontSize: 14, fontWeight: 400, color: '#667eea', marginLeft: 12 }}>
              Readiness: {roadmap.current_readiness}% &bull; ~{roadmap.timeline_months} months
            </span>
          </h3>

          {roadmap.quick_wins?.length > 0 && (
            <div className="advisor-quick-wins">
              <h4>Quick Wins (This Week):</h4>
              <ul>
                {roadmap.quick_wins.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}

          {roadmap.phases?.map((phase, i) => (
            <div key={i} className="advisor-roadmap-phase">
              <div className="phase-header">
                <span className="phase-name">Phase {phase.phase}: {phase.name}</span>
                <span className="phase-duration">{phase.duration_weeks} weeks</span>
              </div>
              {phase.skills?.length > 0 && (
                <div className="skills-tags">
                  {phase.skills.map((s, j) => (
                    <span className="skill-tag overlap" key={j}>{s}</span>
                  ))}
                </div>
              )}
              {phase.resources?.length > 0 && (
                <ul style={{ margin: '4px 0', paddingLeft: 20, fontSize: 13, color: '#555' }}>
                  {phase.resources.map((r, j) => <li key={j}>{r}</li>)}
                </ul>
              )}
              {phase.milestone && (
                <div className="phase-milestone">Milestone: {phase.milestone}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Market Insights */}
      {marketInsights && (
        <div className="postings-section">
          <h3>Market Insights ({marketInsights.total_postings_analyzed} postings analyzed)</h3>
          {marketInsights.most_demanded_skills?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4>Most Demanded Skills (You're Missing)</h4>
              <div className="skills-tags">
                {marketInsights.most_demanded_skills.map((s, i) => (
                  <span className="skill-tag missing" key={i}>
                    {s.skill} ({s.count})
                  </span>
                ))}
              </div>
            </div>
          )}
          {marketInsights.skills_you_have?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4>Skills You Have (In Demand)</h4>
              <div className="skills-tags">
                {marketInsights.skills_you_have.map((s, i) => (
                  <span className="skill-tag overlap" key={i}>
                    {s.skill} ({s.count})
                  </span>
                ))}
              </div>
            </div>
          )}
          {marketInsights.skills_gap?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4>Skills Gap</h4>
              <div className="skills-tags">
                {marketInsights.skills_gap.map((s, i) => (
                  <span className="skill-tag missing" key={i}>{s}</span>
                ))}
              </div>
            </div>
          )}
          {marketInsights.recommendations?.length > 0 && (
            <div>
              <h4>Recommendations</h4>
              <ul>{marketInsights.recommendations.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          )}
        </div>
      )}

      {/* Feedback Analysis */}
      {feedbackAnalysis && (
        <div className="postings-section">
          <h3>Application Feedback Analysis ({feedbackAnalysis.total_applications} applications)</h3>
          {feedbackAnalysis.outcome_distribution && (
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
              {Object.entries(feedbackAnalysis.outcome_distribution).map(([outcome, count]) => (
                <div key={outcome} style={{
                  padding: '12px 20px', borderRadius: 8, textAlign: 'center', minWidth: 80,
                  background: outcome === 'offer' ? '#e8f5e9' : outcome === 'interview' ? '#e3f2fd' :
                    outcome === 'rejected' ? '#fbe9e7' : '#f5f5f5',
                }}>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>{count}</div>
                  <div style={{ fontSize: 12, textTransform: 'capitalize' }}>{outcome}</div>
                </div>
              ))}
            </div>
          )}
          {feedbackAnalysis.success_patterns?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4>Success Patterns</h4>
              <ul>{feedbackAnalysis.success_patterns.map((p, i) => <li key={i}>{typeof p === 'string' ? p : JSON.stringify(p)}</li>)}</ul>
            </div>
          )}
          {feedbackAnalysis.recommendations?.length > 0 && (
            <div>
              <h4>Recommendations</h4>
              <ul>{feedbackAnalysis.recommendations.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          )}
        </div>
      )}

      {/* Salary Intelligence */}
      {salaryInsights && (
        <div className="postings-section">
          <h3>Salary Intelligence</h3>
          {!salaryInsights.salary_data_available ? (
            <p style={{ color: '#6b7280' }}>{salaryInsights.message}</p>
          ) : (
            <>
              <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
                <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: 12, minWidth: 140, textAlign: 'center' }}>
                  <div style={{ fontSize: 12, color: '#9a3412', fontWeight: 600 }}>Median</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#c2410c' }}>${salaryInsights.overall?.median?.toLocaleString()}</div>
                </div>
                <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: 12, minWidth: 140, textAlign: 'center' }}>
                  <div style={{ fontSize: 12, color: '#9a3412', fontWeight: 600 }}>Range</div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: '#c2410c' }}>
                    ${salaryInsights.overall?.min?.toLocaleString()} - ${salaryInsights.overall?.max?.toLocaleString()}
                  </div>
                </div>
                <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: 12, minWidth: 140, textAlign: 'center' }}>
                  <div style={{ fontSize: 12, color: '#9a3412', fontWeight: 600 }}>Data Points</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#c2410c' }}>{salaryInsights.postings_with_salary}</div>
                </div>
              </div>

              {salaryInsights.by_role?.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <h4 style={{ fontSize: 14, marginBottom: 8 }}>By Role</h4>
                  {salaryInsights.by_role.map((r, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ width: 100, fontSize: 13, textTransform: 'capitalize', fontWeight: 500 }}>{r.role}</span>
                      <span style={{ fontSize: 13, color: '#555' }}>
                        ${r.min?.toLocaleString()} - ${r.max?.toLocaleString()} (n={r.count})
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {salaryInsights.top_paying?.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <h4 style={{ fontSize: 14, marginBottom: 8 }}>Top Paying Postings</h4>
                  {salaryInsights.top_paying.map((p, i) => (
                    <div key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                      <strong>{p.title}</strong> @ {p.company} — {p.salary_range} (score: {Math.round(p.match_score || 0)})
                    </div>
                  ))}
                </div>
              )}

              {salaryInsights.negotiation_points?.length > 0 && (
                <div style={{ background: '#fef3c7', borderRadius: 8, padding: 12 }}>
                  <h4 style={{ fontSize: 14, color: '#92400e', marginBottom: 8 }}>Negotiation Talking Points</h4>
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {salaryInsights.negotiation_points.map((pt, i) => (
                      <li key={i} style={{ fontSize: 13, color: '#78350f', marginBottom: 4 }}>{pt}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {!analysis && !roles && !roadmap && !marketInsights && !feedbackAnalysis && !salaryInsights && !loading && (
        <div className="empty-state">
          <p>Get AI-powered career insights, role recommendations, and skills roadmaps.</p>
          <p className="text-md text-muted">All analysis runs on local RTX 5090 ($0.00)</p>
        </div>
      )}
    </div>
  );
}

export default CareerAdvisor;
