import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// Mock API for all remaining component tests
vi.mock('../services/api', () => ({
  default: {
    getJourneyTimeline: vi.fn(),
    getJourneySkills: vi.fn(),
    getProjectAnalysis: vi.fn(),
    listProjectDocuments: vi.fn(),
    updateProjectAnalysis: vi.fn(),
    approveProjectAnalysis: vi.fn(),
    listGDriveFiles: vi.fn(),
    importGDriveFile: vi.fn(),
    getLinkedInUpdates: vi.fn(),
    generateLinkedInUpdate: vi.fn(),
    updateLinkedInSection: vi.fn(),
    compareLinkedIn: vi.fn(),
    getTemplates: vi.fn(),
    createTemplate: vi.fn(),
    updateTemplate: vi.fn(),
    deleteTemplate: vi.fn(),
    customizeTemplate: vi.fn(),
    downloadTemplate: vi.fn(),
  },
}));

import JourneyTimeline from '../components/JourneyTimeline';
import JourneySkills from '../components/JourneySkills';
import ClientAnalysisView from '../components/ClientAnalysisView';
import GDriveFilePicker from '../components/GDriveFilePicker';
import LinkedInProfileUpdate from '../components/LinkedInProfileUpdate';
import ResumeTemplates from '../components/ResumeTemplates';

// ---------------------------------------------------------------------------
// JourneyTimeline Tests
// ---------------------------------------------------------------------------
describe('JourneyTimeline', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  test('shows loading state initially', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyTimeline.mockReturnValue(new Promise(() => {}));
    render(<JourneyTimeline />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  test('shows empty state when no events', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyTimeline.mockResolvedValue({ events: [], total: 0 });
    render(<JourneyTimeline />);
    await waitFor(() => {
      expect(screen.getByText(/no timeline events/i)).toBeInTheDocument();
    });
  });

  test('renders category filter buttons', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyTimeline.mockResolvedValue({
      events: [{ id: 1, title: 'Built gateway', date: '2026-01-15', category: 'milestone', description: 'Created the AI gateway' }],
      total: 1,
    });
    render(<JourneyTimeline />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'all' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'milestone' })).toBeInTheDocument();
    });
  });

  test('renders event cards', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyTimeline.mockResolvedValue({
      events: [
        { id: 1, title: 'Built AI Gateway', date: '2026-01-15', category: 'milestone', description: 'Architected the entire gateway' },
        { id: 2, title: 'Fixed swap bug', date: '2026-02-01', category: 'fix', description: 'Resolved timeout issue' },
      ],
      total: 2,
    });
    render(<JourneyTimeline />);
    await waitFor(() => {
      expect(screen.getByText('Built AI Gateway')).toBeInTheDocument();
      expect(screen.getByText('Fixed swap bug')).toBeInTheDocument();
    });
  });

  test('calls API with page and category', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneyTimeline.mockResolvedValue({ events: [], total: 0 });
    render(<JourneyTimeline />);
    await waitFor(() => {
      expect(api.getJourneyTimeline).toHaveBeenCalledWith(1, 30, undefined);
    });
  });
});

