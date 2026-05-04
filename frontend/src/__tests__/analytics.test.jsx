import { render, screen, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  default: {
    getAnalyticsOverview: vi.fn(),
    getAnalyticsFunnel: vi.fn(),
    getSkillsDemand: vi.fn(),
    getAgentUsage: vi.fn(),
    getFeedbackSummary: vi.fn(),
    getScoreTrends: vi.fn(),
    getFeedbackInsights: vi.fn(),
    getFeedbackAnalysis: vi.fn(),
    getSessionInsights: vi.fn(),
  },
}));

import AnalyticsDashboard from '../components/AnalyticsDashboard';

const MOCK_OVERVIEW = {
  total_postings: 42,
  total_applications: 15,
  average_match_score: 78,
  response_rate: 33,
  active_campaigns: 3,
  agent_runs: 120,
};

const MOCK_FUNNEL = {
  stages: { discovered: 42, applied: 15, screening: 8, interview: 4, offer: 1 },
  conversions: [
    { from: 'discovered', to: 'applied', from_count: 42, to_count: 15, conversion_rate: 35.7 },
    { from: 'applied', to: 'screening', from_count: 15, to_count: 8, conversion_rate: 53.3 },
  ],
};

const MOCK_SKILLS = [
  { skill: 'Python', demand_count: 25 },
  { skill: 'Kubernetes', demand_count: 18 },
  { skill: 'AWS', demand_count: 14 },
];

const MOCK_AGENTS = [
  { agent_type: 'scout', total_runs: 50, success_count: 45, failed_count: 5, success_rate: 90, avg_duration_ms: 3200 },
  { agent_type: 'coach', total_runs: 20, success_count: 18, failed_count: 2, success_rate: 90, avg_duration_ms: 5100 },
];

const MOCK_FEEDBACK = [
  { outcome: 'interview', count: 4, percentage: 26.7 },
  { outcome: 'rejected', count: 6, percentage: 40.0 },
  { outcome: 'ghosted', count: 5, percentage: 33.3 },
];

