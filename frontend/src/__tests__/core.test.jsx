import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// Mock all child components that Dashboard imports to keep tests focused
vi.mock('../components/ResumeUpload', () => ({ default: () => <div data-testid="resume-upload">ResumeUpload</div> }));
vi.mock('../components/JobDescriptionInput', () => ({ default: () => <div data-testid="job-desc">JobDescriptionInput</div> }));
vi.mock('../components/OptimizedResumeView', () => ({ default: () => <div data-testid="optimized-view">OptimizedResumeView</div> }));
vi.mock('../components/SkillsGap', () => ({ default: () => <div data-testid="skills-gap">SkillsGap</div> }));
vi.mock('../components/GoogleDriveImport', () => ({ default: () => <div data-testid="gdrive">GoogleDriveImport</div> }));
vi.mock('../components/ExperienceChat', () => ({ default: () => <div data-testid="experience">ExperienceChat</div> }));
vi.mock('../components/ProjectAnalyzer', () => ({ default: () => <div data-testid="projects">ProjectAnalyzer</div> }));
vi.mock('../components/JourneyMiner', () => ({ default: () => <div data-testid="journey">JourneyMiner</div> }));
vi.mock('../components/CampaignManager', () => ({ default: () => <div data-testid="campaigns">CampaignManager</div> }));
vi.mock('../components/ResumeBuilder', () => ({ default: () => <div data-testid="builder">ResumeBuilder</div> }));
vi.mock('../components/DeepAnalysis', () => ({ default: () => <div data-testid="deep">DeepAnalysis</div> }));
vi.mock('../components/AgentDashboard', () => ({ default: () => <div data-testid="agents">AgentDashboard</div> }));
vi.mock('../components/Onboarding', () => ({ default: () => null }));

vi.mock('../services/api', () => ({
  default: {
    login: vi.fn(),
    register: vi.fn(),
    listSessions: vi.fn().mockResolvedValue({ sessions: [] }),
    getPipelineReminders: vi.fn().mockResolvedValue({ reminders: [] }),
  }
}));

import App from '../App';
import Login from '../components/Login';
import Dashboard from '../components/Dashboard';

// ---------------------------------------------------------------------------
// App.jsx Tests
// ---------------------------------------------------------------------------
describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  test('renders Login when not authenticated', async () => {
    await act(async () => { render(<App />); });
    expect(screen.getByText('Resume Optimizer')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter your email')).toBeInTheDocument();
  });

  test('renders Dashboard when user_id is in localStorage', async () => {
    localStorage.setItem('user_id', 'test-user');
    localStorage.setItem('auth_token', 'test-token');
    await act(async () => { render(<App />); });
    expect(screen.getByText('Optimize Resume')).toBeInTheDocument();
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });

  test('redirects / to /login when not authenticated', async () => {
    await act(async () => { render(<App />); });
    expect(screen.getByPlaceholderText('Enter your email')).toBeInTheDocument();
    expect(screen.queryByText('Logout')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Login.jsx Tests
// ---------------------------------------------------------------------------
describe('Login', () => {
  const mockOnLogin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders heading and login form fields', () => {
    render(<Login onLogin={mockOnLogin} />);
    expect(screen.getByText('Resume Optimizer')).toBeInTheDocument();
    expect(screen.getByText('Sign In')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter your email')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter your password')).toBeInTheDocument();
  });

  test('toggles between Sign In and Create Account modes', () => {
    render(<Login onLogin={mockOnLogin} />);
    expect(screen.getByText('Sign In')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Confirm your password')).not.toBeInTheDocument();

    // Click "Register" toggle link
    fireEvent.click(screen.getByText('Register'));
    expect(screen.getByText('Create Account')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Confirm your password')).toBeInTheDocument();
  });

  test('shows error when passwords do not match in register mode', async () => {
    render(<Login onLogin={mockOnLogin} />);
    fireEvent.click(screen.getByText('Register'));

    fireEvent.change(screen.getByPlaceholderText('Enter your email'), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm your password'), { target: { value: 'different' } });

    fireEvent.submit(screen.getByPlaceholderText('Enter your email').closest('form'));

    await waitFor(() => {
      expect(screen.getByText('Passwords do not match')).toBeInTheDocument();
    });
    expect(mockOnLogin).not.toHaveBeenCalled();
  });

  test('calls api.login and onLogin on successful sign in', async () => {
    const api = (await import('../services/api')).default;
    api.login.mockResolvedValue({ user_id: 'u1', token: 'tok1' });

    render(<Login onLogin={mockOnLogin} />);
    fireEvent.change(screen.getByPlaceholderText('Enter your email'), { target: { value: 'user@test.com' } });
    fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'pass123' } });
    fireEvent.submit(screen.getByPlaceholderText('Enter your email').closest('form'));

    await waitFor(() => {
      expect(api.login).toHaveBeenCalledWith('user@test.com', 'pass123');
      expect(mockOnLogin).toHaveBeenCalledWith('u1', 'tok1');
    });
  });

  test('shows error-message on failed login', async () => {
    const api = (await import('../services/api')).default;
    api.login.mockRejectedValue({ response: { data: { error: 'Invalid credentials' } } });

    render(<Login onLogin={mockOnLogin} />);
    fireEvent.change(screen.getByPlaceholderText('Enter your email'), { target: { value: 'bad@test.com' } });
    fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'wrong' } });
    fireEvent.submit(screen.getByPlaceholderText('Enter your email').closest('form'));

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });
    expect(mockOnLogin).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Dashboard.jsx Tests
