import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  default: {
    listClientProjects: vi.fn(),
    listDriveFolders: vi.fn(),
    createClientProject: vi.fn(),
    startProjectAnalysis: vi.fn(),
    reanalyzeProject: vi.fn(),
    getJobStatus: vi.fn(),
    getProjectAnalysis: vi.fn(),
    listProjectDocuments: vi.fn(),
    updateProjectAnalysis: vi.fn(),
    approveProjectAnalysis: vi.fn(),
    getJourneyTimeline: vi.fn(),
    getJourneySkills: vi.fn(),
    getJourneyAchievements: vi.fn(),
    getJourneyNarratives: vi.fn(),
    updateJourneyNarratives: vi.fn(),
    approveJourneyNarratives: vi.fn(),
    startJourneyMining: vi.fn(),
    startJourneyReview: vi.fn(),
    sendJourneyReviewMessage: vi.fn(),
    applyJourneyReviewChanges: vi.fn(),
  },
}));

vi.mock('../components/ClientAnalysisView', () => ({
  default: ({ projectId, onBack }) => (
    <div data-testid="analysis-view">
      Analysis for {projectId}
      <button onClick={onBack}>Back</button>
    </div>
  ),
}));
vi.mock('../components/JourneyTimeline', () => ({
  default: () => <div data-testid="journey-timeline">Timeline</div>,
}));
vi.mock('../components/JourneySkills', () => ({
  default: () => <div data-testid="journey-skills">Skills</div>,
}));
vi.mock('../components/JourneyNarratives', () => ({
  default: () => <div data-testid="journey-narratives">Narratives</div>,
}));

import ProjectAnalyzer from '../components/ProjectAnalyzer';
import AnalysisApproval from '../components/AnalysisApproval';
import JourneyMiner from '../components/JourneyMiner';

