import React, { useState } from 'react';
import '../styles/Onboarding.css';

const STEPS = [
  {
    title: 'Welcome to Resume Optimizer',
    description: 'Let\'s set up your profile in 5 quick steps. Each step builds on the last to give you the most powerful resume optimization.',
    icon: '\ud83d\ude80',
    action: null,
    actionLabel: null,
  },
  {
    title: 'Step 1: Get Your Resume Ready',
    description: 'You can either upload your current resume (PDF, DOCX, or TXT) for optimization, or build one from scratch with our guided interview if you don\'t have one yet. You can also import your LinkedIn profile or pull from Google Drive.',
    icon: '\ud83d\udcc4',
    action: 'optimize',
    actionLabel: 'Go to Upload',
    altAction: 'resume-interview',
    altActionLabel: 'Build from Scratch',
    tip: 'Already have a resume? Upload it for richer optimization. New to resumes? We\'ll help you build one step by step.',
  },
  {
    title: 'Step 2: Import LinkedIn Profile',
    description: 'Your LinkedIn profile provides 70+ skills with endorsement counts, recommendations, and work history — all of which improve scoring accuracy.',
    icon: '\ud83d\udd17',
    action: 'optimize',
    actionLabel: 'Go to Upload (LinkedIn)',
    tip: 'Upload a LinkedIn data export (JSON, XML, DOCX, PDF, or TXT) or use the one-click import.',
  },
  {
    title: 'Step 3: Paste a Job Description',
    description: 'Copy a job listing you\'re interested in. The optimizer compares your resume against the JD using NLP keyword matching, semantic similarity, and endorsement-weighted skills.',
    icon: '\ud83d\udcdd',
    action: 'optimize',
    actionLabel: 'Go to Optimize',
    tip: 'The more complete the JD, the more accurate the score. Include requirements, responsibilities, and qualifications.',
  },
  {
    title: 'Step 4: Build Your Deep Profile',
    description: 'The Deep Profile synthesizes all your data — LinkedIn, project documentation, AI journey, and extracted experiences — into career phases, higher-order skills, and differentiators.',
    icon: '\ud83e\udde0',
    action: 'deep-analysis',
    actionLabel: 'Go to Deep Analysis',
    tip: 'This powers salary intelligence, job scoring, and LinkedIn update suggestions.',
  },
  {
    title: 'Step 5: Start Job Searching',
    description: 'The AI Agents tab includes Job Scout (scrapes LinkedIn, Indeed, Glassdoor), Application Pipeline (Kanban tracker), Interview Coach, and Career Advisor — all running on your local GPU for free.',
    icon: '\ud83c\udfaf',
    action: 'agents',
    actionLabel: 'Go to AI Agents',
    tip: 'Use "Quick Apply" to automatically tailor your resume + generate a cover letter + prep for interviews in one click.',
  },
];

function Onboarding({ onDismiss, onNavigate }) {
  const [currentStep, setCurrentStep] = useState(0);

  const handleNext = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      localStorage.setItem('ro_onboarding_seen', '1');
      onDismiss();
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSkip = () => {
    localStorage.setItem('ro_onboarding_seen', '1');
    onDismiss();
  };

  const handleAction = (tabId) => {
    if (tabId && onNavigate) {
      localStorage.setItem('ro_onboarding_seen', '1');
      onNavigate(tabId);
    }
  };

  const step = STEPS[currentStep];
  const isLast = currentStep === STEPS.length - 1;
  const isFirst = currentStep === 0;

  return (
    <div className="onboarding-overlay" onClick={handleSkip}>
      <div className="onboarding-modal" onClick={(e) => e.stopPropagation()}>
        <button className="onboarding-skip" onClick={handleSkip}>
          Skip
        </button>

        <div className="onboarding-progress">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`onboarding-dot ${i === currentStep ? 'active' : ''} ${i < currentStep ? 'done' : ''}`}
            />
          ))}
        </div>

        <div className="onboarding-step-icon">{step.icon}</div>
        <h2 className="onboarding-title">{step.title}</h2>
        <p className="onboarding-desc">{step.description}</p>
        {step.tip && <p className="onboarding-tip">{step.tip}</p>}

        <div className="onboarding-actions">
          {!isFirst && (
            <button className="onboarding-back" onClick={handleBack}>
              Back
            </button>
          )}

          {step.action && (
            <button className="onboarding-action" onClick={() => handleAction(step.action)}>
              {step.actionLabel}
            </button>
          )}

          {step.altAction && (
            <button className="onboarding-action onboarding-alt-action" onClick={() => handleAction(step.altAction)}>
              {step.altActionLabel}
            </button>
          )}

          <button className="onboarding-next" onClick={handleNext}>
            {isLast ? "I'm Ready!" : 'Next'}
          </button>
        </div>

        <div className="onboarding-step-count">
          {currentStep + 1} of {STEPS.length}
        </div>
      </div>
    </div>
  );
}

export default Onboarding;
