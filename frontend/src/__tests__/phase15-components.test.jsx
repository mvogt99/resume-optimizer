import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// Mock API for all Phase 15 component tests
vi.mock('../services/api', () => ({
  default: {
    coachListSessions: vi.fn(),
    coachStart: vi.fn(),
    coachAnswer: vi.fn(),
    coachGetSession: vi.fn(),
    generatePrepSheet: vi.fn(),
    scoutListPostings: vi.fn(),
    generateCoverLetter: vi.fn(),
    getCoverLetterForPosting: vi.fn(),
    updateCoverLetter: vi.fn(),
    regenerateCoverLetter: vi.fn(),
    getResumeVersions: vi.fn(),
    getResumeVersion: vi.fn(),
    buildDeepProfile: vi.fn(),
    getLinkedInUpdates: vi.fn(),
    generateLinkedInUpdate: vi.fn(),
    updateLinkedInSection: vi.fn(),
    getAnalyticsOverview: vi.fn(),
    listCampaigns: vi.fn(),
  },
}));

import InterviewCoachUI from '../components/InterviewCoachUI';
import CoverLetterUI from '../components/CoverLetterUI';
import VersionDiff from '../components/VersionDiff';
import PortfolioShowcase from '../components/PortfolioShowcase';
import RecommendationDrafter from '../components/RecommendationDrafter';
import CampaignAnalytics from '../components/CampaignAnalytics';