// ---------------------------------------------------------------------------
// AnalyticsDashboard Tests
// ---------------------------------------------------------------------------
describe('AnalyticsDashboard', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const api = (await import('../services/api')).default;
    api.getAnalyticsOverview.mockResolvedValue({ data: MOCK_OVERVIEW });
    api.getAnalyticsFunnel.mockResolvedValue({ data: MOCK_FUNNEL });
    api.getSkillsDemand.mockResolvedValue({ data: { skills: MOCK_SKILLS } });
    api.getAgentUsage.mockResolvedValue({ data: { agents: MOCK_AGENTS } });
    api.getFeedbackSummary.mockResolvedValue({ data: { distribution: MOCK_FEEDBACK } });
    api.getScoreTrends.mockResolvedValue({ data: { periods: [{ period: '2026-W10', avg_score: 72, count: 8 }] } });
    api.getFeedbackInsights.mockResolvedValue({ data: { top_rejection_reasons: [{ reason: 'Overqualified', count: 3 }], improvement_suggestions: ['Target mid-level roles'] } });
    api.getSessionInsights.mockResolvedValue({
      total_sessions: 8, avg_score: 72.5, max_score: 92, min_score: 45,
      avg_score_by_role: [
        { role: 'engineer', avg_score: 78, count: 5, success_rate: 60 },
        { role: 'architect', avg_score: 85, count: 3, success_rate: null },
      ],
      score_trend: [{ period: '2026-02', avg_score: 68, count: 3 }, { period: '2026-03', avg_score: 77, count: 5 }],
      best_resume_per_role: [{ role: 'engineer', resume_version_id: 1, score: 92 }],
      top_keywords: [{ keyword: 'python', count: 7 }, { keyword: 'kubernetes', count: 4 }],
    });
    api.getFeedbackAnalysis.mockResolvedValue({
      total_analyzed: 5,
      skills_correlated_with_rejection: [{ skill: 'docker', rejection_count: 3 }, { skill: 'kubernetes', rejection_count: 2 }],
      skills_correlated_with_success: [{ skill: 'python', success_count: 4 }],
      score_vs_outcome: { interview: 82, rejected: 58 },
      role_performance: [{ role: 'engineer', total: 4, positive: 2, negative: 2, success_rate: 50 }],
      actionable_insights: ['Skills most correlated with rejections: docker, kubernetes'],
    });
  });

  test('renders loading state initially', async () => {
    const api = (await import('../services/api')).default;
    // Use never-resolving promises so the component stays in loading state
    api.getAnalyticsOverview.mockReturnValue(new Promise(() => {}));
    api.getAnalyticsFunnel.mockReturnValue(new Promise(() => {}));
    api.getSkillsDemand.mockReturnValue(new Promise(() => {}));
    api.getAgentUsage.mockReturnValue(new Promise(() => {}));
    api.getFeedbackSummary.mockReturnValue(new Promise(() => {}));
    api.getScoreTrends.mockReturnValue(new Promise(() => {}));
    api.getFeedbackInsights.mockReturnValue(new Promise(() => {}));
    api.getFeedbackAnalysis.mockReturnValue(new Promise(() => {}));
    api.getSessionInsights.mockReturnValue(new Promise(() => {}));
    render(<AnalyticsDashboard />);
    expect(screen.getByText(/loading analytics/i)).toBeTruthy();
  });

  test('renders overview cards with data', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      // '42' appears in overview cards AND funnel, so use getAllByText
      expect(screen.getAllByText('42').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('15').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('78%').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('33%')).toBeTruthy();
    });
  });

  test('renders overview card labels', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Total Postings')).toBeTruthy();
      expect(screen.getByText('Applications')).toBeTruthy();
      expect(screen.getByText('Avg Match Score')).toBeTruthy();
      expect(screen.getByText('Response Rate')).toBeTruthy();
      expect(screen.getByText('Campaigns')).toBeTruthy();
      expect(screen.getByText('Agent Runs')).toBeTruthy();
    });
  });

  test('renders pipeline funnel stages', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('discovered')).toBeTruthy();
      // 'applied' and 'interview' appear in both funnel and feedback sections
      expect(screen.getAllByText('applied').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('interview').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('offer')).toBeTruthy();
    });
  });

  test('renders funnel conversion rates', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText(/35.7%/)).toBeTruthy();
      expect(screen.getByText(/53.3%/)).toBeTruthy();
    });
  });

  test('renders skills demand bar chart', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Python')).toBeTruthy();
      expect(screen.getByText('Kubernetes')).toBeTruthy();
      expect(screen.getByText('AWS')).toBeTruthy();
      expect(screen.getByText('25')).toBeTruthy();
      // '18' may appear in agent table too (success_count)
      expect(screen.getAllByText('18').length).toBeGreaterThanOrEqual(1);
    });
  });

  test('renders agent usage table', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('scout')).toBeTruthy();
      expect(screen.getByText('coach')).toBeTruthy();
      expect(screen.getByText('50')).toBeTruthy();
      // Both agents have 90% success rate
      expect(screen.getAllByText('90%').length).toBe(2);
    });
  });

  test('renders feedback distribution', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      // 'interview' appears in both funnel and feedback — use getAllByText
      expect(screen.getAllByText('interview').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('rejected')).toBeTruthy();
      expect(screen.getByText('ghosted')).toBeTruthy();
      expect(screen.getByText('26.7%')).toBeTruthy();
    });
  });

  test('renders error state on API failure', async () => {
    const api = (await import('../services/api')).default;
    api.getAnalyticsOverview.mockRejectedValue(new Error('Network error'));
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText(/failed to load analytics/i)).toBeTruthy();
    });
  });

  test('renders empty state when no data', async () => {
    const api = (await import('../services/api')).default;
    api.getAnalyticsOverview.mockResolvedValue({ data: { total_postings: 0, total_applications: 0, average_match_score: 0, response_rate: 0, active_campaigns: 0, agent_runs: 0 } });
    api.getAnalyticsFunnel.mockResolvedValue({ data: { stages: {} } });
    api.getSkillsDemand.mockResolvedValue({ data: { skills: [] } });
    api.getAgentUsage.mockResolvedValue({ data: { agents: [] } });
    api.getFeedbackSummary.mockResolvedValue({ data: { distribution: [] } });
    api.getScoreTrends.mockResolvedValue({ data: null });
    api.getFeedbackInsights.mockResolvedValue({ data: null });
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText(/no data yet/i)).toBeTruthy();
    });
  });

  test('calls all five analytics API endpoints', async () => {
    const api = (await import('../services/api')).default;
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(api.getAnalyticsOverview).toHaveBeenCalledTimes(1);
      expect(api.getAnalyticsFunnel).toHaveBeenCalledTimes(1);
      expect(api.getSkillsDemand).toHaveBeenCalledTimes(1);
      expect(api.getAgentUsage).toHaveBeenCalledTimes(1);
      expect(api.getFeedbackSummary).toHaveBeenCalledTimes(1);
    });
  });

  test('renders section headings', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Analytics Dashboard')).toBeTruthy();
      expect(screen.getByText('Pipeline Funnel')).toBeTruthy();
      expect(screen.getByText('Top Skills in Demand')).toBeTruthy();
      expect(screen.getByText('Agent Usage')).toBeTruthy();
      expect(screen.getByText('Feedback Summary')).toBeTruthy();
    });
  });

  test('renders score trends section', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Score Trends')).toBeTruthy();
      expect(screen.getByText('2026-W10')).toBeTruthy();
      expect(screen.getByText('72%')).toBeTruthy();
      expect(screen.getByText('n=8')).toBeTruthy();
    });
  });

  test('renders feedback insights section', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Feedback Insights')).toBeTruthy();
      expect(screen.getByText(/Overqualified/)).toBeTruthy();
      expect(screen.getByText(/Target mid-level roles/)).toBeTruthy();
    });
  });

  test('handles missing score trends gracefully', async () => {
    const api = (await import('../services/api')).default;
    api.getScoreTrends.mockRejectedValue(new Error('not found'));
    api.getFeedbackInsights.mockRejectedValue(new Error('not found'));
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Analytics Dashboard')).toBeTruthy();
      // Should still render without score trends
      expect(screen.queryByText('Score Trends')).toBeFalsy();
    });
  });

  test('calls score trends and feedback insights APIs', async () => {
    const api = (await import('../services/api')).default;
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(api.getScoreTrends).toHaveBeenCalledTimes(1);
      expect(api.getFeedbackInsights).toHaveBeenCalledTimes(1);
    });
  });

  // Phase 17.05: Feedback Analysis Panel
  test('renders feedback analysis panel with skill correlations', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText("What's Working / What to Improve")).toBeTruthy();
    });
    // Strengths
    expect(screen.getAllByText(/python/).length).toBeGreaterThanOrEqual(1);
    // Weaknesses
    expect(screen.getByText(/docker.*3x rejected/)).toBeTruthy();
    expect(screen.getByText(/kubernetes.*2x rejected/)).toBeTruthy();
  });

  test('renders score vs outcome data', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Score vs. Outcome')).toBeTruthy();
    });
    expect(screen.getByText(/82% avg/)).toBeTruthy();
    expect(screen.getByText(/58% avg/)).toBeTruthy();
  });

  test('renders role performance bars', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Role Performance')).toBeTruthy();
    });
    expect(screen.getAllByText('engineer').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('50%').length).toBeGreaterThanOrEqual(1);
  });

  test('renders actionable insights', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Actionable Insights')).toBeTruthy();
    });
    expect(screen.getByText(/Skills most correlated with rejections/)).toBeTruthy();
  });

  // Phase 17.12: Session insights panel
  test('renders session optimization performance panel', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Optimization Performance by Role')).toBeTruthy();
    });
    // Overall stats
    expect(screen.getByText('72.5%')).toBeTruthy();
    expect(screen.getByText('92%')).toBeTruthy();
  });

  test('renders score by role bars', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Average Score by Role')).toBeTruthy();
    });
    expect(screen.getAllByText('engineer').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('architect').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('60% win')).toBeTruthy(); // unique to session panel
  });

  test('renders top matching keywords', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Top Matching Keywords')).toBeTruthy();
    });
    expect(screen.getByText(/python.*7/)).toBeTruthy();
    expect(screen.getByText(/kubernetes.*4/)).toBeTruthy();
  });

  test('renders score trend', async () => {
    await act(async () => { render(<AnalyticsDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('Score Trend (Monthly)')).toBeTruthy();
    });
    expect(screen.getByText('2026-02')).toBeTruthy();
    expect(screen.getByText('2026-03')).toBeTruthy();
  });
});
