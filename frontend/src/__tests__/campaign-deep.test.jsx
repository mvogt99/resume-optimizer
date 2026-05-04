import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  default: {
    listCampaigns: vi.fn(),
    deleteCampaign: vi.fn(),
    getCampaign: vi.fn(),
    listCampaignPosts: vi.fn(),
    generateCampaignPosts: vi.fn(),
    updateCampaign: vi.fn(),
    updateCampaignPost: vi.fn(),
    deleteCampaignPost: vi.fn(),
    regenerateCampaignPost: vi.fn(),
    exportCampaign: vi.fn(),
    reorderCampaignPosts: vi.fn(),
    startCampaignInterview: vi.fn(),
    sendCampaignMessage: vi.fn(),
    createCampaignFromInterview: vi.fn(),
    getJobStatus: vi.fn(),
    getDeepProfile: vi.fn(),
    buildDeepProfile: vi.fn(),
    startDeepInterview: vi.fn(),
    sendDeepInterviewMessage: vi.fn(),
    finalizeDeepInterview: vi.fn(),
    getRoleSynthesis: vi.fn(),
  },
}));

vi.mock('../components/CampaignInterview', () => ({
  default: ({ onCampaignCreated, onBack }) => (
    <div data-testid="campaign-interview">
      <button onClick={onBack}>Back</button>
      <button onClick={() => onCampaignCreated(1)}>Create</button>
    </div>
  ),
}));
vi.mock('../components/CampaignCanvas', () => ({
  default: ({ campaignId, onBack }) => (
    <div data-testid="campaign-canvas">
      Canvas {campaignId}
      <button onClick={onBack}>Back</button>
    </div>
  ),
}));
vi.mock('../components/PostEditor', () => ({
  default: () => <div data-testid="post-editor">PostEditor</div>,
}));
vi.mock('../components/CampaignTimeline', () => ({
  default: () => <div data-testid="campaign-timeline">CampaignTimeline</div>,
}));

import CampaignManager from '../components/CampaignManager';
import CampaignList from '../components/CampaignList';
import DeepAnalysis from '../components/DeepAnalysis';

