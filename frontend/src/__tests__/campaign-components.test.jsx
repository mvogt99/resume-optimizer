import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// Mock API for all campaign component tests
vi.mock('../services/api', () => ({
  default: {
    getCampaign: vi.fn(),
    listCampaignPosts: vi.fn(),
    generateCampaignPosts: vi.fn(),
    updateCampaign: vi.fn(),
    updateCampaignPost: vi.fn(),
    deleteCampaignPost: vi.fn(),
    regenerateCampaignPost: vi.fn(),
    exportCampaign: vi.fn(),
    reorderCampaignPosts: vi.fn(),
    getJobStatus: vi.fn(),
    startCampaignInterview: vi.fn(),
    sendCampaignMessage: vi.fn(),
    createCampaignFromInterview: vi.fn(),
    getJourneyNarratives: vi.fn(),
    updateJourneyNarratives: vi.fn(),
    approveJourneyNarratives: vi.fn(),
    startJourneyReview: vi.fn(),
    sendJourneyReviewMessage: vi.fn(),
    applyJourneyReviewChanges: vi.fn(),
  },
}));

import CampaignCanvas from '../components/CampaignCanvas';
import CampaignInterview from '../components/CampaignInterview';
import CampaignTimeline from '../components/CampaignTimeline';
import PostEditor from '../components/PostEditor';
import JourneyNarratives from '../components/JourneyNarratives';