// ---------------------------------------------------------------------------
describe('Dashboard', () => {
  const mockOnLogout = vi.fn();
  const mockUser = { id: 'test-user' };

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('ro_onboarding_seen', 'true');
  });

  test('renders all 9 tab buttons', async () => {
    await act(async () => { render(<Dashboard user={mockUser} onLogout={mockOnLogout} />); });

    const expectedTabs = [
      'Optimize Resume', 'Resume Builder', 'Google Drive',
      'Experience Interview', 'Client Projects', 'AI Journey',
      'Campaigns', 'Deep Analysis', 'AI Agents',
    ];
    expectedTabs.forEach(tab => {
      expect(screen.getByText(tab)).toBeInTheDocument();
    });
    expect(expectedTabs.length).toBe(9);
  });

  test('default tab is Optimize Resume with step indicator', async () => {
    await act(async () => { render(<Dashboard user={mockUser} onLogout={mockOnLogout} />); });
    const optimizeBtn = screen.getByText('Optimize Resume');
    expect(optimizeBtn.className).toContain('active');
    expect(screen.getByTestId('resume-upload')).toBeInTheDocument();
  });

  test('tab switching renders correct content', async () => {
    await act(async () => { render(<Dashboard user={mockUser} onLogout={mockOnLogout} />); });
    fireEvent.click(screen.getByText('AI Agents'));
    expect(screen.getByTestId('agents')).toBeInTheDocument();
    expect(screen.queryByTestId('resume-upload')).not.toBeInTheDocument();
  });

  test('step indicator shows 3 steps', async () => {
    await act(async () => { render(<Dashboard user={mockUser} onLogout={mockOnLogout} />); });
    expect(screen.getByText('Upload Resume')).toBeInTheDocument();
    expect(screen.getByText('Job Description')).toBeInTheDocument();
    expect(screen.getByText('Optimized Resume')).toBeInTheDocument();
  });

  test('header contains Resume Optimizer title and Logout', async () => {
    await act(async () => { render(<Dashboard user={mockUser} onLogout={mockOnLogout} />); });
    expect(screen.getByText('Resume Optimizer')).toBeInTheDocument();
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });

  test('Logout button calls onLogout', async () => {
    await act(async () => { render(<Dashboard user={mockUser} onLogout={mockOnLogout} />); });
    fireEvent.click(screen.getByText('Logout'));
    expect(mockOnLogout).toHaveBeenCalledTimes(1);
    expect(mockOnLogout).toHaveBeenCalled();
  });

  test('Guide button is rendered', async () => {
    await act(async () => { render(<Dashboard user={mockUser} onLogout={mockOnLogout} />); });
    expect(screen.getByText('Guide')).toBeInTheDocument();
    expect(screen.getByText('Guide').tagName).toBe('BUTTON');
  });

  // Phase 17.10: Reminder badge
  test('shows reminder badge on AI Agents tab when reminders exist', async () => {
    const api = (await import('../services/api')).default;
    api.getPipelineReminders.mockResolvedValue({
      reminders: [
        { id: 'r1', title: 'Dev', company: 'Co', updated_at: '2026-03-10' },
        { id: 'r2', title: 'Eng', company: 'Co2', updated_at: '2026-03-10' },
      ],
    });

    await act(async () => { render(<Dashboard user={mockUser} onLogout={mockOnLogout} />); });
    // Wait for reminder count to load
    await act(async () => { await new Promise(r => setTimeout(r, 50)); });

    // The AI Agents button should contain the badge count "2"
    const agentsBtn = screen.getByText('AI Agents');
    expect(agentsBtn.parentElement.textContent).toContain('2');
  });

  test('no reminder badge when reminders are empty', async () => {
    const api = (await import('../services/api')).default;
    api.getPipelineReminders.mockResolvedValue({ reminders: [] });

    await act(async () => { render(<Dashboard user={mockUser} onLogout={mockOnLogout} />); });
    await act(async () => { await new Promise(r => setTimeout(r, 50)); });

    // AI Agents button should NOT have a badge
    const agentsBtn = screen.getByText('AI Agents');
    // The button text should just be "AI Agents" without any number
    expect(agentsBtn.textContent).toBe('AI Agents');
  });

  test('dismissed reminders are filtered from badge count', async () => {
    const api = (await import('../services/api')).default;
    // Pre-dismiss r1 in localStorage
    localStorage.setItem('ro_dismissed_reminders', JSON.stringify(['r1']));
    api.getPipelineReminders.mockResolvedValue({
      reminders: [
        { id: 'r1', title: 'Dev', company: 'Co', updated_at: '2026-03-10' },
        { id: 'r2', title: 'Eng', company: 'Co2', updated_at: '2026-03-10' },
      ],
    });

    await act(async () => { render(<Dashboard user={mockUser} onLogout={mockOnLogout} />); });
    await act(async () => { await new Promise(r => setTimeout(r, 50)); });

    // Only r2 should count (r1 dismissed)
    const agentsBtn = screen.getByText('AI Agents');
    expect(agentsBtn.parentElement.textContent).toContain('1');
    // Clean up
    localStorage.removeItem('ro_dismissed_reminders');
  });
});
