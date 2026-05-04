import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  default: {
    getAgentStatus: vi.fn(),
    scoutListPostings: vi.fn(),
    scoutListCriteria: vi.fn(),
    scoutSearch: vi.fn(),
    scoutSaveCriteria: vi.fn(),
    scoutUpdatePosting: vi.fn(),
    scoutDeletePosting: vi.fn(),
    scoutRescorePosting: vi.fn(),
    scoutAddPosting: vi.fn(),
    getPipeline: vi.fn(),
    getPipelineAnalytics: vi.fn(),
    getPipelineReminders: vi.fn(),
    movePosting: vi.fn(),
    generateFollowup: vi.fn(),
    analyzePerformance: vi.fn(),
    coachListSessions: vi.fn(),
    coachStart: vi.fn(),
    coachAnswer: vi.fn(),
    coachGetSession: vi.fn(),
    tailorResume: vi.fn(),
    getTailoredResume: vi.fn(),
    generateCoverLetter: vi.fn(),
    getCoverLetterForPosting: vi.fn(),
    updateCoverLetter: vi.fn(),
    deleteCoverLetter: vi.fn(),
    regenerateCoverLetter: vi.fn(),
    advisorAnalyze: vi.fn(),
    advisorSkillsRoadmap: vi.fn(),
    advisorRoleRecommendations: vi.fn(),
    recordFeedback: vi.fn(),
    getTemplates: vi.fn(),
    generatePrepSheet: vi.fn(),
    applyToJob: vi.fn(),
    getApplicationBundle: vi.fn(),
  },
}));

vi.mock('../components/JobScout', () => ({ default: () => <div data-testid="job-scout">JobScout</div> }));
vi.mock('../components/ApplicationPipeline', () => ({ default: () => <div data-testid="pipeline">Pipeline</div> }));
vi.mock('../components/ResumeTailor', () => ({ default: () => <div data-testid="tailor">Tailor</div> }));
vi.mock('../components/CoverLetter', () => ({ default: () => <div data-testid="cover-letter">CoverLetter</div> }));
vi.mock('../components/InterviewCoach', () => ({ default: () => <div data-testid="coach">Coach</div> }));
vi.mock('../components/CareerAdvisor', () => ({ default: () => <div data-testid="advisor">Advisor</div> }));

import AgentDashboard from '../components/AgentDashboard';
import JobScoutReal from '../components/JobScout';
import ApplicationPipelineReal from '../components/ApplicationPipeline';
import InterviewCoachReal from '../components/InterviewCoach';
import ResumeTailorReal from '../components/ResumeTailor';
import CoverLetterReal from '../components/CoverLetter';
import CareerAdvisorReal from '../components/CareerAdvisor';

