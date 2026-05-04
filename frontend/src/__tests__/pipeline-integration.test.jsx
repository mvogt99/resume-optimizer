/**
 * Pipeline integration tests — Prepare button (17.03) and Cover Letter dialog (17.04).
 * Separate file because ApplicationPipeline is vi.mock'd in agents.test.jsx,
 * and vi.doUnmock doesn't reliably clear cached module resolution within the same file.
 */
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  default: {
    getPipeline: vi.fn(),
    getPipelineAnalytics: vi.fn(),
    getPipelineReminders: vi.fn(),
    movePosting: vi.fn(),
    generateFollowup: vi.fn(),
    analyzePerformance: vi.fn(),
    generateCoverLetter: vi.fn(),
    coachStart: vi.fn(),
    recordFeedback: vi.fn(),
  },
}));

import ApplicationPipeline from '../components/ApplicationPipeline';
import api from '../services/api';

describe('ApplicationPipeline — Pipeline Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderPipeline = async (columns, props = {}) => {
    api.getPipeline.mockResolvedValue({ total: 1, columns });
    api.getPipelineAnalytics.mockResolvedValue({});
    api.getPipelineReminders.mockResolvedValue({ reminders: [] });

    let result;
    await act(async () => {
      result = render(<ApplicationPipeline {...props} />);
    });
    // Let useEffect + setState settle
    await act(async () => { await new Promise(r => setTimeout(r, 50)); });
    return result;
  };

  test('shows Prepare button for cards in phone_screen stage', async () => {
    const { container } = await renderPipeline(
      { phone_screen: [{ id: 'p1', title: 'Senior Dev', company: 'Acme', match_score: 85, status: 'phone_screen' }] },
      { onNavigateToCoach: vi.fn() },
    );
    expect(container.querySelector('.pipeline-card-title')?.textContent).toBe('Senior Dev');
    expect(container.querySelector('.btn-prep')).not.toBeNull();
    expect(container.querySelector('.btn-prep').textContent).toBe('Prepare');
  });

  test('shows Prepare button for cards in interview stage', async () => {
    const { container } = await renderPipeline(
      { interview: [{ id: 'p2', title: 'Tech Lead', company: 'BigCo', match_score: 90, status: 'interview' }] },
      { onNavigateToCoach: vi.fn() },
    );
    expect(container.querySelector('.btn-prep')).not.toBeNull();
  });

  test('Prepare button calls onNavigateToCoach with posting id', async () => {
    const navigateFn = vi.fn();
    const { container } = await renderPipeline(
      { interview: [{ id: 'p2', title: 'Tech Lead', company: 'BigCo', match_score: 90, status: 'interview' }] },
      { onNavigateToCoach: navigateFn },
    );
    fireEvent.click(container.querySelector('.btn-prep'));
    expect(navigateFn).toHaveBeenCalledWith('p2');
  });

  test('no Prepare button for non-interview stages', async () => {
    const { container } = await renderPipeline({
      discovered: [{ id: 'p3', title: 'Junior Dev', company: 'StartupCo', match_score: 50, status: 'discovered' }],
    });
    expect(container.querySelector('.pipeline-card-title')?.textContent).toBe('Junior Dev');
    expect(container.querySelector('.btn-prep')).toBeNull();
  });

  test('no Prepare button for bookmarked stage', async () => {
    const { container } = await renderPipeline({
      bookmarked: [{ id: 'b1', title: 'PM Role', company: 'X', match_score: 70, status: 'bookmarked' }],
    });
    expect(container.querySelector('.btn-prep')).toBeNull();
  });

  test('moving to applied shows cover letter confirmation dialog', async () => {
    const { container } = await renderPipeline({
      bookmarked: [{ id: 'p4', title: 'Eng Manager', company: 'Corp', match_score: 75, status: 'bookmarked' }],
    });

    const select = container.querySelector('.pipeline-card-actions select');
    expect(select).not.toBeNull();
    await act(async () => { fireEvent.change(select, { target: { value: 'applied' } }); });

    expect(screen.getByText('Moving to Applied')).toBeInTheDocument();
    expect(screen.getByText('Generate Cover Letter')).toBeInTheDocument();
    expect(screen.getByText('Skip')).toBeInTheDocument();
  });

  test('skip in CL dialog moves posting without generating cover letter', async () => {
    api.movePosting.mockResolvedValue({});

    const { container } = await renderPipeline({
      bookmarked: [{ id: 'p5', title: 'Dev Role', company: 'Co', match_score: 60, status: 'bookmarked' }],
    });

    const select = container.querySelector('.pipeline-card-actions select');
    await act(async () => { fireEvent.change(select, { target: { value: 'applied' } }); });

    await act(async () => { fireEvent.click(screen.getByText('Skip')); });

    await waitFor(() => {
      expect(api.movePosting).toHaveBeenCalledWith('p5', 'applied');
    });
    expect(api.generateCoverLetter).not.toHaveBeenCalled();
  });

  test('generate CL in dialog calls generateCoverLetter then moves posting', async () => {
    api.movePosting.mockResolvedValue({});
    api.generateCoverLetter.mockResolvedValue({ id: 'cl1' });

    const { container } = await renderPipeline({
      bookmarked: [{ id: 'p6', title: 'Architect', company: 'BigCorp', match_score: 88, status: 'bookmarked' }],
    });

    const select = container.querySelector('.pipeline-card-actions select');
    await act(async () => { fireEvent.change(select, { target: { value: 'applied' } }); });

    await act(async () => { fireEvent.click(screen.getByText('Generate Cover Letter')); });

    await waitFor(() => {
      expect(api.generateCoverLetter).toHaveBeenCalledWith('p6');
      expect(api.movePosting).toHaveBeenCalledWith('p6', 'applied');
    });
  });

  test('moving to non-applied stage does not show CL dialog', async () => {
    api.movePosting.mockResolvedValue({});

    const { container } = await renderPipeline({
      discovered: [{ id: 'p7', title: 'Analyst', company: 'FinCo', match_score: 55, status: 'discovered' }],
    });

    const select = container.querySelector('.pipeline-card-actions select');
    await act(async () => { fireEvent.change(select, { target: { value: 'bookmarked' } }); });

    expect(screen.queryByText('Moving to Applied')).not.toBeInTheDocument();
    expect(api.movePosting).toHaveBeenCalledWith('p7', 'bookmarked');
  });
});
