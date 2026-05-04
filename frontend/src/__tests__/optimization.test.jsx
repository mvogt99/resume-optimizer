import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../components/GDriveFilePicker', () => ({
  default: ({ onImport, onClose }) => (
    <div data-testid="gdrive-picker">
      <button onClick={() => onImport('r1')}>MockImport</button>
      <button onClick={onClose}>MockClose</button>
    </div>
  ),
}));

vi.mock('../services/api', () => ({
  default: {
    getSkillsGap: vi.fn(),
    startAtsImprovement: vi.fn(),
  },
}));

import ResumeUpload from '../components/ResumeUpload';
import JobDescriptionInput from '../components/JobDescriptionInput';
import OptimizedResumeView from '../components/OptimizedResumeView';
import SkillsGap from '../components/SkillsGap';

// ---------------------------------------------------------------------------
// ResumeUpload Tests
// ---------------------------------------------------------------------------
describe('ResumeUpload', () => {
  const mockOnUpload = vi.fn();
  const mockOnLinkedIn = vi.fn();
  const mockOnGDrive = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  test('renders heading and subtitle', () => {
    render(<ResumeUpload onUpload={mockOnUpload} onLinkedInImport={mockOnLinkedIn} onGDriveImport={mockOnGDrive} />);
    expect(screen.getByText('Upload Your Resume')).toBeInTheDocument();
    expect(screen.getByText(/Upload a file, import from LinkedIn/)).toBeInTheDocument();
  });

  test('renders upload area with instructions', () => {
    render(<ResumeUpload onUpload={mockOnUpload} onLinkedInImport={mockOnLinkedIn} onGDriveImport={mockOnGDrive} />);
    expect(screen.getByText('Click to upload')).toBeInTheDocument();
    expect(screen.getByText(/PDF, DOCX, DOC, TXT/)).toBeInTheDocument();
  });

  test('renders LinkedIn and GDrive buttons', () => {
    render(<ResumeUpload onUpload={mockOnUpload} onLinkedInImport={mockOnLinkedIn} onGDriveImport={mockOnGDrive} />);
    expect(screen.getByText('Import from LinkedIn')).toBeInTheDocument();
    expect(screen.getByText('Browse Google Drive')).toBeInTheDocument();
  });

  test('LinkedIn button calls onLinkedInImport', () => {
    render(<ResumeUpload onUpload={mockOnUpload} onLinkedInImport={mockOnLinkedIn} onGDriveImport={mockOnGDrive} />);
    fireEvent.click(screen.getByText('Import from LinkedIn'));
    expect(mockOnLinkedIn).toHaveBeenCalledTimes(1);
  });

  test('LinkedIn button shows Importing... when loading', () => {
    render(<ResumeUpload onUpload={mockOnUpload} onLinkedInImport={mockOnLinkedIn} onGDriveImport={mockOnGDrive} loading={true} />);
    expect(screen.getByText('Importing...')).toBeInTheDocument();
  });

  test('GDrive button opens picker', () => {
    render(<ResumeUpload onUpload={mockOnUpload} onLinkedInImport={mockOnLinkedIn} onGDriveImport={mockOnGDrive} />);
    expect(screen.queryByTestId('gdrive-picker')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Browse Google Drive'));
    expect(screen.getByTestId('gdrive-picker')).toBeInTheDocument();
  });

  test('hidden file input accepts correct types', () => {
    render(<ResumeUpload onUpload={mockOnUpload} onLinkedInImport={mockOnLinkedIn} onGDriveImport={mockOnGDrive} />);
    const input = document.querySelector('input[type="file"]');
    expect(input).toBeTruthy();
    expect(input.accept).toBe('.pdf,.doc,.docx,.txt');
  });

  test('Continue button not shown without file selected', () => {
    render(<ResumeUpload onUpload={mockOnUpload} onLinkedInImport={mockOnLinkedIn} onGDriveImport={mockOnGDrive} />);
    expect(screen.queryByText('Continue')).not.toBeInTheDocument();
  });

  test('selecting a valid file shows file info and Continue button', () => {
    render(<ResumeUpload onUpload={mockOnUpload} onLinkedInImport={mockOnLinkedIn} onGDriveImport={mockOnGDrive} />);
    const input = document.querySelector('input[type="file"]');
    const file = new File(['resume content'], 'resume.pdf', { type: 'application/pdf' });
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getByText('resume.pdf')).toBeInTheDocument();
    expect(screen.getByText('Continue')).toBeInTheDocument();
  });

  test('Continue button calls onUpload with selected file', () => {
    render(<ResumeUpload onUpload={mockOnUpload} onLinkedInImport={mockOnLinkedIn} onGDriveImport={mockOnGDrive} />);
    const input = document.querySelector('input[type="file"]');
    const file = new File(['resume content'], 'resume.pdf', { type: 'application/pdf' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByText('Continue'));
    expect(mockOnUpload).toHaveBeenCalledWith(file);
  });
});

// ---------------------------------------------------------------------------
// JobDescriptionInput Tests
// ---------------------------------------------------------------------------
describe('JobDescriptionInput', () => {
  const mockOnSubmit = vi.fn();
  const mockOnBack = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  test('renders heading and subtitle', () => {
    render(<JobDescriptionInput onSubmit={mockOnSubmit} onBack={mockOnBack} />);
    expect(screen.getByText('Enter Job Description')).toBeInTheDocument();
    expect(screen.getByText(/Paste the job description/)).toBeInTheDocument();
  });

  test('Paste Text mode active by default', () => {
    render(<JobDescriptionInput onSubmit={mockOnSubmit} onBack={mockOnBack} />);
    const pasteBtn = screen.getByText(/Paste Text/);
    expect(pasteBtn.className).toContain('active');
    expect(screen.getByPlaceholderText(/Paste the complete job description/)).toBeInTheDocument();
  });

  test('toggle to Upload File mode', () => {
    render(<JobDescriptionInput onSubmit={mockOnSubmit} onBack={mockOnBack} />);
    fireEvent.click(screen.getByText(/Upload File/));
    expect(screen.getByText(/Upload job description file/)).toBeInTheDocument();
  });

  test('Optimize button disabled when text too short', () => {
    render(<JobDescriptionInput onSubmit={mockOnSubmit} onBack={mockOnBack} />);
    const optimizeBtn = screen.getByText(/Optimize Resume/);
    expect(optimizeBtn).toBeDisabled();
  });

  test('shows character count', () => {
    render(<JobDescriptionInput onSubmit={mockOnSubmit} onBack={mockOnBack} />);
    expect(screen.getByText('0 characters')).toBeInTheDocument();
  });

  test('shows minimum warning when text entered but too short', () => {
    render(<JobDescriptionInput onSubmit={mockOnSubmit} onBack={mockOnBack} />);
    const textarea = screen.getByPlaceholderText(/Paste the complete job description/);
    fireEvent.change(textarea, { target: { value: 'Short text' } });
    expect(screen.getByText(/minimum 50 required/)).toBeInTheDocument();
  });

  test('Optimize button enabled when text >= 50 chars', () => {
    render(<JobDescriptionInput onSubmit={mockOnSubmit} onBack={mockOnBack} />);
    const textarea = screen.getByPlaceholderText(/Paste the complete job description/);
    const longText = 'A'.repeat(60);
    fireEvent.change(textarea, { target: { value: longText } });
    const optimizeBtn = screen.getByText(/Optimize Resume/);
    expect(optimizeBtn).not.toBeDisabled();
  });

  test('Back button calls onBack', () => {
    render(<JobDescriptionInput onSubmit={mockOnSubmit} onBack={mockOnBack} />);
    fireEvent.click(screen.getByText(/Back/));
    expect(mockOnBack).toHaveBeenCalledTimes(1);
  });

  test('submit with sufficient text calls onSubmit', () => {
    render(<JobDescriptionInput onSubmit={mockOnSubmit} onBack={mockOnBack} />);
    const textarea = screen.getByPlaceholderText(/Paste the complete job description/);
    const longText = 'B'.repeat(60);
    fireEvent.change(textarea, { target: { value: longText } });
    fireEvent.click(screen.getByText(/Optimize Resume/));
    expect(mockOnSubmit).toHaveBeenCalledWith(longText);
  });

  test('renders with initialText prop', () => {
    const initial = 'C'.repeat(55);
    render(<JobDescriptionInput onSubmit={mockOnSubmit} onBack={mockOnBack} initialText={initial} />);
    const textarea = screen.getByPlaceholderText(/Paste the complete job description/);
    expect(textarea.value).toBe(initial);
  });
});

// ---------------------------------------------------------------------------
// OptimizedResumeView Tests
// ---------------------------------------------------------------------------
describe('OptimizedResumeView', () => {
  const mockStartOver = vi.fn();
  const mockData = {
    relevance_score: 72,
    optimized_resume: {
      optimized_text: 'Optimized resume text here',
      matching_keywords: ['Python', 'Flask'],
      added_keywords: ['Docker', 'Kubernetes'],
    },
    score_breakdown: {
      keyword_coverage: 75,
      semantic_similarity: 65,
      skills_match: 80,
      section_completeness: 90,
    },
    sections_found: { summary: true, experience: true, education: true, skills: true },
  };

  beforeEach(() => vi.clearAllMocks());

  test('renders heading', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} />);
    expect(screen.getByText('Your Optimized Resume')).toBeInTheDocument();
  });

  test('displays relevance score', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} />);
    expect(screen.getByText('72%')).toBeInTheDocument();
    expect(screen.getByText('Relevance Score')).toBeInTheDocument();
  });

  test('renders score breakdown rings', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} />);
    expect(screen.getByText('Keywords')).toBeInTheDocument();
    expect(screen.getByText('Relevance')).toBeInTheDocument();
    expect(screen.getByText('Skills')).toBeInTheDocument();
    expect(screen.getByText('Sections')).toBeInTheDocument();
  });

  test('renders matching keywords', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} />);
    expect(screen.getByText(/Matching Keywords/)).toBeInTheDocument();
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('Flask')).toBeInTheDocument();
  });

  test('renders missing keywords', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} />);
    expect(screen.getByText(/Missing Keywords/)).toBeInTheDocument();
    expect(screen.getByText('Docker')).toBeInTheDocument();
    expect(screen.getByText('Kubernetes')).toBeInTheDocument();
  });

  test('renders optimized resume text', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} />);
    expect(screen.getByText('Optimized resume text here')).toBeInTheDocument();
  });

  test('renders download buttons', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} resumeId="r1" />);
    expect(screen.getByText('PDF')).toBeInTheDocument();
    expect(screen.getByText('DOCX')).toBeInTheDocument();
    expect(screen.getByText('TXT')).toBeInTheDocument();
  });

  test('Optimize Another Resume button calls onStartOver', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} />);
    fireEvent.click(screen.getByText('Optimize Another Resume'));
    expect(mockStartOver).toHaveBeenCalledTimes(1);
  });

  test('renders Next Steps section', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} />);
    expect(screen.getByText('Next Steps')).toBeInTheDocument();
    expect(screen.getByText(/Review the optimized resume/)).toBeInTheDocument();
  });

  test('renders breakdown detail bars', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} />);
    expect(screen.getByText('Score Breakdown')).toBeInTheDocument();
    expect(screen.getByText('Keyword Coverage')).toBeInTheDocument();
    expect(screen.getByText('Semantic Relevance')).toBeInTheDocument();
    expect(screen.getByText('Skills Match')).toBeInTheDocument();
    expect(screen.getByText('Section Completeness')).toBeInTheDocument();
  });

  test('shows resume source badge when provided', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} resumeSource="linkedin" resumeName="linkedin_resume.pdf" />);
    expect(screen.getByText('LinkedIn')).toBeInTheDocument();
    expect(screen.getByText('linkedin_resume.pdf')).toBeInTheDocument();
  });

  test('renders Improve Score button when score < 100', () => {
    render(<OptimizedResumeView data={mockData} onStartOver={mockStartOver} resumeId="r1" />);
    expect(screen.getByText('Improve Score')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// SkillsGap Tests
// ---------------------------------------------------------------------------
describe('SkillsGap', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  test('shows loading state initially', async () => {
    const api = (await import('../services/api')).default;
    api.getSkillsGap.mockReturnValue(new Promise(() => {})); // never resolves
    render(<SkillsGap resumeId="r1" onClose={mockOnClose} />);
    expect(screen.getByText('Loading skills analysis...')).toBeInTheDocument();
  });

  test('shows error state on API failure', async () => {
    const api = (await import('../services/api')).default;
    api.getSkillsGap.mockRejectedValue(new Error('fail'));
    render(<SkillsGap resumeId="r1" onClose={mockOnClose} />);
    await waitFor(() => {
      expect(screen.getByText('Failed to fetch skills gap data')).toBeInTheDocument();
    });
  });

  test('renders skills analysis after loading', async () => {
    const api = (await import('../services/api')).default;
    api.getSkillsGap.mockResolvedValue({
      skills_gap: {
        coverage_percent: 65,
        total_job_keywords: 20,
        gap_summary: { shown: 10, can_add: 5, need_to_learn: 5 },
        skills_already_shown: [{ skill: 'Python', endorsements: 50 }],
        skills_to_emphasize: [{ skill: 'Docker', endorsements: 10 }],
        skills_to_acquire: [{ skill: 'Kubernetes', endorsements: 0 }],
      },
      relevant_accomplishments: [],
      relevant_recommendations: [],
    });
    render(<SkillsGap resumeId="r1" onClose={mockOnClose} />);
    await waitFor(() => {
      expect(screen.getByText('Skills Gap Analysis')).toBeInTheDocument();
    });
  });

  test('renders three skill columns', async () => {
    const api = (await import('../services/api')).default;
    api.getSkillsGap.mockResolvedValue({
      skills_gap: {
        coverage_percent: 65,
        total_job_keywords: 20,
        gap_summary: { shown: 10, can_add: 5, need_to_learn: 5 },
        skills_already_shown: [{ skill: 'Python', endorsements: 50 }],
        skills_to_emphasize: [{ skill: 'Docker', endorsements: 10 }],
        skills_to_acquire: [{ skill: 'Kubernetes', endorsements: 0 }],
      },
      relevant_accomplishments: [],
      relevant_recommendations: [],
    });
    render(<SkillsGap resumeId="r1" onClose={mockOnClose} />);
    await waitFor(() => {
      expect(screen.getByText('Already in Resume')).toBeInTheDocument();
      expect(screen.getByText('Add from LinkedIn')).toBeInTheDocument();
      expect(screen.getByText('Skills to Learn')).toBeInTheDocument();
    });
  });

  test('displays skill names in columns', async () => {
    const api = (await import('../services/api')).default;
    api.getSkillsGap.mockResolvedValue({
      skills_gap: {
        coverage_percent: 65,
        total_job_keywords: 20,
        gap_summary: { shown: 1, can_add: 1, need_to_learn: 1 },
        skills_already_shown: [{ skill: 'Python', endorsements: 50 }],
        skills_to_emphasize: [{ skill: 'Docker', endorsements: 10 }],
        skills_to_acquire: [{ skill: 'Kubernetes', endorsements: 0 }],
      },
      relevant_accomplishments: [],
      relevant_recommendations: [],
    });
    render(<SkillsGap resumeId="r1" onClose={mockOnClose} />);
    await waitFor(() => {
      expect(screen.getByText('Python')).toBeInTheDocument();
      expect(screen.getByText('Docker')).toBeInTheDocument();
      expect(screen.getByText('Kubernetes')).toBeInTheDocument();
    });
  });

  test('displays coverage percentage', async () => {
    const api = (await import('../services/api')).default;
    api.getSkillsGap.mockResolvedValue({
      skills_gap: {
        coverage_percent: 65,
        total_job_keywords: 20,
        gap_summary: { shown: 10, can_add: 5, need_to_learn: 5 },
        skills_already_shown: [],
        skills_to_emphasize: [],
        skills_to_acquire: [],
      },
      relevant_accomplishments: [],
      relevant_recommendations: [],
    });
    render(<SkillsGap resumeId="r1" onClose={mockOnClose} />);
    await waitFor(() => {
      expect(screen.getByText('65%')).toBeInTheDocument();
      expect(screen.getByText('Coverage')).toBeInTheDocument();
    });
  });

  test('displays gap stats', async () => {
    const api = (await import('../services/api')).default;
    api.getSkillsGap.mockResolvedValue({
      skills_gap: {
        coverage_percent: 65,
        total_job_keywords: 20,
        gap_summary: { shown: 10, can_add: 5, need_to_learn: 5 },
        skills_already_shown: [],
        skills_to_emphasize: [],
        skills_to_acquire: [],
      },
      relevant_accomplishments: [],
      relevant_recommendations: [],
    });
    render(<SkillsGap resumeId="r1" onClose={mockOnClose} />);
    await waitFor(() => {
      expect(screen.getByText('Job Keywords')).toBeInTheDocument();
      expect(screen.getByText('In Resume')).toBeInTheDocument();
      expect(screen.getByText('Can Add')).toBeInTheDocument();
      expect(screen.getByText('To Learn')).toBeInTheDocument();
    });
  });

  test('Adjust Skills button present', async () => {
    const api = (await import('../services/api')).default;
    api.getSkillsGap.mockResolvedValue({
      skills_gap: {
        coverage_percent: 50,
        total_job_keywords: 10,
        gap_summary: { shown: 5, can_add: 3, need_to_learn: 2 },
        skills_already_shown: [],
        skills_to_emphasize: [],
        skills_to_acquire: [],
      },
      relevant_accomplishments: [],
      relevant_recommendations: [],
    });
    render(<SkillsGap resumeId="r1" onClose={mockOnClose} />);
    await waitFor(() => {
      expect(screen.getByText('Adjust Skills')).toBeInTheDocument();
    });
  });
});