// ---------------------------------------------------------------------------
// CampaignManager Tests
// ---------------------------------------------------------------------------
describe('CampaignManager', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const api = (await import('../services/api')).default;
    api.listCampaigns.mockResolvedValue({ campaigns: [] });
  });

  test('renders CampaignList by default', async () => {
    render(<CampaignManager />);
    await waitFor(() => {
      expect(screen.getByText('Your Campaigns')).toBeInTheDocument();
    });
  });

  test('renders heading via CampaignList child', async () => {
    render(<CampaignManager />);
    await waitFor(() => {
      expect(screen.getByText('+ New Campaign')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// CampaignList Tests (unmocked)
// ---------------------------------------------------------------------------
describe('CampaignList', () => {
  const mockSelect = vi.fn();
  const mockNew = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  test('renders heading', async () => {
    const api = (await import('../services/api')).default;
    api.listCampaigns.mockResolvedValue({ campaigns: [] });
    render(<CampaignList onSelectCampaign={mockSelect} onNewCampaign={mockNew} />);
    await waitFor(() => {
      expect(screen.getByText('Your Campaigns')).toBeInTheDocument();
    });
  });

  test('renders New Campaign button', async () => {
    const api = (await import('../services/api')).default;
    api.listCampaigns.mockResolvedValue({ campaigns: [] });
    render(<CampaignList onSelectCampaign={mockSelect} onNewCampaign={mockNew} />);
    await waitFor(() => {
      expect(screen.getByText('+ New Campaign')).toBeInTheDocument();
    });
  });

  test('shows empty state when no campaigns', async () => {
    const api = (await import('../services/api')).default;
    api.listCampaigns.mockResolvedValue({ campaigns: [] });
    render(<CampaignList onSelectCampaign={mockSelect} onNewCampaign={mockNew} />);
    await waitFor(() => {
      expect(screen.getByText(/No campaigns yet/)).toBeInTheDocument();
    });
  });

  test('shows Create Your First Campaign button in empty state', async () => {
    const api = (await import('../services/api')).default;
    api.listCampaigns.mockResolvedValue({ campaigns: [] });
    render(<CampaignList onSelectCampaign={mockSelect} onNewCampaign={mockNew} />);
    await waitFor(() => {
      expect(screen.getByText('Create Your First Campaign')).toBeInTheDocument();
    });
  });

  test('renders campaign cards', async () => {
    const api = (await import('../services/api')).default;
    api.listCampaigns.mockResolvedValue({
      campaigns: [
        { id: 1, theme: 'Local AI Leadership', audience: 'CTOs', tone: 'Professional', status: 'draft', post_count: 5 },
      ],
    });
    render(<CampaignList onSelectCampaign={mockSelect} onNewCampaign={mockNew} />);
    await waitFor(() => {
      expect(screen.getByText('Local AI Leadership')).toBeInTheDocument();
      expect(screen.getByText(/Audience: CTOs/)).toBeInTheDocument();
    });
  });

  test('New Campaign button calls onNewCampaign', async () => {
    const api = (await import('../services/api')).default;
    api.listCampaigns.mockResolvedValue({ campaigns: [] });
    render(<CampaignList onSelectCampaign={mockSelect} onNewCampaign={mockNew} />);
    await waitFor(() => {
      expect(screen.getByText('+ New Campaign')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('+ New Campaign'));
    expect(mockNew).toHaveBeenCalledTimes(1);
  });

  test('shows post count on campaign card', async () => {
    const api = (await import('../services/api')).default;
    api.listCampaigns.mockResolvedValue({
      campaigns: [
        { id: 1, theme: 'Test', audience: 'Devs', tone: 'Casual', status: 'ready', post_count: 3 },
      ],
    });
    render(<CampaignList onSelectCampaign={mockSelect} onNewCampaign={mockNew} />);
    await waitFor(() => {
      expect(screen.getByText(/3 posts/)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// DeepAnalysis Tests
// ---------------------------------------------------------------------------
describe('DeepAnalysis', () => {
  beforeEach(() => vi.clearAllMocks());

  test('shows empty state when no profile', async () => {
    const api = (await import('../services/api')).default;
    api.getDeepProfile.mockRejectedValue(new Error('not found'));
    render(<DeepAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('No deep profile yet')).toBeInTheDocument();
    });
  });

  test('shows Build Deep Profile button', async () => {
    const api = (await import('../services/api')).default;
    api.getDeepProfile.mockRejectedValue(new Error('not found'));
    render(<DeepAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('Build Deep Profile')).toBeInTheDocument();
    });
  });

  test('renders heading', async () => {
    const api = (await import('../services/api')).default;
    api.getDeepProfile.mockRejectedValue(new Error('not found'));
    render(<DeepAnalysis />);
    expect(screen.getByText('Deep Professional Analysis')).toBeInTheDocument();
  });

  test('shows profile sections when loaded', async () => {
    const api = (await import('../services/api')).default;
    api.getDeepProfile.mockResolvedValue({
      profile: {
        professional_summary: 'A seasoned architect',
        career_arc: { trajectory: 'ascending', phases: [] },
        technology_mastery: [],
        higher_order_skills: [],
        business_impacts: [],
        leadership_profile: {},
        differentiators: [],
        development_areas: [],
        cross_source_insights: [],
      },
      source_summary: '3 projects, 76 skills, 849 events',
      updated_at: '2026-03-10',
    });
    render(<DeepAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('Deep Professional Profile')).toBeInTheDocument();
      expect(screen.getByText('Professional Summary')).toBeInTheDocument();
    });
  });

  test('shows career arc section', async () => {
    const api = (await import('../services/api')).default;
    api.getDeepProfile.mockResolvedValue({
      profile: {
        professional_summary: 'Summary text',
        career_arc: { trajectory: 'ascending', phases: [{ name: 'Early Career', years: '2010-2015' }] },
        technology_mastery: [],
        higher_order_skills: [],
        business_impacts: [],
        leadership_profile: {},
        differentiators: [],
        development_areas: [],
        cross_source_insights: [],
      },
      source_summary: '3 projects, 76 skills, 849 events',
      updated_at: '2026-03-10',
    });
    render(<DeepAnalysis />);
    await waitFor(() => {
      expect(screen.getByText('Career Arc')).toBeInTheDocument();
    });
  });

  test('shows action buttons for role analysis', async () => {
    const api = (await import('../services/api')).default;
    api.getDeepProfile.mockResolvedValue({
      profile: {
        professional_summary: 'Sum',
        career_arc: { trajectory: 'stable', phases: [] },
        technology_mastery: [],
        higher_order_skills: [],
        business_impacts: [],
        leadership_profile: {},
        differentiators: [],
        development_areas: [],
        cross_source_insights: [],
      },
      source_summary: '3 projects, 76 skills, 849 events',
      updated_at: '2026-03-10',
    });
    render(<DeepAnalysis />);
    await waitFor(() => {
      expect(screen.getAllByText('Role Analysis').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Rebuild Profile')).toBeInTheDocument();
    });
  });
});
