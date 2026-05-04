import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  default: {
    listGDriveFiles: vi.fn(),
    getResumeVersions: vi.fn(),
    importGDriveFile: vi.fn(),
    reimportGDriveFile: vi.fn(),
    getResumeVersion: vi.fn(),
    updateResumeVersion: vi.fn(),
    startExperienceSession: vi.fn(),
    sendExperienceMessage: vi.fn(),
    getExperienceSummary: vi.fn(),
    finalizeExperience: vi.fn(),
    applyExperience: vi.fn(),
    getBuilderSources: vi.fn(),
    startBuilderSession: vi.fn(),
  },
}));

vi.mock('../components/GDriveFilePicker', () => ({
  default: () => <div data-testid="gdrive-picker">GDriveFilePicker</div>,
}));
vi.mock('../components/SourceSelector', () => ({
  default: () => <div data-testid="source-selector">SourceSelector</div>,
}));
vi.mock('../components/BuilderInterview', () => ({
  default: () => <div data-testid="builder-interview">BuilderInterview</div>,
}));
vi.mock('../components/BuilderPreview', () => ({
  default: () => <div data-testid="builder-preview">BuilderPreview</div>,
}));

import GoogleDriveImport from '../components/GoogleDriveImport';
import ExperienceChat from '../components/ExperienceChat';
import ResumeBuilder from '../components/ResumeBuilder';

