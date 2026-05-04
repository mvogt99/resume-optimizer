import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  default: {
    startBuilderInterview: vi.fn(),
    sendBuilderInterviewMessage: vi.fn(),
    getBuilderPreview: vi.fn(),
    compileBuilderResume: vi.fn(),
    editBuilderResume: vi.fn(),
    saveBuilderResume: vi.fn(),
  },
}));

import Onboarding from '../components/Onboarding';
import SourceSelector from '../components/SourceSelector';
import BuilderInterview from '../components/BuilderInterview';
import BuilderPreview from '../components/BuilderPreview';

// ---------------------------------------------------------------------------
// Onboarding Tests
// ---------------------------------------------------------------------------
describe('Onboarding', () => {
  const mockDismiss = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  test('renders first step title', () => {
    render(<Onboarding onDismiss={mockDismiss} />);
    expect(screen.getByText('Upload Your Resume')).toBeInTheDocument();
  });

  test('renders Skip button', () => {
    render(<Onboarding onDismiss={mockDismiss} />);
    expect(screen.getByText('Skip')).toBeInTheDocument();
  });

  test('renders Next button on first step', () => {
    render(<Onboarding onDismiss={mockDismiss} />);
    expect(screen.getByText('Next')).toBeInTheDocument();
  });

  test('Next advances to second step', () => {
    render(<Onboarding onDismiss={mockDismiss} />);
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('Paste a Job Description')).toBeInTheDocument();
  });

  test('two Nexts advance to third step', () => {
    render(<Onboarding onDismiss={mockDismiss} />);
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('See Your Score')).toBeInTheDocument();
  });

  test('last step shows Get Started button', () => {
    render(<Onboarding onDismiss={mockDismiss} />);
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('Get Started')).toBeInTheDocument();
  });

  test('Get Started calls onDismiss', () => {
    render(<Onboarding onDismiss={mockDismiss} />);
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Get Started'));
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });

  test('Skip calls onDismiss', () => {
    render(<Onboarding onDismiss={mockDismiss} />);
    fireEvent.click(screen.getByText('Skip'));
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });

  test('sets localStorage on dismiss', () => {
    render(<Onboarding onDismiss={mockDismiss} />);
    fireEvent.click(screen.getByText('Skip'));
    expect(localStorage.getItem('ro_onboarding_seen')).toBe('1');
  });
});