// ---------------------------------------------------------------------------
// InterviewCoachUI Tests
// ---------------------------------------------------------------------------
describe('InterviewCoachUI', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const api = (await import('../services/api')).default;
    api.coachListSessions.mockResolvedValue({ sessions: [] });
  });

  test('renders session sidebar with New Session button', async () => {
    await act(async () => { render(<InterviewCoachUI />); });
    await waitFor(() => {
      expect(screen.getByText('Sessions')).toBeInTheDocument();
      expect(screen.getByText('New Session')).toBeInTheDocument();
    });
  });

  test('shows empty main area when no active session', async () => {
    await act(async () => { render(<InterviewCoachUI />); });
    await waitFor(() => {
      expect(screen.getByText('Interview Coach')).toBeInTheDocument();
      expect(screen.getByText(/practice mock interviews/i)).toBeInTheDocument();
    });
  });

  test('shows config panel when New Session clicked', async () => {
    await act(async () => { render(<InterviewCoachUI />); });
    await waitFor(() => {
      expect(screen.getByText('New Session')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('New Session'));
    await waitFor(() => {
      expect(screen.getByText('Configure Mock Interview')).toBeInTheDocument();
      expect(screen.getByText('Start Interview')).toBeInTheDocument();
    });
  });

  test('renders persona selector in config', async () => {
    await act(async () => { render(<InterviewCoachUI />); });
    fireEvent.click(screen.getByText('New Session'));
    await waitFor(() => {
      expect(screen.getByText('Interviewer Persona')).toBeInTheDocument();
      // Check select has persona options
      const select = screen.getByRole('combobox');
      expect(select).toBeInTheDocument();
    });
  });

  test('renders session list when sessions exist', async () => {
    const api = (await import('../services/api')).default;
    api.coachListSessions.mockResolvedValue({
      sessions: [
        { session_id: 's1', persona: 'technical', is_complete: false },
        { session_id: 's2', persona: 'hr_recruiter', is_complete: true },
      ],
    });
    await act(async () => { render(<InterviewCoachUI />); });
    await waitFor(() => {
      expect(screen.getByText('technical')).toBeInTheDocument();
      expect(screen.getByText('hr_recruiter')).toBeInTheDocument();
      expect(screen.getByText('Complete')).toBeInTheDocument();
      expect(screen.getByText('In Progress')).toBeInTheDocument();
    });
  });

  test('shows chat messages after starting session', async () => {
    const api = (await import('../services/api')).default;
    api.coachStart.mockResolvedValue({
      session_id: 's1',
      question: 'Tell me about yourself.',
    });
    await act(async () => { render(<InterviewCoachUI />); });
    fireEvent.click(screen.getByText('New Session'));
    await waitFor(() => {
      expect(screen.getByText('Start Interview')).toBeInTheDocument();
    });
    await act(async () => {
      fireEvent.click(screen.getByText('Start Interview'));
    });
    await waitFor(() => {
      expect(screen.getByText('Tell me about yourself.')).toBeInTheDocument();
    });
  });

  test('shows error state on API failure', async () => {
    const api = (await import('../services/api')).default;
    api.coachListSessions.mockRejectedValue(new Error('Network error'));
    await act(async () => { render(<InterviewCoachUI />); });
    await waitFor(() => {
      expect(screen.getByText(/failed to load sessions/i)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// CoverLetterUI Tests
// ---------------------------------------------------------------------------
describe('CoverLetterUI', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  test('renders header and empty main when no postings', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockResolvedValue({ postings: [] });
    await act(async () => { render(<CoverLetterUI />); });
    await waitFor(() => {
      expect(screen.getByText('Cover Letters')).toBeInTheDocument();
      expect(screen.getByText('Cover Letter Generator')).toBeInTheDocument();
    });
  });

  test('renders posting sidebar with items', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockResolvedValue({
      postings: [
        { id: 1, title: 'Senior Architect', company: 'Acme Corp' },
        { id: 2, title: 'Staff Engineer', company: 'Beta Inc' },
      ],
    });
    await act(async () => { render(<CoverLetterUI />); });
    await waitFor(() => {
      expect(screen.getByText('Senior Architect')).toBeInTheDocument();
      expect(screen.getByText('Staff Engineer')).toBeInTheDocument();
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });
  });

  test('renders letter preview with Edit/Regenerate/Copy buttons', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockResolvedValue({
      postings: [{ id: 1, title: 'Architect', company: 'Acme' }],
    });
    api.getCoverLetterForPosting.mockResolvedValue({
      id: 10,
      subject: 'Application for Architect',
      greeting: 'Dear Hiring Manager,',
      body: 'I am writing to express my interest...',
      closing: 'Best regards,\nMike Vogt',
    });
    await act(async () => { render(<CoverLetterUI />); });
    await waitFor(() => {
      expect(screen.getByText('Architect')).toBeInTheDocument();
    });
    await act(async () => {
      fireEvent.click(screen.getByText('Architect'));
    });
    await waitFor(() => {
      expect(screen.getByText('Edit')).toBeInTheDocument();
      expect(screen.getByText('Regenerate')).toBeInTheDocument();
      expect(screen.getByText('Copy')).toBeInTheDocument();
    });
  });

  test('shows edit textarea when Edit clicked', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockResolvedValue({
      postings: [{ id: 1, title: 'Architect', company: 'Acme' }],
    });
    api.getCoverLetterForPosting.mockResolvedValue({
      id: 10,
      subject: 'Application',
      greeting: 'Dear Team,',
      body: 'Body text here.',
      closing: 'Thanks',
    });
    await act(async () => { render(<CoverLetterUI />); });
    await waitFor(() => { expect(screen.getByText('Architect')).toBeInTheDocument(); });
    await act(async () => { fireEvent.click(screen.getByText('Architect')); });
    await waitFor(() => { expect(screen.getByText('Edit')).toBeInTheDocument(); });
    fireEvent.click(screen.getByText('Edit'));
    await waitFor(() => {
      expect(screen.getByText('Save')).toBeInTheDocument();
      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });
  });

  test('shows empty posting message when no postings found', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockResolvedValue({ postings: [] });
    await act(async () => { render(<CoverLetterUI />); });
    await waitFor(() => {
      expect(screen.getByText(/no postings found/i)).toBeInTheDocument();
    });
  });

  test('shows error state on API failure', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockRejectedValue(new Error('Network error'));
    await act(async () => { render(<CoverLetterUI />); });
    await waitFor(() => {
      expect(screen.getByText(/failed to load postings/i)).toBeInTheDocument();
    });
  });

  test('renders feedback textarea when Regenerate clicked', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockResolvedValue({
      postings: [{ id: 1, title: 'Dev', company: 'Co' }],
    });
    api.getCoverLetterForPosting.mockResolvedValue({
      id: 10, subject: 'App', greeting: 'Hi', body: 'Text', closing: 'Bye',
    });
    await act(async () => { render(<CoverLetterUI />); });
    await waitFor(() => { expect(screen.getByText('Dev')).toBeInTheDocument(); });
    await act(async () => { fireEvent.click(screen.getByText('Dev')); });
    await waitFor(() => { expect(screen.getByText('Regenerate')).toBeInTheDocument(); });
    fireEvent.click(screen.getByText('Regenerate'));
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/optional feedback/i)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// VersionDiff Tests
// ---------------------------------------------------------------------------
describe('VersionDiff', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  test('renders version dropdowns and Compare button', async () => {
    const api = (await import('../services/api')).default;
    api.getResumeVersions.mockResolvedValue({
      versions: [
        { id: 1, source: 'upload' },
        { id: 2, source: 'builder' },
      ],
    });
    await act(async () => { render(<VersionDiff />); });
    await waitFor(() => {
      expect(screen.getByText('Version Comparison')).toBeInTheDocument();
      expect(screen.getByText('Version A')).toBeInTheDocument();
      expect(screen.getByText('Version B')).toBeInTheDocument();
      expect(screen.getByText('Compare')).toBeInTheDocument();
    });
  });

  test('shows empty state when no diff computed', async () => {
    const api = (await import('../services/api')).default;
    api.getResumeVersions.mockResolvedValue({ versions: [] });
    await act(async () => { render(<VersionDiff />); });
    await waitFor(() => {
      expect(screen.getByText(/select two resume versions/i)).toBeInTheDocument();
    });
  });

  test('renders diff stats after comparing', async () => {
    const api = (await import('../services/api')).default;
    api.getResumeVersions.mockResolvedValue({
      versions: [
        { id: 1, source: 'upload' },
        { id: 2, source: 'builder' },
      ],
    });
    api.getResumeVersion.mockImplementation((id) => {
      if (String(id) === '1') return Promise.resolve({ parsed_text: 'Line one\nLine two', source: 'upload' });
      return Promise.resolve({ parsed_text: 'Line one\nLine three', source: 'builder' });
    });
    await act(async () => { render(<VersionDiff />); });
    await waitFor(() => {
      expect(screen.getByText('Version A')).toBeInTheDocument();
    });

    // Select versions
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: '1' } });
    fireEvent.change(selects[1], { target: { value: '2' } });

    await act(async () => {
      fireEvent.click(screen.getByText('Compare'));
    });
    await waitFor(() => {
      expect(screen.getByText('Unified Diff')).toBeInTheDocument();
      expect(screen.getByText('Side-by-Side Preview')).toBeInTheDocument();
    });
  });

  test('Compare button disabled when same version selected', async () => {
    const api = (await import('../services/api')).default;
    api.getResumeVersions.mockResolvedValue({
      versions: [{ id: 1, source: 'upload' }],
    });
    await act(async () => { render(<VersionDiff />); });
    await waitFor(() => {
      expect(screen.getByText('Compare')).toBeInTheDocument();
    });
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: '1' } });
    fireEvent.change(selects[1], { target: { value: '1' } });
    expect(screen.getByText('Compare')).toBeDisabled();
  });

  test('shows error on API failure during compare', async () => {
    const api = (await import('../services/api')).default;
    api.getResumeVersions.mockResolvedValue({
      versions: [
        { id: 1, source: 'v1' },
        { id: 2, source: 'v2' },
      ],
    });
    api.getResumeVersion.mockRejectedValue(new Error('fail'));
    await act(async () => { render(<VersionDiff />); });
    await waitFor(() => { expect(screen.getByText('Version A')).toBeInTheDocument(); });
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: '1' } });
    fireEvent.change(selects[1], { target: { value: '2' } });
    await act(async () => { fireEvent.click(screen.getByText('Compare')); });
    await waitFor(() => {
      expect(screen.getByText(/failed to load version content/i)).toBeInTheDocument();
    });
  });

  test('renders version options in dropdowns', async () => {
    const api = (await import('../services/api')).default;
    api.getResumeVersions.mockResolvedValue({
      versions: [
        { id: 1, source: 'upload' },
        { id: 2, source: 'gdrive' },
        { id: 3, source: 'builder' },
      ],
    });
    await act(async () => { render(<VersionDiff />); });
    await waitFor(() => {
      // Each dropdown should have 3 options + placeholder
      const options = screen.getAllByRole('option');
      // 2 dropdowns × (1 placeholder + 3 versions) = 8
      expect(options.length).toBe(8);
    });
  });
});