// ---------------------------------------------------------------------------
// CampaignCanvas Tests
// ---------------------------------------------------------------------------
describe('CampaignCanvas', () => {
  const mockBack = vi.fn();

  beforeEach(async () => {
    vi.clearAllMocks();
    const api = (await import('../services/api')).default;
    api.getCampaign.mockResolvedValue({
      id: 1, theme: 'Local AI Infra', audience: 'CTOs', tone: 'Professional', status: 'draft',
    });
    api.listCampaignPosts.mockResolvedValue({ posts: [] });
  });

  test('renders campaign theme as heading', async () => {
    await act(async () => { render(<CampaignCanvas campaignId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText('Local AI Infra')).toBeInTheDocument();
    });
  });

  test('renders back button', async () => {
    await act(async () => { render(<CampaignCanvas campaignId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText('Local AI Infra')).toBeInTheDocument();
    });
    const backBtn = screen.getByText(/back/i);
    fireEvent.click(backBtn);
    expect(mockBack).toHaveBeenCalled();
  });

  test('shows empty posts message', async () => {
    await act(async () => { render(<CampaignCanvas campaignId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText(/no posts yet/i)).toBeInTheDocument();
    });
  });

  test('renders Generate Posts button', async () => {
    await act(async () => { render(<CampaignCanvas campaignId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText('Generate Posts')).toBeInTheDocument();
    });
  });

  test('renders posts when loaded', async () => {
    const api = (await import('../services/api')).default;
    api.listCampaignPosts.mockResolvedValue({
      posts: [
        { id: 10, title: 'Post One', content: 'Content here', status: 'draft', hashtags: '#ai #gpu', position: 1 },
      ],
    });
    await act(async () => { render(<CampaignCanvas campaignId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText('Post One')).toBeInTheDocument();
    });
  });

  test('shows audience and tone metadata', async () => {
    await act(async () => { render(<CampaignCanvas campaignId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText(/CTOs/)).toBeInTheDocument();
      expect(screen.getByText(/Professional/)).toBeInTheDocument();
    });
  });

  test('shows loading state initially', async () => {
    const api = (await import('../services/api')).default;
    // Use never-resolving promises so the component stays in loading state
    api.getCampaign.mockReturnValue(new Promise(() => {}));
    api.listCampaignPosts.mockReturnValue(new Promise(() => {}));
    render(<CampaignCanvas campaignId="1" onBack={mockBack} />);
    expect(screen.getByText(/loading campaign/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// CampaignInterview Tests
// ---------------------------------------------------------------------------
describe('CampaignInterview', () => {
  const mockCreated = vi.fn();
  const mockBack = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  test('renders start form with heading', () => {
    render(<CampaignInterview onCampaignCreated={mockCreated} onBack={mockBack} />);
    expect(screen.getByText('New Campaign')).toBeInTheDocument();
  });

  test('renders Start Campaign Interview button', () => {
    render(<CampaignInterview onCampaignCreated={mockCreated} onBack={mockBack} />);
    expect(screen.getByText('Start Campaign Interview')).toBeInTheDocument();
  });

  test('renders theme input', () => {
    render(<CampaignInterview onCampaignCreated={mockCreated} onBack={mockBack} />);
    expect(screen.getByPlaceholderText(/local ai deployment/i)).toBeInTheDocument();
  });

  test('starts interview on button click', async () => {
    const api = (await import('../services/api')).default;
    api.startCampaignInterview.mockResolvedValue({
      session_id: 's1',
      stage: 'theme',
      message: 'What theme would you like?',
    });

    render(<CampaignInterview onCampaignCreated={mockCreated} onBack={mockBack} />);
    fireEvent.click(screen.getByText('Start Campaign Interview'));
    await waitFor(() => {
      expect(api.startCampaignInterview).toHaveBeenCalled();
      expect(screen.getByText(/campaign interview/i)).toBeInTheDocument();
    });
  });

  test('shows stage progress after start', async () => {
    const api = (await import('../services/api')).default;
    api.startCampaignInterview.mockResolvedValue({
      session_id: 's1',
      stage: 'theme',
      message: 'Tell me about the theme',
      suggestions: [],
    });

    render(<CampaignInterview onCampaignCreated={mockCreated} onBack={mockBack} />);
    fireEvent.click(screen.getByText('Start Campaign Interview'));
    await waitFor(() => {
      expect(screen.getByText('Theme')).toBeInTheDocument();
      expect(screen.getByText('Audience')).toBeInTheDocument();
    });
  });

  test('calls onBack when back clicked during interview', async () => {
    const api = (await import('../services/api')).default;
    api.startCampaignInterview.mockResolvedValue({
      session_id: 's1', stage: 'theme', message: 'Tell me', suggestions: [],
    });

    render(<CampaignInterview onCampaignCreated={mockCreated} onBack={mockBack} />);
    fireEvent.click(screen.getByText('Start Campaign Interview'));
    await waitFor(() => {
      expect(screen.getByText(/campaign interview/i)).toBeInTheDocument();
    });
    const backBtn = screen.getByText(/back/i);
    fireEvent.click(backBtn);
    expect(mockBack).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// CampaignTimeline Tests
// ---------------------------------------------------------------------------
describe('CampaignTimeline', () => {
  const baseCampaign = { created_at: '2026-03-01', cadence: 'weekly' };

  test('renders Timeline heading', () => {
    const posts = [{ id: 1, title: 'Post A', status: 'draft', content: 'x' }];
    render(<CampaignTimeline posts={posts} campaign={baseCampaign} />);
    expect(screen.getByText('Timeline')).toBeInTheDocument();
  });

  test('shows empty state with no posts', () => {
    render(<CampaignTimeline posts={[]} campaign={baseCampaign} />);
    expect(screen.getByText(/no posts to display/i)).toBeInTheDocument();
  });

  test('renders post nodes', () => {
    const posts = [
      { id: 1, title: 'First Post', status: 'draft', content: 'Hello' },
      { id: 2, title: 'Second Post', status: 'ready', content: 'World' },
    ];
    render(<CampaignTimeline posts={posts} campaign={baseCampaign} />);
    expect(screen.getByText('First Post')).toBeInTheDocument();
    expect(screen.getByText('Second Post')).toBeInTheDocument();
  });

  test('shows cadence info', () => {
    render(<CampaignTimeline posts={[{ id: 1, title: 'A', status: 'draft', content: 'x' }]} campaign={baseCampaign} />);
    expect(screen.getByText(/weekly/i)).toBeInTheDocument();
  });

  test('calls onSelectPost when clicking a node', () => {
    const mockSelect = vi.fn();
    const posts = [{ id: 1, title: 'Click Me', status: 'draft', content: 'x' }];
    render(<CampaignTimeline posts={posts} campaign={baseCampaign} onSelectPost={mockSelect} />);
    fireEvent.click(screen.getByText('Click Me'));
    expect(mockSelect).toHaveBeenCalledWith(1);
  });
});

// ---------------------------------------------------------------------------
// PostEditor Tests
// ---------------------------------------------------------------------------
describe('PostEditor', () => {
  const mockSave = vi.fn();
  const mockRegen = vi.fn();
  const mockClose = vi.fn();
  const basePost = {
    id: 1,
    title: 'My Post Title',
    content: 'Post content here',
    hashtags: '#ai #gpu',
    draft_history: [],
    source_refs: [],
  };

  beforeEach(() => vi.clearAllMocks());

  test('renders Edit Post heading', () => {
    render(<PostEditor post={basePost} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    expect(screen.getByText('Edit Post')).toBeInTheDocument();
  });

  test('renders title input with value', () => {
    render(<PostEditor post={basePost} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    const input = screen.getByDisplayValue('My Post Title');
    expect(input).toBeInTheDocument();
  });

  test('renders content textarea with value', () => {
    render(<PostEditor post={basePost} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    const textarea = screen.getByDisplayValue('Post content here');
    expect(textarea).toBeInTheDocument();
  });

  test('renders hashtags input', () => {
    render(<PostEditor post={basePost} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    expect(screen.getByDisplayValue('#ai #gpu')).toBeInTheDocument();
  });

  test('shows character count', () => {
    render(<PostEditor post={basePost} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    expect(screen.getByText(/17\/3000/)).toBeInTheDocument();
  });

  test('renders Save Changes button', () => {
    render(<PostEditor post={basePost} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    expect(screen.getByText('Save Changes')).toBeInTheDocument();
  });

  test('renders Cancel button that calls onClose', () => {
    render(<PostEditor post={basePost} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(mockClose).toHaveBeenCalled();
  });

  test('renders Regenerate button', () => {
    render(<PostEditor post={basePost} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    expect(screen.getByText('Regenerate')).toBeInTheDocument();
  });

  test('renders source references when present', () => {
    const postWithRefs = {
      ...basePost,
      source_refs: [{ type: 'project', name: 'AI Gateway' }],
    };
    render(<PostEditor post={postWithRefs} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    expect(screen.getByText('AI Gateway')).toBeInTheDocument();
  });

  test('renders draft history when present', () => {
    const postWithHistory = {
      ...basePost,
      draft_history: [
        { title: 'Draft v1', content: 'Old content' },
      ],
    };
    render(<PostEditor post={postWithHistory} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    expect(screen.getByText(/draft history/i)).toBeInTheDocument();
  });

  test('close button calls onClose', () => {
    render(<PostEditor post={basePost} campaignId="1" onSave={mockSave} onRegenerate={mockRegen} onClose={mockClose} />);
    const closeBtn = screen.getByText('×');
    fireEvent.click(closeBtn);
    expect(mockClose).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// JourneyNarratives Tests
// ---------------------------------------------------------------------------
describe('JourneyNarratives', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  test('shows loading state', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyNarratives.mockReturnValue(new Promise(() => {}));
    render(<JourneyNarratives />);
    expect(screen.getByText(/loading narratives/i)).toBeInTheDocument();
  });

  test('shows empty state when no narratives', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyNarratives.mockResolvedValue({ narratives: [] });
    render(<JourneyNarratives />);
    await waitFor(() => {
      expect(screen.getByText(/no narratives generated yet/i)).toBeInTheDocument();
    });
  });

  test('renders Build Narratives button in empty state', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyNarratives.mockResolvedValue({ narratives: [] });
    render(<JourneyNarratives />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /build narratives with ai/i })).toBeInTheDocument();
    });
  });

  test('renders narrative tabs', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyNarratives.mockResolvedValue({
      narratives: [
        { id: 1, narrative_type: 'resume_entry', title: 'Resume Entry 1', content: 'Led AI infra migration', approved: 0 },
      ],
    });
    render(<JourneyNarratives />);
    await waitFor(() => {
      expect(screen.getByText(/resume entries/i)).toBeInTheDocument();
      expect(screen.getByText(/linkedin sections/i)).toBeInTheDocument();
      expect(screen.getByText(/campaign seeds/i)).toBeInTheDocument();
    });
  });

  test('renders narrative content', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyNarratives.mockResolvedValue({
      narratives: [
        { id: 1, narrative_type: 'resume_entry', title: 'AI Migration', content: 'Architected local AI pipeline', approved: 0 },
      ],
    });
    render(<JourneyNarratives />);
    await waitFor(() => {
      expect(screen.getByText(/architected local ai pipeline/i)).toBeInTheDocument();
    });
  });

  test('shows Approve button for unapproved narratives', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyNarratives.mockResolvedValue({
      narratives: [
        { id: 1, narrative_type: 'resume_entry', title: 'Test', content: 'Content', approved: 0 },
      ],
    });
    render(<JourneyNarratives />);
    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });
  });

  test('shows Approved badge for approved narratives', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyNarratives.mockResolvedValue({
      narratives: [
        { id: 1, narrative_type: 'resume_entry', title: 'Test', content: 'Content', approved: 1 },
      ],
    });
    render(<JourneyNarratives />);
    await waitFor(() => {
      expect(screen.getByText('Approved')).toBeInTheDocument();
    });
  });
});
