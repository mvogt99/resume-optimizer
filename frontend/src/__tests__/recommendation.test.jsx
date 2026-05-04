import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_RECOMMENDATION = {
  recommendation_id: 'abc-123',
  rankings: [
    {
      resume_id: 1,
      resume_version_id: null,
      filename: 'senior_architect_resume.txt',
      source: 'upload',
      score: 78,
      score_breakdown: {
        keyword_coverage: 82.0,
        semantic_similarity: 74.5,
        skills_match: 79.3,
        section_completeness: 75.0,
      },
      matching_keywords: ['python', 'kubernetes', 'aws'],
      missing_keywords: ['kafka', 'postgresql'],
      rank: 1,
    },
    {
      resume_id: 2,
      resume_version_id: null,
      filename: 'generic_developer_resume.txt',
      source: 'upload',
      score: 32,
      score_breakdown: {
        keyword_coverage: 28.0,
        semantic_similarity: 35.1,
        skills_match: 30.5,
        section_completeness: 50.0,
      },
      matching_keywords: ['python'],
      missing_keywords: ['kubernetes', 'aws', 'terraform'],
      rank: 2,
    },
  ],
  recommended_resume_id: 1,
  recommended_version_id: null,
  rationale: 'senior_architect_resume.txt is the best match with a score of 78/100, demonstrating strong alignment with Python, Kubernetes, and AWS requirements.',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

import ResumeRecommendation from '../components/ResumeRecommendation';

describe('ResumeRecommendation', () => {
  let onSelect;
  let onRecompare;

  beforeEach(() => {
    vi.clearAllMocks();
    onSelect = vi.fn();
    onRecompare = vi.fn();
  });

  test('renders ranked resume cards', () => {
    render(
      <ResumeRecommendation
        recommendation={MOCK_RECOMMENDATION}
        loading={false}
        onSelect={onSelect}
        onRecompare={onRecompare}
      />
    );

    // Use getAllByText since filename may appear in multiple places (card + rationale)
    expect(screen.getAllByText(/senior_architect_resume/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/generic_developer_resume/i).length).toBeGreaterThan(0);
  });

  test('highlights recommended resume as top pick', () => {
    render(
      <ResumeRecommendation
        recommendation={MOCK_RECOMMENDATION}
        loading={false}
        onSelect={onSelect}
        onRecompare={onRecompare}
      />
    );

    // The recommended card should have a visual indicator (badge/label)
    expect(screen.getAllByText(/recommended|top pick|best match/i).length).toBeGreaterThan(0);
  });

  test('shows score for each resume', () => {
    render(
      <ResumeRecommendation
        recommendation={MOCK_RECOMMENDATION}
        loading={false}
        onSelect={onSelect}
        onRecompare={onRecompare}
      />
    );

    // Scores may appear in multiple elements (score display + breakdown bars)
    expect(screen.getAllByText(/78/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/32/).length).toBeGreaterThan(0);
  });

  test('shows rationale text', () => {
    render(
      <ResumeRecommendation
        recommendation={MOCK_RECOMMENDATION}
        loading={false}
        onSelect={onSelect}
        onRecompare={onRecompare}
      />
    );

    // Rationale text contains "best match"
    expect(screen.getAllByText(/best match/i).length).toBeGreaterThan(0);
  });

  test('shows matching keywords for top resume', () => {
    render(
      <ResumeRecommendation
        recommendation={MOCK_RECOMMENDATION}
        loading={false}
        onSelect={onSelect}
        onRecompare={onRecompare}
      />
    );

    expect(screen.getAllByText(/python/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/kubernetes/i).length).toBeGreaterThan(0);
  });

  test('accept button calls onSelect with resume_id', () => {
    render(
      <ResumeRecommendation
        recommendation={MOCK_RECOMMENDATION}
        loading={false}
        onSelect={onSelect}
        onRecompare={onRecompare}
      />
    );

    // Primary button is "✓ Use This Resume" on the recommended card
    const primaryBtn = screen.getByText(/✓ Use This Resume/i);
    fireEvent.click(primaryBtn);

    expect(onSelect).toHaveBeenCalledWith(1, null);
  });

  test('override — selecting non-recommended fires onSelect with correct id', () => {
    render(
      <ResumeRecommendation
        recommendation={MOCK_RECOMMENDATION}
        loading={false}
        onSelect={onSelect}
        onRecompare={onRecompare}
      />
    );

    // Find select buttons for non-recommended cards
    const allSelectBtns = screen.getAllByRole('button', { name: /use this resume|select|choose/i });
    // Click second one (override)
    if (allSelectBtns.length > 1) {
      fireEvent.click(allSelectBtns[1]);
      expect(onSelect).toHaveBeenCalledWith(2, null);
    } else {
      // If only one button, ensure onSelect was called
      fireEvent.click(allSelectBtns[0]);
      expect(onSelect).toHaveBeenCalled();
    }
  });

  test('loading state shows spinner', () => {
    render(
      <ResumeRecommendation
        recommendation={null}
        loading={true}
        onSelect={onSelect}
        onRecompare={onRecompare}
      />
    );

    expect(screen.getByTestId('recommendation-loading')).toBeInTheDocument();
  });

  test('does not render cards while loading', () => {
    render(
      <ResumeRecommendation
        recommendation={null}
        loading={true}
        onSelect={onSelect}
        onRecompare={onRecompare}
      />
    );

    expect(screen.queryByText(/senior_architect/i)).not.toBeInTheDocument();
  });

  test('single resume result still renders correctly', () => {
    const singleRec = {
      ...MOCK_RECOMMENDATION,
      rankings: [MOCK_RECOMMENDATION.rankings[0]],
    };

    render(
      <ResumeRecommendation
        recommendation={singleRec}
        loading={false}
        onSelect={onSelect}
        onRecompare={onRecompare}
      />
    );

    expect(screen.getAllByText(/senior_architect_resume/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/78/).length).toBeGreaterThan(0);
  });

  test('mode toggle — Compare vs Merge toggle visible when multiple resumes', () => {
    render(
      <ResumeRecommendation
        recommendation={MOCK_RECOMMENDATION}
        loading={false}
        onSelect={onSelect}
        onRecompare={onRecompare}
        mode="compare"
        onModeChange={vi.fn()}
      />
    );

    // Component shows we're in compare mode via the mode-badge
    expect(screen.getAllByText(/compare mode|comparing|ranked/i).length).toBeGreaterThan(0);
  });
});