// ---------------------------------------------------------------------------
// PortfolioShowcase Tests
// ---------------------------------------------------------------------------
describe('PortfolioShowcase', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders Generate Portfolio button in empty state', async () => {
    await act(async () => { render(<PortfolioShowcase />); });
    expect(screen.getByText('Portfolio Showcase')).toBeInTheDocument();
    expect(screen.getByText('Generate Portfolio')).toBeInTheDocument();
    expect(screen.getByText(/generate a structured portfolio/i)).toBeInTheDocument();
  });

  test('renders portfolio sections after generation', async () => {
    const api = (await import('../services/api')).default;
    api.buildDeepProfile.mockResolvedValue({
      career_phases: [
        { phase: 'Early Career', description: 'Started as software engineer' },
      ],
      projects: [
        { name: 'AI Gateway', client: 'Internal', role: 'Architect', technologies: ['Python', 'FastAPI'], outcomes: ['Reduced latency 50%'] },
      ],
      skills_summary: ['Python', 'Docker', 'Kubernetes'],
      differentiators: ['20 years cross-industry experience'],
    });
    await act(async () => { render(<PortfolioShowcase />); });
    await act(async () => {
      fireEvent.click(screen.getByText('Generate Portfolio'));
    });
    await waitFor(() => {
      expect(screen.getByText('Career Phases')).toBeInTheDocument();
      expect(screen.getByText('Projects')).toBeInTheDocument();
      expect(screen.getByText('Skills')).toBeInTheDocument();
      expect(screen.getByText('AI Gateway')).toBeInTheDocument();
    });
  });

  test('renders technology tags on project cards', async () => {
    const api = (await import('../services/api')).default;
    api.buildDeepProfile.mockResolvedValue({
      projects: [
        { name: 'Gateway', technologies: ['Python', 'Redis'], outcomes: [] },
      ],
      skills_summary: [],
    });
    await act(async () => { render(<PortfolioShowcase />); });
    await act(async () => { fireEvent.click(screen.getByText('Generate Portfolio')); });
    await waitFor(() => {
      expect(screen.getByText('Python')).toBeInTheDocument();
      expect(screen.getByText('Redis')).toBeInTheDocument();
    });
  });

  test('renders Export as Text and Regenerate buttons', async () => {
    const api = (await import('../services/api')).default;
    api.buildDeepProfile.mockResolvedValue({
      projects: [{ name: 'P1', technologies: [], outcomes: [] }],
      skills_summary: ['Go'],
    });
    await act(async () => { render(<PortfolioShowcase />); });
    await act(async () => { fireEvent.click(screen.getByText('Generate Portfolio')); });
    await waitFor(() => {
      expect(screen.getByText('Export as Text')).toBeInTheDocument();
      expect(screen.getByText('Regenerate')).toBeInTheDocument();
    });
  });

  test('shows error on API failure', async () => {
    const api = (await import('../services/api')).default;
    api.buildDeepProfile.mockRejectedValue(new Error('fail'));
    await act(async () => { render(<PortfolioShowcase />); });
    await act(async () => { fireEvent.click(screen.getByText('Generate Portfolio')); });
    await waitFor(() => {
      expect(screen.getByText(/failed to generate portfolio/i)).toBeInTheDocument();
    });
  });

  test('renders differentiators list', async () => {
    const api = (await import('../services/api')).default;
    api.buildDeepProfile.mockResolvedValue({
      projects: [],
      skills_summary: [],
      differentiators: ['Unique blend of maritime and tech'],
    });
    await act(async () => { render(<PortfolioShowcase />); });
    await act(async () => { fireEvent.click(screen.getByText('Generate Portfolio')); });
    await waitFor(() => {
      expect(screen.getByText('Differentiators')).toBeInTheDocument();
      expect(screen.getByText('Unique blend of maritime and tech')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// RecommendationDrafter Tests
// ---------------------------------------------------------------------------
describe('RecommendationDrafter', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const api = (await import('../services/api')).default;
    api.getLinkedInUpdates.mockResolvedValue([]);
  });

  test('renders form fields', async () => {
    await act(async () => { render(<RecommendationDrafter />); });
    await waitFor(() => {
      expect(screen.getByText('Recommendation Drafter')).toBeInTheDocument();
      expect(screen.getByText('New Request')).toBeInTheDocument();
      expect(screen.getByText('Target Name *')).toBeInTheDocument();
      expect(screen.getByText('Relationship')).toBeInTheDocument();
      expect(screen.getByText('Shared Projects')).toBeInTheDocument();
      expect(screen.getByText('Specific Skills to Highlight')).toBeInTheDocument();
    });
  });

  test('renders Generate Draft button disabled when name empty', async () => {
    await act(async () => { render(<RecommendationDrafter />); });
    await waitFor(() => {
      const btn = screen.getByText('Generate Draft');
      expect(btn).toBeInTheDocument();
      expect(btn).toBeDisabled();
    });
  });

  test('enables Generate Draft when name filled', async () => {
    await act(async () => { render(<RecommendationDrafter />); });
    await waitFor(() => {
      expect(screen.getByText('Generate Draft')).toBeInTheDocument();
    });
    const nameInput = screen.getByPlaceholderText('e.g., Jane Smith');
    fireEvent.change(nameInput, { target: { value: 'Jane Smith' } });
    expect(screen.getByText('Generate Draft')).not.toBeDisabled();
  });

  test('shows drafts list when drafts exist', async () => {
    const api = (await import('../services/api')).default;
    api.getLinkedInUpdates.mockResolvedValue([
      { id: 1, target_name: 'Bob Chen', relationship: 'colleague', body: 'Great collaborator on many projects.' },
    ]);
    await act(async () => { render(<RecommendationDrafter />); });
    await waitFor(() => {
      expect(screen.getByText('Bob Chen')).toBeInTheDocument();
      expect(screen.getByText(/great collaborator/i)).toBeInTheDocument();
    });
  });

  test('renders Edit, Copy, Delete buttons on draft cards', async () => {
    const api = (await import('../services/api')).default;
    api.getLinkedInUpdates.mockResolvedValue([
      { id: 1, target_name: 'Alice', body: 'Draft content here for review.' },
    ]);
    await act(async () => { render(<RecommendationDrafter />); });
    await waitFor(() => {
      expect(screen.getByText('Edit')).toBeInTheDocument();
      expect(screen.getByText('Copy')).toBeInTheDocument();
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });
  });

  test('shows empty state when no drafts', async () => {
    await act(async () => { render(<RecommendationDrafter />); });
    await waitFor(() => {
      expect(screen.getByText(/no drafts yet/i)).toBeInTheDocument();
    });
  });

  test('renders draft count in header', async () => {
    const api = (await import('../services/api')).default;
    api.getLinkedInUpdates.mockResolvedValue([
      { id: 1, target_name: 'A', body: 'x' },
      { id: 2, target_name: 'B', body: 'y' },
    ]);
    await act(async () => { render(<RecommendationDrafter />); });
    await waitFor(() => {
      expect(screen.getByText('Drafts (2)')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// CampaignAnalytics Tests
// ---------------------------------------------------------------------------
describe('CampaignAnalytics', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  test('shows loading state initially', async () => {
    const api = (await import('../services/api')).default;
    api.getAnalyticsOverview.mockReturnValue(new Promise(() => {}));
    api.listCampaigns.mockReturnValue(new Promise(() => {}));
    render(<CampaignAnalytics />);
    expect(screen.getByText(/loading analytics/i)).toBeInTheDocument();
  });

  test('renders summary cards with campaign data', async () => {
    const api = (await import('../services/api')).default;
    api.getAnalyticsOverview.mockResolvedValue({});
    api.listCampaigns.mockResolvedValue({
      campaigns: [
        { id: 1, theme: 'Leadership', audience: 'Executives', tone: 'professional', post_count: 5, status: 'active' },
        { id: 2, theme: 'Tech', audience: 'Engineers', tone: 'casual', post_count: 3, status: 'draft' },
      ],
    });
    await act(async () => { render(<CampaignAnalytics />); });
    await waitFor(() => {
      expect(screen.getByText('Campaign Analytics')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument(); // Total Campaigns
      expect(screen.getByText('8')).toBeInTheDocument(); // Total Posts
      expect(screen.getByText('4')).toBeInTheDocument(); // Avg Posts/Campaign
      expect(screen.getByText('Total Campaigns')).toBeInTheDocument();
      expect(screen.getByText('Total Posts')).toBeInTheDocument();
    });
  });

  test('renders theme distribution chart', async () => {
    const api = (await import('../services/api')).default;
    api.getAnalyticsOverview.mockResolvedValue({});
    api.listCampaigns.mockResolvedValue({
      campaigns: [
        { id: 1, theme: 'AI Innovation', post_count: 4, status: 'active' },
        { id: 2, theme: 'AI Innovation', post_count: 3, status: 'draft' },
        { id: 3, theme: 'Cloud', post_count: 2, status: 'active' },
      ],
    });
    render(<CampaignAnalytics />);
    await waitFor(() => {
      expect(screen.getByText('Theme Distribution')).toBeInTheDocument();
    });
    expect(screen.getAllByText('AI Innovation').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Cloud').length).toBeGreaterThanOrEqual(1);
  });

  test('renders comparison table with rows', async () => {
    const api = (await import('../services/api')).default;
    api.getAnalyticsOverview.mockResolvedValue({});
    api.listCampaigns.mockResolvedValue({
      campaigns: [
        { id: 1, theme: 'Leadership', audience: 'CIOs', tone: 'formal', post_count: 6, status: 'active' },
      ],
    });
    render(<CampaignAnalytics />);
    await waitFor(() => {
      expect(screen.getByText('Campaign Comparison')).toBeInTheDocument();
    });
    expect(screen.getAllByText('Leadership').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('CIOs')).toBeInTheDocument();
  });

  test('shows empty state when no campaigns', async () => {
    const api = (await import('../services/api')).default;
    api.getAnalyticsOverview.mockResolvedValue({});
    api.listCampaigns.mockResolvedValue({ campaigns: [] });
    await act(async () => { render(<CampaignAnalytics />); });
    await waitFor(() => {
      expect(screen.getByText(/no campaigns found/i)).toBeInTheDocument();
    });
  });

  test('shows error state on API failure', async () => {
    const api = (await import('../services/api')).default;
    api.getAnalyticsOverview.mockRejectedValue(new Error('fail'));
    api.listCampaigns.mockRejectedValue(new Error('fail'));
    await act(async () => { render(<CampaignAnalytics />); });
    await waitFor(() => {
      expect(screen.getByText(/failed to load analytics/i)).toBeInTheDocument();
    });
  });

  test('renders tone distribution', async () => {
    const api = (await import('../services/api')).default;
    api.getAnalyticsOverview.mockResolvedValue({});
    api.listCampaigns.mockResolvedValue({
      campaigns: [
        { id: 1, theme: 'A', tone: 'professional', post_count: 1, status: 'active' },
        { id: 2, theme: 'B', tone: 'casual', post_count: 2, status: 'draft' },
      ],
    });
    render(<CampaignAnalytics />);
    await waitFor(() => {
      expect(screen.getByText('Tone Distribution')).toBeInTheDocument();
    });
    expect(screen.getAllByText('professional').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('casual').length).toBeGreaterThanOrEqual(1);
  });
});