// ---------------------------------------------------------------------------
// SourceSelector Tests
// ---------------------------------------------------------------------------
describe('SourceSelector', () => {
  const mockToggle = vi.fn();
  const sources = {
    linkedin: { available: true, skills_count: 76, experience_count: 5, recommendations_count: 9 },
    projects: { available: true, count: 3 },
    journey: { available: false, count: 0 },
    experiences: { available: true, count: 2 },
  };

  beforeEach(() => vi.clearAllMocks());

  test('renders heading', () => {
    render(<SourceSelector availableSources={sources} selectedSources={[]} onToggle={mockToggle} />);
    expect(screen.getByText('Choose Data Sources')).toBeInTheDocument();
  });

  test('renders description', () => {
    render(<SourceSelector availableSources={sources} selectedSources={[]} onToggle={mockToggle} />);
    expect(screen.getByText(/Select which data to include/)).toBeInTheDocument();
  });

  test('renders LinkedIn card', () => {
    render(<SourceSelector availableSources={sources} selectedSources={[]} onToggle={mockToggle} />);
    expect(screen.getByText('LinkedIn Profile')).toBeInTheDocument();
  });

  test('renders Client Projects card', () => {
    render(<SourceSelector availableSources={sources} selectedSources={[]} onToggle={mockToggle} />);
    expect(screen.getByText('Client Projects')).toBeInTheDocument();
  });

  test('renders AI Journey card', () => {
    render(<SourceSelector availableSources={sources} selectedSources={[]} onToggle={mockToggle} />);
    expect(screen.getByText('AI Journey')).toBeInTheDocument();
  });

  test('renders Experience Interviews card', () => {
    render(<SourceSelector availableSources={sources} selectedSources={[]} onToggle={mockToggle} />);
    expect(screen.getByText('Experience Interviews')).toBeInTheDocument();
  });

  test('shows unavailable text for journey when not available', () => {
    render(<SourceSelector availableSources={sources} selectedSources={[]} onToggle={mockToggle} />);
    expect(screen.getByText('No data available')).toBeInTheDocument();
  });

  test('shows count for available sources', () => {
    render(<SourceSelector availableSources={sources} selectedSources={[]} onToggle={mockToggle} />);
    expect(screen.getByText(/76 skills/)).toBeInTheDocument();
    expect(screen.getByText(/3 approved/)).toBeInTheDocument();
    expect(screen.getByText(/2 interview/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// BuilderInterview Tests
// ---------------------------------------------------------------------------
describe('BuilderInterview', () => {
  const mockComplete = vi.fn();
  const mockSkip = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  test('renders intro heading', () => {
    render(<BuilderInterview sessionId="s1" onComplete={mockComplete} onSkip={mockSkip} />);
    expect(screen.getByText('Gap-Driven Interview')).toBeInTheDocument();
  });

  test('renders intro description', () => {
    render(<BuilderInterview sessionId="s1" onComplete={mockComplete} onSkip={mockSkip} />);
    expect(screen.getByText(/AI career coach will ask you about experience gaps/)).toBeInTheDocument();
  });

  test('renders Start Interview button', () => {
    render(<BuilderInterview sessionId="s1" onComplete={mockComplete} onSkip={mockSkip} />);
    expect(screen.getByText('Start Interview')).toBeInTheDocument();
  });

  test('renders Skip Interview button', () => {
    render(<BuilderInterview sessionId="s1" onComplete={mockComplete} onSkip={mockSkip} />);
    expect(screen.getByText('Skip Interview')).toBeInTheDocument();
  });

  test('Skip button calls onSkip', () => {
    render(<BuilderInterview sessionId="s1" onComplete={mockComplete} onSkip={mockSkip} />);
    fireEvent.click(screen.getByText('Skip Interview'));
    expect(mockSkip).toHaveBeenCalledTimes(1);
  });

  test('Start Interview calls API', async () => {
    const api = (await import('../services/api')).default;
    api.startBuilderInterview.mockResolvedValue({
      session_id: 'is1',
      message: 'Let me ask about gaps.',
      gaps_identified: 3,
    });
    render(<BuilderInterview sessionId="s1" onComplete={mockComplete} onSkip={mockSkip} />);
    fireEvent.click(screen.getByText('Start Interview'));
    await waitFor(() => {
      expect(api.startBuilderInterview).toHaveBeenCalledWith('s1');
      expect(screen.getByText(/Let me ask about gaps/)).toBeInTheDocument();
    });
  });

  test('shows sidebar after starting', async () => {
    const api = (await import('../services/api')).default;
    api.startBuilderInterview.mockResolvedValue({
      session_id: 'is1',
      message: 'Tell me about experience.',
      gaps_identified: 2,
    });
    render(<BuilderInterview sessionId="s1" onComplete={mockComplete} onSkip={mockSkip} />);
    fireEvent.click(screen.getByText('Start Interview'));
    await waitFor(() => {
      expect(screen.getByText(/Extracted Bullets/)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// BuilderPreview Tests
// ---------------------------------------------------------------------------
describe('BuilderPreview', () => {
  const mockSave = vi.fn();
  const mockBack = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  test('shows loading state', async () => {
    const api = (await import('../services/api')).default;
    api.getBuilderPreview.mockReturnValue(new Promise(() => {}));
    render(<BuilderPreview sessionId="s1" interviewSessionId="is1" onSave={mockSave} onBack={mockBack} />);
    expect(screen.getByText('Loading preview...')).toBeInTheDocument();
  });

  test('renders Compile Resume button', async () => {
    const api = (await import('../services/api')).default;
    api.getBuilderPreview.mockResolvedValue({
      text: 'Resume preview text',
      ats_score: null,
      score_breakdown: null,
      sources_used: [],
    });
    render(<BuilderPreview sessionId="s1" interviewSessionId="is1" onSave={mockSave} onBack={mockBack} />);
    await waitFor(() => {
      expect(screen.getByText('Compile Resume')).toBeInTheDocument();
    });
  });

  test('renders resume preview text', async () => {
    const api = (await import('../services/api')).default;
    api.getBuilderPreview.mockResolvedValue({
      text: 'My professional resume content',
      ats_score: null,
      score_breakdown: null,
      sources_used: [],
    });
    render(<BuilderPreview sessionId="s1" interviewSessionId="is1" onSave={mockSave} onBack={mockBack} />);
    await waitFor(() => {
      expect(screen.getByText('My professional resume content')).toBeInTheDocument();
    });
  });

  test('renders heading', async () => {
    const api = (await import('../services/api')).default;
    api.getBuilderPreview.mockResolvedValue({
      text: 'text',
      ats_score: null,
      score_breakdown: null,
      sources_used: [],
    });
    render(<BuilderPreview sessionId="s1" interviewSessionId="is1" onSave={mockSave} onBack={mockBack} />);
    await waitFor(() => {
      expect(screen.getByText('Resume Preview')).toBeInTheDocument();
    });
  });

  test('Back button calls onBack', async () => {
    const api = (await import('../services/api')).default;
    api.getBuilderPreview.mockResolvedValue({
      text: 'text',
      ats_score: null,
      score_breakdown: null,
      sources_used: [],
    });
    render(<BuilderPreview sessionId="s1" interviewSessionId="is1" onSave={mockSave} onBack={mockBack} />);
    await waitFor(() => {
      fireEvent.click(screen.getByText('Back'));
      expect(mockBack).toHaveBeenCalledTimes(1);
    });
  });
});

// ---------------------------------------------------------------------------
// API Service Tests
// ---------------------------------------------------------------------------
describe('api service', () => {
  test('exports default object with expected methods', async () => {
    vi.doUnmock('../services/api');
    // We just verify the module shape — real HTTP calls are mocked above
    const apiModule = await import('../services/api');
    const api = apiModule.default;
    expect(typeof api.login).toBe('function');
    expect(typeof api.register).toBe('function');
    expect(typeof api.uploadResume).toBe('function');
    expect(typeof api.uploadJobDescription).toBe('function');
    expect(typeof api.optimizeResume).toBe('function');
    expect(typeof api.getSkillsGap).toBe('function');
    expect(typeof api.listCampaigns).toBe('function');
    expect(typeof api.scoutSearch).toBe('function');
    expect(typeof api.getPipeline).toBe('function');
    expect(typeof api.buildDeepProfile).toBe('function');
  });

  test('api has campaign CRUD methods', async () => {
    vi.doUnmock('../services/api');
    const apiModule = await import('../services/api');
    const api = apiModule.default;
    expect(typeof api.startCampaignInterview).toBe('function');
    expect(typeof api.sendCampaignMessage).toBe('function');
    expect(typeof api.createCampaignFromInterview).toBe('function');
    expect(typeof api.listCampaignPosts).toBe('function');
    expect(typeof api.generateCampaignPosts).toBe('function');
    expect(typeof api.exportCampaign).toBe('function');
  });

  test('api has agent methods', async () => {
    vi.doUnmock('../services/api');
    const apiModule = await import('../services/api');
    const api = apiModule.default;
    expect(typeof api.scoutListPostings).toBe('function');
    expect(typeof api.scoutSaveCriteria).toBe('function');
    expect(typeof api.getPipelineAnalytics).toBe('function');
    expect(typeof api.coachStart).toBe('function');
    expect(typeof api.advisorAnalyze).toBe('function');
    expect(typeof api.tailorResume).toBe('function');
    expect(typeof api.generateCoverLetter).toBe('function');
  });

  test('api has builder methods', async () => {
    vi.doUnmock('../services/api');
    const apiModule = await import('../services/api');
    const api = apiModule.default;
    expect(typeof api.getBuilderSources).toBe('function');
    expect(typeof api.startBuilderSession).toBe('function');
    expect(typeof api.getBuilderPreview).toBe('function');
    expect(typeof api.compileBuilderResume).toBe('function');
    expect(typeof api.saveBuilderResume).toBe('function');
    expect(typeof api.startBuilderInterview).toBe('function');
  });

  test('api has journey methods', async () => {
    vi.doUnmock('../services/api');
    const apiModule = await import('../services/api');
    const api = apiModule.default;
    expect(typeof api.startJourneyMining).toBe('function');
    expect(typeof api.getJourneyTimeline).toBe('function');
    expect(typeof api.getJourneySkills).toBe('function');
    expect(typeof api.getJourneyNarratives).toBe('function');
    expect(typeof api.approveJourneyNarratives).toBe('function');
  });
});