// ---------------------------------------------------------------------------
// ProjectAnalyzer Tests
// ---------------------------------------------------------------------------
describe('ProjectAnalyzer', () => {
  beforeEach(() => vi.clearAllMocks());

  test('renders heading', async () => {
    const api = (await import('../services/api')).default;
    api.listClientProjects.mockResolvedValue({ projects: [] });
    await act(async () => { render(<ProjectAnalyzer />); });
    expect(screen.getByText('Client Project Analysis')).toBeInTheDocument();
  });

  test('renders Add Client Project button', async () => {
    const api = (await import('../services/api')).default;
    api.listClientProjects.mockResolvedValue({ projects: [] });
    await act(async () => { render(<ProjectAnalyzer />); });
    expect(screen.getByText('+ Add Client Project')).toBeInTheDocument();
  });

  test('shows empty state when no projects', async () => {
    const api = (await import('../services/api')).default;
    api.listClientProjects.mockResolvedValue({ projects: [] });
    await act(async () => { render(<ProjectAnalyzer />); });
    await waitFor(() => {
      expect(screen.getByText('No client projects yet')).toBeInTheDocument();
    });
  });

  test('renders project cards when projects exist', async () => {
    const api = (await import('../services/api')).default;
    api.listClientProjects.mockResolvedValue({
      projects: [
        { id: 1, client_name: 'Acme Corp', analysis_status: 'pending', document_count: 5 },
      ],
    });
    await act(async () => { render(<ProjectAnalyzer />); });
    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });
  });

  test('shows Start Analysis button for pending project', async () => {
    const api = (await import('../services/api')).default;
    api.listClientProjects.mockResolvedValue({
      projects: [
        { id: 1, client_name: 'Test', analysis_status: 'pending', document_count: 3 },
      ],
    });
    await act(async () => { render(<ProjectAnalyzer />); });
    await waitFor(() => {
      expect(screen.getByText('Start Analysis')).toBeInTheDocument();
    });
  });

  test('shows View Analysis for completed project', async () => {
    const api = (await import('../services/api')).default;
    api.listClientProjects.mockResolvedValue({
      projects: [
        { id: 1, client_name: 'Done', analysis_status: 'completed', document_count: 10 },
      ],
    });
    await act(async () => { render(<ProjectAnalyzer />); });
    await waitFor(() => {
      expect(screen.getByText('View Analysis')).toBeInTheDocument();
    });
  });

  test('Add button opens folder browser modal', async () => {
    const api = (await import('../services/api')).default;
    api.listClientProjects.mockResolvedValue({ projects: [] });
    api.listDriveFolders.mockResolvedValue({ folders: [] });
    await act(async () => { render(<ProjectAnalyzer />); });
    fireEvent.click(screen.getByText('+ Add Client Project'));
    await waitFor(() => {
      expect(screen.getByText('Select Project Folder')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// AnalysisApproval Tests
// ---------------------------------------------------------------------------
describe('AnalysisApproval', () => {
  const mockApprove = vi.fn();
  const mockCancel = vi.fn();

  test('renders approval dialog', () => {
    render(
      <AnalysisApproval
        clientName="TestCo"
        techCount={12}
        govCount={5}
        roleCount={8}
        onApprove={mockApprove}
        onCancel={mockCancel}
      />
    );
    expect(screen.getByText('Approve & Store in Knowledge Graph')).toBeInTheDocument();
  });

  test('displays client name', () => {
    render(
      <AnalysisApproval
        clientName="BigCorp"
        techCount={10}
        govCount={3}
        roleCount={7}
        onApprove={mockApprove}
        onCancel={mockCancel}
      />
    );
    expect(screen.getByText(/BigCorp/)).toBeInTheDocument();
  });

  test('displays counts', () => {
    render(
      <AnalysisApproval
        clientName="X"
        techCount={15}
        govCount={6}
        roleCount={9}
        onApprove={mockApprove}
        onCancel={mockCancel}
      />
    );
    expect(screen.getByText(/15/)).toBeInTheDocument();
    expect(screen.getByText(/technologies/)).toBeInTheDocument();
    expect(screen.getByText(/6/)).toBeInTheDocument();
    expect(screen.getByText(/governance controls/)).toBeInTheDocument();
    expect(screen.getByText(/9/)).toBeInTheDocument();
    expect(screen.getByText(/role contributions/)).toBeInTheDocument();
  });

  test('Cancel button calls onCancel', () => {
    render(
      <AnalysisApproval
        clientName="X"
        techCount={0}
        govCount={0}
        roleCount={0}
        onApprove={mockApprove}
        onCancel={mockCancel}
      />
    );
    fireEvent.click(screen.getByText('Cancel'));
    expect(mockCancel).toHaveBeenCalledTimes(1);
  });

  test('Approve button calls onApprove', () => {
    render(
      <AnalysisApproval
        clientName="X"
        techCount={0}
        govCount={0}
        roleCount={0}
        onApprove={mockApprove}
        onCancel={mockCancel}
      />
    );
    fireEvent.click(screen.getByText('Approve & Store'));
    expect(mockApprove).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// JourneyMiner Tests
// ---------------------------------------------------------------------------
describe('JourneyMiner', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const api = (await import('../services/api')).default;
    api.getJourneyTimeline.mockResolvedValue({ events: [], total: 0 });
    api.getJourneySkills.mockResolvedValue({ skills: [] });
    api.getJourneyAchievements.mockResolvedValue({ achievements: [] });
  });

  test('renders heading', async () => {
    await act(async () => { render(<JourneyMiner />); });
    expect(screen.getByText('AI Journey Knowledge Mining')).toBeInTheDocument();
  });

  test('renders Start Mining button', async () => {
    await act(async () => { render(<JourneyMiner />); });
    expect(screen.getByText('Start Mining')).toBeInTheDocument();
  });

  test('renders sub-navigation tabs', async () => {
    await act(async () => { render(<JourneyMiner />); });
    // "Timeline" appears in both tab button and mocked component
    expect(screen.getAllByText('Timeline').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Skills')).toBeInTheDocument();
    expect(screen.getByText('Narratives')).toBeInTheDocument();
  });

  test('default sub-view is Timeline', async () => {
    await act(async () => { render(<JourneyMiner />); });
    await waitFor(() => {
      expect(screen.getByTestId('journey-timeline')).toBeInTheDocument();
    });
  });

  test('tab switching renders Skills sub-view', async () => {
    await act(async () => { render(<JourneyMiner />); });
    fireEvent.click(screen.getByText('Skills'));
    await waitFor(() => {
      expect(screen.getByTestId('journey-skills')).toBeInTheDocument();
    });
  });

  test('tab switching renders Narratives sub-view', async () => {
    await act(async () => { render(<JourneyMiner />); });
    fireEvent.click(screen.getByText('Narratives'));
    await waitFor(() => {
      expect(screen.getByTestId('journey-narratives')).toBeInTheDocument();
    });
  });

  test('shows stats when events exist', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyTimeline.mockResolvedValue({ events: [{}], total: 42 });
    api.getJourneySkills.mockResolvedValue({ skills: Array.from({ length: 15 }, (_, i) => ({ name: `skill${i}` })) });
    api.getJourneyAchievements.mockResolvedValue({ achievements: Array.from({ length: 8 }, (_, i) => ({ text: `ach${i}` })) });
    await act(async () => { render(<JourneyMiner />); });
    await waitFor(() => {
      expect(screen.getByText('Timeline Events')).toBeInTheDocument();
      expect(screen.getByText('Skills Tracked')).toBeInTheDocument();
      expect(screen.getByText('Achievements')).toBeInTheDocument();
    });
  });

  test('Start Mining calls API', async () => {
    const api = (await import('../services/api')).default;
    api.startJourneyMining.mockResolvedValue({ job_id: 'j1' });
    api.getJobStatus.mockResolvedValue({ status: 'completed' });
    await act(async () => { render(<JourneyMiner />); });
    fireEvent.click(screen.getByText('Start Mining'));
    await waitFor(() => {
      expect(api.startJourneyMining).toHaveBeenCalled();
    });
  });
});
