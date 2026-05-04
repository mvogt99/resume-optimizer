import React, { useState, useEffect } from 'react';
import api from '../services/api';

function AnalyticsDashboard() {
  const [overview, setOverview] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [skills, setSkills] = useState([]);
  const [agents, setAgents] = useState([]);
  const [feedbackDist, setFeedbackDist] = useState([]);
  const [scoreTrends, setScoreTrends] = useState(null);
  const [feedbackInsights, setFeedbackInsights] = useState(null);
  const [feedbackAnalysis, setFeedbackAnalysis] = useState(null);
  const [sessionInsights, setSessionInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const [ov, fn, sk, ag, fb, st, fi, fa, si] = await Promise.all([
          api.getAnalyticsOverview(),
          api.getAnalyticsFunnel(),
          api.getSkillsDemand(),
          api.getAgentUsage(),
          api.getFeedbackSummary(),
          api.getScoreTrends().catch(() => ({ data: null })),
          api.getFeedbackInsights().catch(() => ({ data: null })),
          api.getFeedbackAnalysis().catch(() => null),
          api.getSessionInsights().catch(() => null),
        ]);
        setOverview(ov.data);
        setFunnel(fn.data);
        setSkills(sk.data.skills || []);
        setAgents(ag.data.agents || []);
        setFeedbackDist(fb.data.distribution || []);
        setScoreTrends(st.data);
        setFeedbackInsights(fi.data);
        setFeedbackAnalysis(fa);
        setSessionInsights(si);
      } catch (err) {
        setError('Failed to load analytics. ' + (err.response?.data?.error || err.message));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}>Loading analytics...</div>;
  if (error) return <div className="alert alert-danger">{error}</div>;

  const cardStyle = {
    background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8,
    padding: 16, textAlign: 'center', minWidth: 140,
  };
  const labelStyle = { fontSize: 12, color: '#6b7280', textTransform: 'uppercase', fontWeight: 600 };
  const valueStyle = { fontSize: 28, fontWeight: 700, margin: '8px 0 0' };

  const maxSkill = skills.length > 0 ? skills[0].demand_count : 1;

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>Analytics Dashboard</h2>

      {/* Overview Cards */}
      {overview && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 24 }}>
          <div style={cardStyle}>
            <div style={labelStyle}>Total Postings</div>
            <div style={valueStyle}>{overview.total_postings}</div>
          </div>
          <div style={cardStyle}>
            <div style={labelStyle}>Applications</div>
            <div style={valueStyle}>{overview.total_applications}</div>
          </div>
          <div style={cardStyle}>
            <div style={labelStyle}>Avg Match Score</div>
            <div style={valueStyle}>{overview.average_match_score}%</div>
          </div>
          <div style={cardStyle}>
            <div style={labelStyle}>Response Rate</div>
            <div style={valueStyle}>{overview.response_rate}%</div>
          </div>
          <div style={cardStyle}>
            <div style={labelStyle}>Campaigns</div>
            <div style={valueStyle}>{overview.active_campaigns}</div>
          </div>
          <div style={cardStyle}>
            <div style={labelStyle}>Agent Runs</div>
            <div style={valueStyle}>{overview.agent_runs}</div>
          </div>
        </div>
      )}

      {/* Pipeline Funnel */}
      {funnel && funnel.stages && (
        <div style={{ marginBottom: 24 }}>
          <h3>Pipeline Funnel</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {Object.entries(funnel.stages).map(([stage, count]) => {
              const maxCount = Math.max(...Object.values(funnel.stages), 1);
              const pct = (count / maxCount) * 100;
              return (
                <div key={stage} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ width: 100, fontSize: 13, textTransform: 'capitalize', textAlign: 'right' }}>{stage}</div>
                  <div style={{ flex: 1, background: '#f3f4f6', borderRadius: 4, height: 24, overflow: 'hidden' }}>
                    <div style={{
                      width: `${pct}%`, background: '#3b82f6', height: '100%', borderRadius: 4,
                      transition: 'width 0.5s', minWidth: count > 0 ? 20 : 0,
                    }} />
                  </div>
                  <div style={{ width: 40, fontSize: 13, fontWeight: 600 }}>{count}</div>
                </div>
              );
            })}
          </div>
          {funnel.conversions && funnel.conversions.length > 0 && (
            <div style={{ marginTop: 12, fontSize: 13, color: '#6b7280' }}>
              {funnel.conversions.filter(c => c.from_count > 0).map((c, i) => (
                <span key={i} style={{ marginRight: 16 }}>
                  {c.from} → {c.to}: {c.conversion_rate}%
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Skills Demand */}
      {skills.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3>Top Skills in Demand</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {skills.slice(0, 15).map((s, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 150, fontSize: 13, textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {s.skill}
                </div>
                <div style={{ flex: 1, background: '#f3f4f6', borderRadius: 4, height: 20, overflow: 'hidden' }}>
                  <div style={{
                    width: `${(s.demand_count / maxSkill) * 100}%`,
                    background: '#10b981', height: '100%', borderRadius: 4,
                    minWidth: s.demand_count > 0 ? 16 : 0,
                  }} />
                </div>
                <div style={{ width: 30, fontSize: 12, fontWeight: 600 }}>{s.demand_count}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Agent Usage */}
      {agents.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3>Agent Usage</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                <th style={{ textAlign: 'left', padding: 8 }}>Agent</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Runs</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Success</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Failed</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Rate</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Avg Duration</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: 8 }}>{a.agent_type}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{a.total_runs}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{a.success_count}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{a.failed_count}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{a.success_rate}%</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{a.avg_duration_ms ? `${(a.avg_duration_ms / 1000).toFixed(1)}s` : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Feedback Distribution */}
      {feedbackDist.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3>Feedback Summary</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 }}>
            {feedbackDist.map((f, i) => {
              const colors = { interview: '#3b82f6', offer: '#10b981', rejected: '#ef4444', ghosted: '#f59e0b', no_response: '#6b7280', withdrawn: '#8b5cf6' };
              return (
                <div key={i} style={{
                  ...cardStyle, borderLeft: `4px solid ${colors[f.outcome] || '#d1d5db'}`,
                }}>
                  <div style={{ fontSize: 13, textTransform: 'capitalize', color: '#374151' }}>{f.outcome}</div>
                  <div style={{ fontSize: 24, fontWeight: 700 }}>{f.count}</div>
                  <div style={{ fontSize: 12, color: '#6b7280' }}>{f.percentage}%</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Score Trends */}
      {scoreTrends && scoreTrends.periods && scoreTrends.periods.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3>Score Trends</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {scoreTrends.periods.map((p, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 80, fontSize: 13, textAlign: 'right' }}>{p.period}</div>
                <div style={{ flex: 1, background: '#f3f4f6', borderRadius: 4, height: 20, overflow: 'hidden' }}>
                  <div style={{
                    width: `${p.avg_score}%`, background: '#6366f1', height: '100%', borderRadius: 4,
                    minWidth: p.avg_score > 0 ? 16 : 0,
                  }} />
                </div>
                <div style={{ width: 50, fontSize: 12, fontWeight: 600 }}>{p.avg_score}%</div>
                <div style={{ width: 30, fontSize: 12, color: '#6b7280' }}>n={p.count}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feedback Insights */}
      {feedbackInsights && (
        <div style={{ marginBottom: 24 }}>
          <h3>Feedback Insights</h3>
          {feedbackInsights.top_rejection_reasons && feedbackInsights.top_rejection_reasons.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <strong style={{ fontSize: 13 }}>Top Rejection Reasons:</strong>
              <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
                {feedbackInsights.top_rejection_reasons.map((r, i) => (
                  <li key={i} style={{ fontSize: 13 }}>{r.reason} ({r.count})</li>
                ))}
              </ul>
            </div>
          )}
          {feedbackInsights.improvement_suggestions && feedbackInsights.improvement_suggestions.length > 0 && (
            <div>
              <strong style={{ fontSize: 13 }}>Improvement Suggestions:</strong>
              <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
                {feedbackInsights.improvement_suggestions.map((s, i) => (
                  <li key={i} style={{ fontSize: 13 }}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Feedback Analysis — What's Working / What to Improve (Phase 17.05) */}
      {feedbackAnalysis && feedbackAnalysis.total_analyzed > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3>What's Working / What to Improve</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            {/* Strengths */}
            <div style={{ ...cardStyle, textAlign: 'left', borderLeft: '4px solid #10b981' }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#065f46', marginBottom: 8 }}>
                Strengths in Demand
              </div>
              {feedbackAnalysis.skills_correlated_with_success?.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {feedbackAnalysis.skills_correlated_with_success.slice(0, 8).map((s, i) => (
                    <span key={i} style={{
                      background: '#d1fae5', color: '#065f46', padding: '3px 10px',
                      borderRadius: 12, fontSize: 12, fontWeight: 500,
                    }}>
                      {s.skill} ({s.success_count})
                    </span>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 13, color: '#6b7280' }}>Record interview/offer outcomes to see patterns</div>
              )}
            </div>

            {/* Weaknesses */}
            <div style={{ ...cardStyle, textAlign: 'left', borderLeft: '4px solid #ef4444' }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#991b1b', marginBottom: 8 }}>
                Skills to Prioritize
              </div>
              {feedbackAnalysis.skills_correlated_with_rejection?.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {feedbackAnalysis.skills_correlated_with_rejection.slice(0, 8).map((s, i) => (
                    <span key={i} style={{
                      background: '#fee2e2', color: '#991b1b', padding: '3px 10px',
                      borderRadius: 12, fontSize: 12, fontWeight: 500,
                    }}>
                      {s.skill} ({s.rejection_count}x rejected)
                    </span>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 13, color: '#6b7280' }}>No rejection patterns detected yet</div>
              )}
            </div>
          </div>

          {/* Score threshold insight */}
          {feedbackAnalysis.score_vs_outcome && Object.keys(feedbackAnalysis.score_vs_outcome).length > 0 && (
            <div style={{ ...cardStyle, textAlign: 'left', marginBottom: 12 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Score vs. Outcome</div>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {Object.entries(feedbackAnalysis.score_vs_outcome).map(([outcome, avgScore]) => {
                  const colors = { interview: '#3b82f6', offer: '#10b981', rejected: '#ef4444', ghosted: '#f59e0b' };
                  return (
                    <div key={outcome} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{
                        width: 10, height: 10, borderRadius: '50%',
                        background: colors[outcome] || '#6b7280',
                      }} />
                      <span style={{ fontSize: 13, textTransform: 'capitalize' }}>{outcome}:</span>
                      <span style={{ fontSize: 13, fontWeight: 600 }}>{avgScore}% avg</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Role performance */}
          {feedbackAnalysis.role_performance?.length > 0 && (
            <div style={{ ...cardStyle, textAlign: 'left', marginBottom: 12 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Role Performance</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {feedbackAnalysis.role_performance.slice(0, 5).map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 100, fontSize: 13, textTransform: 'capitalize', fontWeight: 500 }}>
                      {r.role}
                    </span>
                    <div style={{ flex: 1, background: '#f3f4f6', borderRadius: 4, height: 16, overflow: 'hidden' }}>
                      <div style={{
                        width: `${r.success_rate}%`, height: '100%', borderRadius: 4,
                        background: r.success_rate >= 50 ? '#10b981' : r.success_rate >= 25 ? '#f59e0b' : '#ef4444',
                        minWidth: r.success_rate > 0 ? 8 : 0,
                      }} />
                    </div>
                    <span style={{ width: 50, fontSize: 12, fontWeight: 600 }}>{r.success_rate}%</span>
                    <span style={{ fontSize: 11, color: '#6b7280' }}>n={r.total}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actionable insights */}
          {feedbackAnalysis.actionable_insights?.length > 0 && (
            <div style={{ ...cardStyle, textAlign: 'left', borderLeft: '4px solid #6366f1' }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#4338ca', marginBottom: 8 }}>
                Actionable Insights
              </div>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {feedbackAnalysis.actionable_insights.map((insight, i) => (
                  <li key={i} style={{ fontSize: 13, color: '#374151', marginBottom: 4 }}>{insight}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Session Optimization Insights (Phase 17.12) */}
      {sessionInsights && sessionInsights.total_sessions > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3>Optimization Performance by Role</h3>

          {/* Overall stats cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12, marginBottom: 16 }}>
            <div style={cardStyle}>
              <div style={labelStyle}>Sessions</div>
              <div style={valueStyle}>{sessionInsights.total_sessions}</div>
            </div>
            <div style={cardStyle}>
              <div style={labelStyle}>Avg Score</div>
              <div style={{ ...valueStyle, color: sessionInsights.avg_score >= 70 ? '#10b981' : sessionInsights.avg_score >= 50 ? '#f59e0b' : '#ef4444' }}>
                {sessionInsights.avg_score}%
              </div>
            </div>
            <div style={cardStyle}>
              <div style={labelStyle}>Best</div>
              <div style={{ ...valueStyle, color: '#10b981' }}>{sessionInsights.max_score}%</div>
            </div>
            <div style={cardStyle}>
              <div style={labelStyle}>Worst</div>
              <div style={{ ...valueStyle, color: '#ef4444' }}>{sessionInsights.min_score}%</div>
            </div>
          </div>

          {/* Score by role — bar chart */}
          {sessionInsights.avg_score_by_role?.length > 0 && (
            <div style={{ ...cardStyle, textAlign: 'left', marginBottom: 12 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Average Score by Role</div>
              {sessionInsights.avg_score_by_role.map((r, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ width: 90, fontSize: 13, textTransform: 'capitalize', fontWeight: 500 }}>{r.role}</span>
                  <div style={{ flex: 1, background: '#f3f4f6', borderRadius: 4, height: 20, overflow: 'hidden' }}>
                    <div style={{
                      width: `${r.avg_score}%`, height: '100%', borderRadius: 4,
                      background: r.avg_score >= 70 ? '#10b981' : r.avg_score >= 50 ? '#f59e0b' : '#ef4444',
                      minWidth: r.avg_score > 0 ? 8 : 0,
                    }} />
                  </div>
                  <span style={{ width: 45, fontSize: 12, fontWeight: 600 }}>{r.avg_score}%</span>
                  <span style={{ width: 35, fontSize: 11, color: '#6b7280' }}>n={r.count}</span>
                  {r.success_rate != null && (
                    <span style={{
                      fontSize: 11, padding: '1px 6px', borderRadius: 10,
                      background: r.success_rate >= 50 ? '#d1fae5' : '#fee2e2',
                      color: r.success_rate >= 50 ? '#065f46' : '#991b1b',
                    }}>
                      {r.success_rate}% win
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Score trend */}
          {sessionInsights.score_trend?.length > 0 && (
            <div style={{ ...cardStyle, textAlign: 'left', marginBottom: 12 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Score Trend (Monthly)</div>
              {sessionInsights.score_trend.map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ width: 70, fontSize: 12, textAlign: 'right', color: '#555' }}>{p.period}</span>
                  <div style={{ flex: 1, background: '#f3f4f6', borderRadius: 4, height: 16, overflow: 'hidden' }}>
                    <div style={{
                      width: `${p.avg_score}%`, height: '100%', borderRadius: 4,
                      background: '#6366f1', minWidth: p.avg_score > 0 ? 8 : 0,
                    }} />
                  </div>
                  <span style={{ width: 45, fontSize: 12, fontWeight: 600 }}>{p.avg_score}%</span>
                  <span style={{ width: 30, fontSize: 11, color: '#6b7280' }}>n={p.count}</span>
                </div>
              ))}
            </div>
          )}

          {/* Top keywords */}
          {sessionInsights.top_keywords?.length > 0 && (
            <div style={{ ...cardStyle, textAlign: 'left' }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Top Matching Keywords</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {sessionInsights.top_keywords.map((kw, i) => (
                  <span key={i} style={{
                    background: '#eef2ff', color: '#4338ca', padding: '3px 10px',
                    borderRadius: 12, fontSize: 12, fontWeight: 500,
                  }}>
                    {kw.keyword} ({kw.count})
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {(!overview || overview.total_postings === 0) && (
        <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>
          <p>No data yet. Start using the Job Scout and Application Pipeline to see analytics here.</p>
        </div>
      )}
    </div>
  );
}

export default AnalyticsDashboard;