// ---------------------------------------------------------------------------
// GoogleDriveImport Tests
// ---------------------------------------------------------------------------
describe('GoogleDriveImport', () => {
  beforeEach(() => vi.clearAllMocks());

  test('renders heading', async () => {
    const api = (await import('../services/api')).default;
    api.listGDriveFiles.mockResolvedValue({ files: [] });
    api.getResumeVersions.mockResolvedValue({ versions: [] });
    await act(async () => { render(<GoogleDriveImport onResumeImported={vi.fn()} />); });
    expect(screen.getByText('Import from Google Drive')).toBeInTheDocument();
  });

  test('shows loading state', async () => {
    const api = (await import('../services/api')).default;
    api.listGDriveFiles.mockReturnValue(new Promise(() => {}));
    api.getResumeVersions.mockReturnValue(new Promise(() => {}));
    render(<GoogleDriveImport onResumeImported={vi.fn()} />);
    expect(screen.getByText('Loading files...')).toBeInTheDocument();
  });

  test('shows empty state when no files', async () => {
    const api = (await import('../services/api')).default;
    api.listGDriveFiles.mockResolvedValue({ files: [] });
    api.getResumeVersions.mockResolvedValue({ versions: [] });
    await act(async () => { render(<GoogleDriveImport onResumeImported={vi.fn()} />); });
    await waitFor(() => {
      expect(screen.getByText('No files found in Resumes folder')).toBeInTheDocument();
    });
  });

  test('renders files when loaded', async () => {
    const api = (await import('../services/api')).default;
    api.listGDriveFiles.mockResolvedValue({
      files: [
        { id: 'f1', name: 'resume.pdf', mimeType: 'application/pdf', size: 1024, modifiedTime: '2026-01-01', supported: true },
      ],
    });
    api.getResumeVersions.mockResolvedValue({ versions: [] });
    await act(async () => { render(<GoogleDriveImport onResumeImported={vi.fn()} />); });
    await waitFor(() => {
      expect(screen.getByText('resume.pdf')).toBeInTheDocument();
    });
  });

  test('renders panel headers', async () => {
    const api = (await import('../services/api')).default;
    api.listGDriveFiles.mockResolvedValue({ files: [] });
    api.getResumeVersions.mockResolvedValue({ versions: [] });
    await act(async () => { render(<GoogleDriveImport onResumeImported={vi.fn()} />); });
    await waitFor(() => {
      expect(screen.getByText('Resumes Folder')).toBeInTheDocument();
      expect(screen.getByText('Imported Versions')).toBeInTheDocument();
    });
  });

  test('shows empty versions state', async () => {
    const api = (await import('../services/api')).default;
    api.listGDriveFiles.mockResolvedValue({ files: [] });
    api.getResumeVersions.mockResolvedValue({ versions: [] });
    await act(async () => { render(<GoogleDriveImport onResumeImported={vi.fn()} />); });
    await waitFor(() => {
      expect(screen.getByText('No imported resumes yet')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// ExperienceChat Tests
// ---------------------------------------------------------------------------
describe('ExperienceChat', () => {
  const mockOnCreated = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  test('renders start form with heading', () => {
    render(<ExperienceChat onExperienceCreated={mockOnCreated} />);
    expect(screen.getByText('Experience Interview')).toBeInTheDocument();
    expect(screen.getByText(/Tell us about a work experience/)).toBeInTheDocument();
  });

  test('renders employer and client fields', () => {
    render(<ExperienceChat onExperienceCreated={mockOnCreated} />);
    expect(screen.getByPlaceholderText(/e.g., PwC, Google/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e.g., Major Bank/)).toBeInTheDocument();
  });

  test('renders Start Interview button', () => {
    render(<ExperienceChat onExperienceCreated={mockOnCreated} />);
    expect(screen.getByText('Start Interview')).toBeInTheDocument();
  });

  test('Start Interview button starts session', async () => {
    const api = (await import('../services/api')).default;
    api.startExperienceSession.mockResolvedValue({
      session_id: 's1',
      stage: 'intro',
      message: 'Welcome! Tell me about your role.',
    });
    render(<ExperienceChat onExperienceCreated={mockOnCreated} />);
    fireEvent.change(screen.getByPlaceholderText(/e.g., PwC/), { target: { value: 'Acme Corp' } });
    fireEvent.click(screen.getByText('Start Interview'));
    await waitFor(() => {
      expect(api.startExperienceSession).toHaveBeenCalledWith('Acme Corp', '');
      expect(screen.getByText(/Welcome! Tell me about your role/)).toBeInTheDocument();
    });
  });

  test('shows stage progress after session starts', async () => {
    const api = (await import('../services/api')).default;
    api.startExperienceSession.mockResolvedValue({
      session_id: 's1',
      stage: 'role',
      message: 'What is your title?',
    });
    render(<ExperienceChat onExperienceCreated={mockOnCreated} />);
    fireEvent.change(screen.getByPlaceholderText(/e.g., PwC/), { target: { value: 'TestCo' } });
    fireEvent.click(screen.getByText('Start Interview'));
    await waitFor(() => {
      expect(screen.getByText('role')).toBeInTheDocument();
      expect(screen.getByText('responsibilities')).toBeInTheDocument();
    });
  });

  test('renders chat input after session starts', async () => {
    const api = (await import('../services/api')).default;
    api.startExperienceSession.mockResolvedValue({
      session_id: 's1',
      stage: 'intro',
      message: 'Hello',
    });
    render(<ExperienceChat onExperienceCreated={mockOnCreated} />);
    fireEvent.change(screen.getByPlaceholderText(/e.g., PwC/), { target: { value: 'Co' } });
    fireEvent.click(screen.getByText('Start Interview'));
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your response...')).toBeInTheDocument();
      expect(screen.getByText('Send')).toBeInTheDocument();
    });
  });

  test('renders sidebar with Extracted Data', async () => {
    const api = (await import('../services/api')).default;
    api.startExperienceSession.mockResolvedValue({
      session_id: 's1',
      stage: 'intro',
      message: 'Hello',
    });
    render(<ExperienceChat onExperienceCreated={mockOnCreated} />);
    fireEvent.change(screen.getByPlaceholderText(/e.g., PwC/), { target: { value: 'Co' } });
    fireEvent.click(screen.getByText('Start Interview'));
    await waitFor(() => {
      expect(screen.getByText('Extracted Data')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// ResumeBuilder Tests
// ---------------------------------------------------------------------------
describe('ResumeBuilder', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const api = (await import('../services/api')).default;
    api.getResumeVersions.mockResolvedValue({ versions: [] });
    api.getBuilderSources.mockResolvedValue({
      linkedin: { available: false },
      projects: { available: false },
      journey: { available: false },
      experiences: { available: false },
    });
  });

  test('renders heading', async () => {
    render(<ResumeBuilder />);
    await waitFor(() => {
      expect(screen.getByText('Resume Builder')).toBeInTheDocument();
    });
  });

  test('renders step indicators', async () => {
    render(<ResumeBuilder />);
    await waitFor(() => {
      expect(screen.getByText('Base Resume')).toBeInTheDocument();
      expect(screen.getByText('Choose Sources')).toBeInTheDocument();
      expect(screen.getByText('Interview')).toBeInTheDocument();
    });
  });

  test('renders Select Base Resume section', async () => {
    render(<ResumeBuilder />);
    await waitFor(() => {
      expect(screen.getByText(/Select Base Resume/)).toBeInTheDocument();
      expect(screen.getByText('Start Blank')).toBeInTheDocument();
    });
  });

  test('renders job description textarea', async () => {
    render(<ResumeBuilder />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Paste the full job description/)).toBeInTheDocument();
    });
  });

  test('Next button disabled when job text too short', async () => {
    render(<ResumeBuilder />);
    await waitFor(() => {
      const nextBtn = screen.getByText(/Next: Choose Sources/);
      expect(nextBtn).toBeDisabled();
    });
  });

  test('shows character count', async () => {
    render(<ResumeBuilder />);
    await waitFor(() => {
      expect(screen.getByText('0 characters')).toBeInTheDocument();
    });
  });

  test('Next button enabled with sufficient text', async () => {
    render(<ResumeBuilder />);
    await waitFor(() => {
      const textarea = screen.getByPlaceholderText(/Paste the full job description/);
      fireEvent.change(textarea, { target: { value: 'X'.repeat(55) } });
      const nextBtn = screen.getByText(/Next: Choose Sources/);
      expect(nextBtn).not.toBeDisabled();
    });
  });
});