// ---------------------------------------------------------------------------
// AgentDashboard Tests
// ---------------------------------------------------------------------------
describe('AgentDashboard', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const api = (await import('../services/api')).default;
    api.getAgentStatus.mockResolvedValue({
      agents: [{ type: 'scout', status: 'ready' }],
      model_ready: true,
      swap_id: 'qwen3-coder-30b',
    });
    api.scoutListPostings.mockResolvedValue({ postings: [] });
  });

  test('renders heading', async () => {
    await act(async () => { render(<AgentDashboard />); });
    expect(screen.getByText('AI Career Agents')).toBeInTheDocument();
  });

  test('renders all 6 tab buttons', async () => {
    await act(async () => { render(<AgentDashboard />); });
    const tabs = ['Job Scout', 'Pipeline', 'Resume Tailor', 'Cover Letter', 'Interview Coach', 'Career Advisor'];
    tabs.forEach(tab => {
      expect(screen.getByText(tab)).toBeInTheDocument();
    });
  });

  test('default tab is Job Scout', async () => {
    await act(async () => { render(<AgentDashboard />); });
    expect(screen.getByTestId('job-scout')).toBeInTheDocument();
  });

  test('tab switching renders correct content', async () => {
    await act(async () => { render(<AgentDashboard />); });
    fireEvent.click(screen.getByText('Pipeline'));
    expect(screen.getByTestId('pipeline')).toBeInTheDocument();
    expect(screen.queryByTestId('job-scout')).not.toBeInTheDocument();
  });

  test('Career Advisor tab renders advisor component', async () => {
    await act(async () => { render(<AgentDashboard />); });
    fireEvent.click(screen.getByText('Career Advisor'));
    expect(screen.getByTestId('advisor')).toBeInTheDocument();
  });

  test('Interview Coach tab renders coach component', async () => {
    await act(async () => { render(<AgentDashboard />); });
    fireEvent.click(screen.getByText('Interview Coach'));
    expect(screen.getByTestId('coach')).toBeInTheDocument();
  });

  test('shows cost indicator', async () => {
    await act(async () => { render(<AgentDashboard />); });
    await waitFor(() => {
      expect(screen.getByText('$0.00')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// JobScout Tests (unmocked)
// ---------------------------------------------------------------------------
describe('JobScout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Restore real module for these tests
    vi.doUnmock('../components/JobScout');
  });

  test('renders search form heading', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockResolvedValue({ postings: [] });
    api.scoutListCriteria.mockResolvedValue({ criteria: [] });

    const { default: JobScout } = await import('../components/JobScout');
    await act(async () => { render(<JobScout />); });
    expect(screen.getByText('Job Search')).toBeInTheDocument();
  });

  test('renders Search Jobs button', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockResolvedValue({ postings: [] });
    api.scoutListCriteria.mockResolvedValue({ criteria: [] });

    const { default: JobScout } = await import('../components/JobScout');
    await act(async () => { render(<JobScout />); });
    expect(screen.getByText('Search Jobs')).toBeInTheDocument();
  });

  test('renders form fields', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockResolvedValue({ postings: [] });
    api.scoutListCriteria.mockResolvedValue({ criteria: [] });

    const { default: JobScout } = await import('../components/JobScout');
    await act(async () => { render(<JobScout />); });
    expect(screen.getByPlaceholderText(/Data Architect/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Remote, New York/)).toBeInTheDocument();
  });

  test('shows empty postings state', async () => {
    const api = (await import('../services/api')).default;
    api.scoutListPostings.mockResolvedValue({ postings: [] });
    api.scoutListCriteria.mockResolvedValue({ criteria: [] });

    const { default: JobScout } = await import('../components/JobScout');
    await act(async () => { render(<JobScout />); });
    await waitFor(() => {
      expect(screen.getByText(/No job postings yet/)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// ApplicationPipeline Tests (unmocked)
// ---------------------------------------------------------------------------
describe('ApplicationPipeline', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.doUnmock('../components/ApplicationPipeline');
  });

  test('shows loading then empty state', async () => {
    const api = (await import('../services/api')).default;
    api.getPipeline.mockResolvedValue({ total: 0, stages: {} });
    api.getPipelineAnalytics.mockResolvedValue(null);
    api.getPipelineReminders.mockResolvedValue({ reminders: [] });

    const { default: Pipeline } = await import('../components/ApplicationPipeline');
    render(<Pipeline />);
    await waitFor(() => {
      expect(screen.getByText(/No applications in the pipeline/)).toBeInTheDocument();
    });
  });

  // Pipeline integration tests (Prepare button, Cover Letter dialog)
  // are in pipeline-integration.test.jsx (separate file avoids vi.mock cache issues)
});

// ---------------------------------------------------------------------------
// ResumeTailor Tests (unmocked)
// ---------------------------------------------------------------------------
describe('ResumeTailor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.doUnmock('../components/ResumeTailor');
  });

  test('shows empty state without postingId', async () => {
    const { default: Tailor } = await import('../components/ResumeTailor');
    render(<Tailor />);
    expect(screen.getByText(/Select a job posting to tailor/)).toBeInTheDocument();
  });

  test('renders Tailor Resume button with postingId', async () => {
    const api = (await import('../services/api')).default;
    api.getTailoredResume.mockRejectedValue(new Error('not found'));

    const { default: Tailor } = await import('../components/ResumeTailor');
    render(<Tailor postingId="p1" />);
    await waitFor(() => {
      expect(screen.getByText('Tailor Resume')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// CoverLetter Tests (unmocked)
// ---------------------------------------------------------------------------
describe('CoverLetter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.doUnmock('../components/CoverLetter');
  });

  test('shows empty state without postingId', async () => {
    const { default: CL } = await import('../components/CoverLetter');
    render(<CL />);
    expect(screen.getByText(/Select a job posting to generate/)).toBeInTheDocument();
  });

  test('renders Generate button with postingId', async () => {
    const api = (await import('../services/api')).default;
    api.getCoverLetterForPosting.mockResolvedValue(null);

    const { default: CL } = await import('../components/CoverLetter');
    render(<CL postingId="p1" />);
    await waitFor(() => {
      expect(screen.getByText('Generate Cover Letter')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// InterviewCoach Tests (unmocked)
// ---------------------------------------------------------------------------
describe('InterviewCoach', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.doUnmock('../components/InterviewCoach');
  });

  test('renders New Session heading', async () => {
    const api = (await import('../services/api')).default;
    api.coachListSessions.mockResolvedValue({ sessions: [] });
    api.scoutListPostings.mockResolvedValue({ postings: [] });

    const { default: Coach } = await import('../components/InterviewCoach');
    await act(async () => { render(<Coach />); });
    expect(screen.getByText('New Session')).toBeInTheDocument();
  });

  test('renders Start Mock Interview button', async () => {
    const api = (await import('../services/api')).default;
    api.coachListSessions.mockResolvedValue({ sessions: [] });
    api.scoutListPostings.mockResolvedValue({ postings: [] });

    const { default: Coach } = await import('../components/InterviewCoach');
    await act(async () => { render(<Coach />); });
    expect(screen.getByText('Start Mock Interview')).toBeInTheDocument();
  });

  test('renders persona options', async () => {
    const api = (await import('../services/api')).default;
    api.coachListSessions.mockResolvedValue({ sessions: [] });
    api.scoutListPostings.mockResolvedValue({ postings: [] });

    const { default: Coach } = await import('../components/InterviewCoach');
    await act(async () => { render(<Coach />); });
    expect(screen.getByText('Interviewer Persona')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// CareerAdvisor Tests (unmocked)
// ---------------------------------------------------------------------------
describe('CareerAdvisor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.doUnmock('../components/CareerAdvisor');
  });

  test('renders empty state message', async () => {
    const { default: Advisor } = await import('../components/CareerAdvisor');
    render(<Advisor />);
    expect(screen.getByText(/Get AI-powered career insights/)).toBeInTheDocument();
  });

  test('renders action buttons', async () => {
    const { default: Advisor } = await import('../components/CareerAdvisor');
    render(<Advisor />);
    expect(screen.getByText('Career Analysis')).toBeInTheDocument();
    expect(screen.getByText('Role Recommendations')).toBeInTheDocument();
    expect(screen.getByText('Skills Roadmap')).toBeInTheDocument();
  });

  test('renders target role input', async () => {
    const { default: Advisor } = await import('../components/CareerAdvisor');
    render(<Advisor />);
    expect(screen.getByPlaceholderText(/VP of Engineering/)).toBeInTheDocument();
  });

  test('renders RTX 5090 cost info', async () => {
    const { default: Advisor } = await import('../components/CareerAdvisor');
    render(<Advisor />);
    expect(screen.getByText(/RTX 5090/)).toBeInTheDocument();
  });
});