// ---------------------------------------------------------------------------
// JourneySkills Tests
// ---------------------------------------------------------------------------
describe('JourneySkills', () => {
  beforeEach(() => vi.clearAllMocks());

  test('shows loading state', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneySkills.mockReturnValue(new Promise(() => {}));
    render(<JourneySkills />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  test('shows empty state when no skills', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneySkills.mockResolvedValue({ skills: [] });
    render(<JourneySkills />);
    await waitFor(() => {
      expect(screen.getByText(/no skills tracked/i)).toBeInTheDocument();
    });
  });

  test('renders skill cards with counts', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneySkills.mockResolvedValue({
      skills: [
        { name: 'Python', event_count: 42, first_seen: '2025-12-01', last_seen: '2026-03-10', categories: ['coding'] },
        { name: 'Docker', event_count: 18, first_seen: '2026-01-01', last_seen: '2026-03-08', categories: [] },
      ],
    });
    render(<JourneySkills />);
    await waitFor(() => {
      expect(screen.getByText('Python')).toBeInTheDocument();
      expect(screen.getByText('Docker')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();
      expect(screen.getByText('18')).toBeInTheDocument();
    });
  });

  test('renders sort buttons', async () => {
    const api = (await import('../services/api')).default;
    api.getJourneySkills.mockResolvedValue({
      skills: [{ name: 'Python', event_count: 10, first_seen: '2025-12-01', last_seen: '2026-03-01', categories: [] }],
    });
    render(<JourneySkills />);
    await waitFor(() => {
      expect(screen.getByText(/frequency/i)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// ClientAnalysisView Tests
// ---------------------------------------------------------------------------
describe('ClientAnalysisView', () => {
  const mockBack = vi.fn();

  beforeEach(async () => {
    vi.clearAllMocks();
    const api = (await import('../services/api')).default;
    api.getProjectAnalysis.mockResolvedValue({
      analysis_status: 'completed',
      client_name: 'Navitus Health',
      technical_analysis_json: JSON.stringify([
        { name: 'Python', category: 'language', description: 'Primary backend language' },
      ]),
      governance_analysis_json: JSON.stringify([
        { name: 'HIPAA', category: 'compliance', description: 'Healthcare compliance' },
      ]),
      role_analysis_json: JSON.stringify([
        { title: 'Lead Architect', contributions: ['Designed platform'] },
      ]),
      skills_json: '[]',
      outcomes_json: '[]',
    });
    api.listProjectDocuments.mockResolvedValue({ documents: [] });
  });

  test('renders client name', async () => {
    await act(async () => { render(<ClientAnalysisView projectId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText(/navitus health/i)).toBeInTheDocument();
    });
  });

  test('renders back button', async () => {
    await act(async () => { render(<ClientAnalysisView projectId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText(/navitus health/i)).toBeInTheDocument();
    });
    const backBtn = screen.getByRole('button', { name: /back/i });
    fireEvent.click(backBtn);
    expect(mockBack).toHaveBeenCalled();
  });

  test('renders technical analysis items', async () => {
    await act(async () => { render(<ClientAnalysisView projectId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText('Python')).toBeInTheDocument();
    });
  });

  test('renders governance analysis items', async () => {
    await act(async () => { render(<ClientAnalysisView projectId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText('HIPAA')).toBeInTheDocument();
    });
  });

  test('renders role analysis items', async () => {
    await act(async () => { render(<ClientAnalysisView projectId="1" onBack={mockBack} />); });
    await waitFor(() => {
      expect(screen.getByText('Lead Architect')).toBeInTheDocument();
    });
  });

  test('shows loading state initially', async () => {
    const api = (await import('../services/api')).default;
    // Use never-resolving promises so the component stays in loading state
    api.getProjectAnalysis.mockReturnValue(new Promise(() => {}));
    api.listProjectDocuments.mockReturnValue(new Promise(() => {}));
    render(<ClientAnalysisView projectId="1" onBack={mockBack} />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// GDriveFilePicker Tests
// ---------------------------------------------------------------------------
describe('GDriveFilePicker', () => {
  const mockImport = vi.fn();
  const mockClose = vi.fn();

  beforeEach(async () => {
    vi.clearAllMocks();
    const api = (await import('../services/api')).default;
    api.listGDriveFiles.mockResolvedValue({
      files: [
        { id: 'f1', name: 'Resume.pdf', mimeType: 'application/pdf', size: 102400, modifiedTime: '2026-03-01T10:00:00Z' },
        { id: 'f2', name: 'Documents', mimeType: 'application/vnd.google-apps.folder', size: 0, modifiedTime: '2026-03-01T10:00:00Z' },
      ],
    });
  });

  test('renders file list', async () => {
    render(<GDriveFilePicker onImport={mockImport} onClose={mockClose} />);
    await waitFor(() => {
      expect(screen.getByText('Resume.pdf')).toBeInTheDocument();
      expect(screen.getByText('Documents')).toBeInTheDocument();
    });
  });

  test('renders close button', async () => {
    render(<GDriveFilePicker onImport={mockImport} onClose={mockClose} />);
    await waitFor(() => {
      expect(screen.getByText('Resume.pdf')).toBeInTheDocument();
    });
    const closeBtn = screen.getByText('×');
    fireEvent.click(closeBtn);
    expect(mockClose).toHaveBeenCalled();
  });

  test('renders Import button', async () => {
    render(<GDriveFilePicker onImport={mockImport} onClose={mockClose} />);
    await waitFor(() => {
      expect(screen.getByText('Import')).toBeInTheDocument();
    });
  });

  test('renders Cancel button', async () => {
    render(<GDriveFilePicker onImport={mockImport} onClose={mockClose} />);
    await waitFor(() => {
      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });
  });

  test('shows empty state when no files', async () => {
    const api = (await import('../services/api')).default;
    api.listGDriveFiles.mockResolvedValue({ files: [] });
    render(<GDriveFilePicker onImport={mockImport} onClose={mockClose} />);
    await waitFor(() => {
      expect(screen.getByText(/empty/i)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// LinkedInProfileUpdate Tests
// ---------------------------------------------------------------------------
describe('LinkedInProfileUpdate', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  test('renders Generate Updates button', async () => {
    const api = (await import('../services/api')).default;
    api.getLinkedInUpdates.mockResolvedValue({ data: { updates: [] } });
    render(<LinkedInProfileUpdate />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /generate updates/i })).toBeInTheDocument();
    });
  });

  test('shows empty state when no updates', async () => {
    const api = (await import('../services/api')).default;
    api.getLinkedInUpdates.mockResolvedValue({ data: { updates: [] } });
    render(<LinkedInProfileUpdate />);
    await waitFor(() => {
      expect(screen.getByText(/no.*update/i)).toBeInTheDocument();
    });
  });

  test('renders update cards when loaded', async () => {
    const api = (await import('../services/api')).default;
    api.getLinkedInUpdates.mockResolvedValue({
      data: {
        updates: [
          { id: 1, section_name: 'Headline', current_content: 'Old headline', suggested_content: 'New headline', status: 'pending' },
        ],
      },
    });
    render(<LinkedInProfileUpdate />);
    await waitFor(() => {
      expect(screen.getByText('Headline')).toBeInTheDocument();
      expect(screen.getByText(/new headline/i)).toBeInTheDocument();
    });
  });

  test('shows Accept/Reject buttons for pending items', async () => {
    const api = (await import('../services/api')).default;
    api.getLinkedInUpdates.mockResolvedValue({
      data: {
        updates: [
          { id: 1, section_name: 'Summary', current_content: 'Old', suggested_content: 'New', status: 'pending' },
        ],
      },
    });
    render(<LinkedInProfileUpdate />);
    await waitFor(() => {
      expect(screen.getByText('Accept')).toBeInTheDocument();
      expect(screen.getByText('Reject')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// ResumeTemplates Tests
// ---------------------------------------------------------------------------
describe('ResumeTemplates', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  test('renders New Template button', async () => {
    const api = (await import('../services/api')).default;
    api.getTemplates.mockResolvedValue({ data: { templates: [] } });
    render(<ResumeTemplates />);
    await waitFor(() => {
      expect(screen.getByText(/new template/i)).toBeInTheDocument();
    });
  });

  test('renders template list when loaded', async () => {
    const api = (await import('../services/api')).default;
    api.getTemplates.mockResolvedValue({
      data: {
        templates: [
          { id: 1, name: 'Executive Template', role_type: 'executive', base_content: 'Professional summary...' },
        ],
      },
    });
    render(<ResumeTemplates />);
    await waitFor(() => {
      expect(screen.getByText('Executive Template')).toBeInTheDocument();
      expect(screen.getAllByText(/executive/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  test('shows create form when New Template clicked', async () => {
    const api = (await import('../services/api')).default;
    api.getTemplates.mockResolvedValue({ data: { templates: [] } });
    render(<ResumeTemplates />);
    await waitFor(() => {
      expect(screen.getByText(/new template/i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/new template/i));
    await waitFor(() => {
      expect(screen.getByText('Create Template')).toBeInTheDocument();
    });
  });

  test('renders Edit and Delete buttons on template cards', async () => {
    const api = (await import('../services/api')).default;
    api.getTemplates.mockResolvedValue({
      data: {
        templates: [
          { id: 1, name: 'Test Template', role_type: 'general', base_content: 'Content here...' },
        ],
      },
    });
    render(<ResumeTemplates />);
    await waitFor(() => {
      expect(screen.getByText('Edit')).toBeInTheDocument();
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });
  });

  test('renders Customize button', async () => {
    const api = (await import('../services/api')).default;
    api.getTemplates.mockResolvedValue({
      data: {
        templates: [
          { id: 1, name: 'Test', role_type: 'general', base_content: 'Content' },
        ],
      },
    });
    render(<ResumeTemplates />);
    await waitFor(() => {
      expect(screen.getByText('Customize')).toBeInTheDocument();
    });
  });
});
