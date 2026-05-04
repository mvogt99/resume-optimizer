/**
 * Onboarding wizard tests (Phase 17.15).
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

import Onboarding from '../components/Onboarding';

describe('Onboarding Wizard', () => {
  const mockDismiss = vi.fn();
  const mockNavigate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.removeItem('ro_onboarding_seen');
  });

  test('renders welcome step initially', () => {
    render(<Onboarding onDismiss={mockDismiss} onNavigate={mockNavigate} />);
    expect(screen.getByText('Welcome to Resume Optimizer')).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeInTheDocument();
    expect(screen.getByText('1 of 6')).toBeInTheDocument();
  });

  test('Next advances through all 6 steps', () => {
    render(<Onboarding onDismiss={mockDismiss} onNavigate={mockNavigate} />);
    // Step 1: Welcome
    expect(screen.getByText(/Welcome/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText(/Upload Your Resume/)).toBeInTheDocument();
    expect(screen.getByText('2 of 6')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText(/Import LinkedIn/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText(/Paste a Job Description/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText(/Build Your Deep Profile/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText(/Start Job Searching/)).toBeInTheDocument();
    expect(screen.getByText("I'm Ready!")).toBeInTheDocument();
  });

  test('Back button navigates backwards', () => {
    render(<Onboarding onDismiss={mockDismiss} onNavigate={mockNavigate} />);
    fireEvent.click(screen.getByText('Next')); // → step 2
    expect(screen.getByText(/Upload Your Resume/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Back'));
    expect(screen.getByText(/Welcome/)).toBeInTheDocument();
  });

  test('no Back button on first step', () => {
    render(<Onboarding onDismiss={mockDismiss} onNavigate={mockNavigate} />);
    expect(screen.queryByText('Back')).not.toBeInTheDocument();
  });

  test('action buttons navigate to correct tabs', () => {
    render(<Onboarding onDismiss={mockDismiss} onNavigate={mockNavigate} />);

    // Advance to step 6 (Job Searching — has unique action text)
    for (let i = 0; i < 5; i++) fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText(/Start Job Searching/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Go to AI Agents'));
    expect(mockNavigate).toHaveBeenCalledWith('agents');
  });

  test('Skip dismisses and sets localStorage', () => {
    render(<Onboarding onDismiss={mockDismiss} onNavigate={mockNavigate} />);
    fireEvent.click(screen.getByText('Skip'));
    expect(mockDismiss).toHaveBeenCalled();
    expect(localStorage.getItem('ro_onboarding_seen')).toBe('1');
  });

  test('completing all steps sets localStorage', () => {
    render(<Onboarding onDismiss={mockDismiss} onNavigate={mockNavigate} />);
    // Click through all steps
    for (let i = 0; i < 5; i++) fireEvent.click(screen.getByText('Next'));
    // Last step
    fireEvent.click(screen.getByText("I'm Ready!"));
    expect(mockDismiss).toHaveBeenCalled();
    expect(localStorage.getItem('ro_onboarding_seen')).toBe('1');
  });

  test('each action step has a green action button', () => {
    render(<Onboarding onDismiss={mockDismiss} onNavigate={mockNavigate} />);
    fireEvent.click(screen.getByText('Next')); // step 2
    expect(screen.getByText('Go to Upload')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Next')); // step 3
    expect(screen.getByText('Go to Upload (LinkedIn)')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Next')); // step 4
    expect(screen.getByText('Go to Optimize')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Next')); // step 5
    expect(screen.getByText('Go to Deep Analysis')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Next')); // step 6
    expect(screen.getByText('Go to AI Agents')).toBeInTheDocument();
  });
});
