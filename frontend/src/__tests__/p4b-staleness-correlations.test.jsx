/**
 * P4-B tests: ProfileStaleWarning banner (ResumeTailor) + CorrelationDashboard.
 */
import { render, screen, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  default: {
    tailorResume: vi.fn(),
    getTailoredResume: vi.fn(),
    getTemplates: vi.fn(),
    getCorrelations: vi.fn(),
    getPipeline: vi.fn(),
    getPipelineAnalytics: vi.fn(),
    getPipelineReminders: vi.fn(),
  },
}));

import ResumeTailor from '../components/ResumeTailor';
import CorrelationDashboard from '../components/CorrelationDashboard';
import api from '../services/api';

// ---------------------------------------------------------------------------
// ProfileStaleWarning — via ResumeTailor
// ---------------------------------------------------------------------------

describe('ProfileStaleWarning', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getTailoredResume.mockRejectedValue(new Error('none'));
    api.getTemplates.mockResolvedValue({ data: { templates: [] } });
  });

  test('stale warning is shown when profile_stale=true', async () => {
    api.tailorResume.mockResolvedValue({
      profile_stale: true,
      stale_reason: 'profile hash changed',
      optimized_text: 'Resume text',
      ats_score: 72,
      score_breakdown: {},
    });

    await act(async () => {
      render(<ResumeTailor postingId="p1" />);
    });

    const btn = screen.getByText(/tailor resume/i);
    await act(async () => { btn.click(); });

    await waitFor(() => {
      expect(screen.getByTestId('stale-warning')).toBeInTheDocument();
    });
    expect(screen.getByTestId('stale-warning').textContent).toMatch(/profile may be outdated/i);
  });

  test('stale warning includes stale_reason text', async () => {
    api.tailorResume.mockResolvedValue({
      profile_stale: true,
      stale_reason: 'new projects detected',
      optimized_text: 'text',
      ats_score: 60,
      score_breakdown: {},
    });

    await act(async () => {
      render(<ResumeTailor postingId="p1" />);
    });

    await act(async () => { screen.getByText(/tailor resume/i).click(); });

    await waitFor(() => {
      expect(screen.getByTestId('stale-warning').textContent).toMatch(/new projects detected/);
    });
  });

  test('stale warning is hidden when profile_stale=false', async () => {
    api.tailorResume.mockResolvedValue({
      profile_stale: false,
      stale_reason: '',
      optimized_text: 'text',
      ats_score: 80,
      score_breakdown: {},
    });

    await act(async () => {
      render(<ResumeTailor postingId="p1" />);
    });

    await act(async () => { screen.getByText(/tailor resume/i).click(); });

    await waitFor(() => {
      expect(screen.queryByTestId('stale-warning')).not.toBeInTheDocument();
    });
  });

  test('"Build Now" link points to /deep-profile', async () => {
    api.tailorResume.mockResolvedValue({
      profile_stale: true,
      stale_reason: 'stale',
      optimized_text: 'text',
      ats_score: 55,
      score_breakdown: {},
    });

    await act(async () => {
      render(<ResumeTailor postingId="p1" />);
    });

    await act(async () => { screen.getByText(/tailor resume/i).click(); });

    await waitFor(() => {
      expect(screen.getByTestId('stale-build-now')).toBeInTheDocument();
    });
    expect(screen.getByTestId('stale-build-now')).toHaveAttribute('href', '/deep-profile');
  });
});

// ---------------------------------------------------------------------------
// CorrelationDashboard
// ---------------------------------------------------------------------------

describe('CorrelationDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('shows loading state while fetching', async () => {
    // Never resolve so we stay in loading
    api.getCorrelations.mockReturnValue(new Promise(() => {}));
    render(<CorrelationDashboard />);
    expect(screen.getByTestId('correlations-loading')).toBeInTheDocument();
  });

  test('renders stats from API response', async () => {
    api.getCorrelations.mockResolvedValue({
      callback_rate: 33.3,
      total_applications: 12,
      avg_ats_callback: 78.5,
      avg_ats_rejected: 55.2,
    });

    await act(async () => {
      render(<CorrelationDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByTestId('correlations-dashboard')).toBeInTheDocument();
    });
    expect(screen.getByTestId('callback-rate').textContent).toContain('33.3');
    expect(screen.getByTestId('total-applications').textContent).toBe('12');
    expect(screen.getByTestId('avg-ats-callback').textContent).toBe('79');
    expect(screen.getByTestId('avg-ats-rejected').textContent).toBe('55');
  });

  test('shows empty state when total_applications is 0', async () => {
    api.getCorrelations.mockResolvedValue({
      callback_rate: 0.0,
      total_applications: 0,
      avg_ats_callback: null,
      avg_ats_rejected: null,
    });

    await act(async () => {
      render(<CorrelationDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByTestId('correlations-empty')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('correlations-dashboard')).not.toBeInTheDocument();
  });

  test('shows empty state on API error', async () => {
    api.getCorrelations.mockRejectedValue(new Error('network error'));

    await act(async () => {
      render(<CorrelationDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByTestId('correlations-empty')).toBeInTheDocument();
    });
  });

  test('omits avg_ats rows when values are null', async () => {
    api.getCorrelations.mockResolvedValue({
      callback_rate: 50.0,
      total_applications: 4,
      avg_ats_callback: null,
      avg_ats_rejected: null,
    });

    await act(async () => {
      render(<CorrelationDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByTestId('correlations-dashboard')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('avg-ats-callback')).not.toBeInTheDocument();
    expect(screen.queryByTestId('avg-ats-rejected')).not.toBeInTheDocument();
  });
});
