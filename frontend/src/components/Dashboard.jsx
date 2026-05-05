import React, { useState, useEffect, useCallback, useRef } from 'react';
import ResumeUpload from './ResumeUpload';
import JobDescriptionInput from './JobDescriptionInput';
import OptimizedResumeView from './OptimizedResumeView';
import SkillsGap from './SkillsGap';
import GoogleDriveImport from './GoogleDriveImport';
import ExperienceChat from './ExperienceChat';
import ProjectAnalyzer from './ProjectAnalyzer';
import JourneyMiner from './JourneyMiner';
import CampaignManager from './CampaignManager';
import ResumeBuilder from './ResumeBuilder';
import ResumeInterview from './ResumeInterview';
import DeepAnalysis from './DeepAnalysis';
import AgentDashboard from './AgentDashboard';
import ResumeTemplates from './ResumeTemplates';
import AnalyticsDashboard from './AnalyticsDashboard';
import LinkedInProfileUpdate from './LinkedInProfileUpdate';
import InterviewCoachUI from './InterviewCoachUI';
import CoverLetterUI from './CoverLetterUI';
import VersionDiff from './VersionDiff';
import PortfolioShowcase from './PortfolioShowcase';
import RecommendationDrafter from './RecommendationDrafter';
import ResumeRecommendation from './ResumeRecommendation';
import CampaignAnalytics from './CampaignAnalytics';
import Onboarding from './Onboarding';
import PasswordReset from './PasswordReset';
import api from '../services/api';
import '../styles/Dashboard.css';

function Dashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState('optimize');

  // Optimize flow state
  const [step, setStep] = useState(1);
  const [resumeFile, setResumeFile] = useState(null);
  const [additionalResumeFiles, setAdditionalResumeFiles] = useState([]);
  const [additionalResumeIds, setAdditionalResumeIds] = useState([]);
  const [importedResumeId, setImportedResumeId] = useState(null);
  const [currentResumeId, setCurrentResumeId] = useState(null);
  const [optimizedResume, setOptimizedResume] = useState(null);
  const [jobDescText, setJobDescText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Resume comparison / recommendation (step 2.5)
  const [compareMode, setCompareMode] = useState('compare'); // 'compare' | 'merge'
  const [recommendation, setRecommendation] = useState(null);
  const [recommendationLoading, setRecommendationLoading] = useState(false);

  // Saved / local-file version IDs selected at step 1
  const [selectedVersionIds, setSelectedVersionIds] = useState([]);

  // Skills gap
  const [showSkillsGap, setShowSkillsGap] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(
    () => !localStorage.getItem('ro_onboarding_seen')
  );
  const [showPasswordReset, setShowPasswordReset] = useState(false);

  // Sessions
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  // Pipeline linkage: {sessionId: {id, title, company, status}}
  const [sessionPostings, setSessionPostings] = useState({});

  // Follow-up reminders (Phase 17.10)
  const [reminderCount, setReminderCount] = useState(0);
  const [dismissedReminders, setDismissedReminders] = useState(
    () => {
      try { return JSON.parse(localStorage.getItem('ro_dismissed_reminders') || '[]'); }
      catch { return []; }
    }
  );

  // Load follow-up reminders with polling + snooze/dismiss support
  const lastNotifiedCountRef = useRef(0);
  useEffect(() => {
    let cancelled = false;
    let intervalId = null;

    const checkReminders = async () => {
      try {
        const data = await api.getPipelineReminders();
        const allReminders = data.reminders || [];
        // Filter out dismissed reminders
        const active = allReminders.filter(r => !dismissedReminders.includes(r.id));
        if (!cancelled) {
          setReminderCount(active.length);
          // Fire browser notification only when count increases (avoid spam)
          if (
            active.length > 0 &&
            active.length > lastNotifiedCountRef.current &&
            'Notification' in window &&
            Notification.permission === 'granted'
          ) {
            new Notification('Resume Optimizer — Follow-up Reminders', {
              body: `${active.length} application(s) need follow-up`,
              icon: '/favicon.ico',
            });
          }
          lastNotifiedCountRef.current = active.length;
        }
      } catch {
        // ignore — reminders are optional
      }
    };

    // Request notification permission on first load
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    checkReminders();
    // Poll every 5 minutes (300000ms) — light endpoint, no LLM
    intervalId = setInterval(checkReminders, 300000);

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [dismissedReminders]); // re-run when dismissals change

  const dismissReminder = useCallback((reminderId) => {
    setDismissedReminders(prev => {
      const next = [...prev, reminderId];
      localStorage.setItem('ro_dismissed_reminders', JSON.stringify(next));
      return next;
    });
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const data = await api.listSessions();
      setSessions(data.sessions || []);
      // Load pipeline linkage in parallel — silently ignore failures
      api.getSessionPostingStatuses()
        .then(d => setSessionPostings(d.statuses || {}))
        .catch(() => {});
    } catch {
      // silently ignore — sessions are optional
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'optimize') {
      loadSessions();
    }
  }, [activeTab, loadSessions]);

  const handleResumeUpload = (file) => {
    setResumeFile(file);
    setAdditionalResumeFiles([]);
    setAdditionalResumeIds([]);
    setImportedResumeId(null);
    setStep(2);
    setError('');
  };

  const handleMultiUpload = (primaryFile, additionalFiles) => {
    setResumeFile(primaryFile);
    setAdditionalResumeFiles(additionalFiles);
    setAdditionalResumeIds([]);
    setImportedResumeId(null);
    setStep(2);
    setError('');
  };

  const handleLinkedInFileUpload = async (file) => {
    setLoading(true);
    setError('');
    try {
      await api.uploadLinkedInProfile(file);
      // After importing the profile, create a resume from it
      const result = await api.createResumeFromLinkedIn();
      setImportedResumeId(result.resume_id);
      setCurrentResumeId(result.resume_id);
      setResumeFile(null);
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to upload LinkedIn profile.');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const handleLinkedInImport = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await api.createResumeFromLinkedIn();
      setImportedResumeId(result.resume_id);
      setCurrentResumeId(result.resume_id);
      setResumeFile(null);
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to import LinkedIn profile.');
    } finally {
      setLoading(false);
    }
  };

  const handleGDriveResumeImport = (resumeId) => {
    setImportedResumeId(resumeId);
    setCurrentResumeId(resumeId);
    setResumeFile(null);
    setSelectedVersionIds([]);
    setStep(2);
    setError('');
  };

  // Step 1: user selected one or more saved resume versions from database
  const handleSavedResumeSelect = (versionIds) => {
    setSelectedVersionIds(versionIds);
    setImportedResumeId(null);
    setResumeFile(null);
    setAdditionalResumeFiles([]);
    setAdditionalResumeIds([]);
    setStep(2);
    setError('');
  };

  // Step 1: user imported one or more files from the local filesystem
  const handleLocalImport = (versionIds) => {
    setSelectedVersionIds(Array.isArray(versionIds) ? versionIds : [versionIds]);
    setImportedResumeId(null);
    setResumeFile(null);
    setAdditionalResumeFiles([]);
    setAdditionalResumeIds([]);
    setStep(2);
    setError('');
  };

  const handleJobDescriptionSubmit = async (jobDesc) => {
    setLoading(true);
    setError('');
    setJobDescText(jobDesc);

    try {
      // ── Version path: resumes selected from Saved Resumes or Local Folder ──
      if (selectedVersionIds.length > 0) {
        await api.uploadJobDescription(jobDesc);

        if (selectedVersionIds.length >= 2) {
          // Multi-version compare → step 2.5
          setLoading(false);
          setRecommendationLoading(true);
          setStep(2.5);
          try {
            const rec = await api.compareResumes({
              resumeVersionIds: selectedVersionIds,
              resumeIds: [],
              jobDescriptionText: jobDesc,
              skipRationale: false,
            });
            setRecommendation(rec);
          } catch {
            // Fall back to single-version optimize with the first one
            const result = await api.optimizeFromVersion(selectedVersionIds[0]);
            setOptimizedResume(result);
            setStep(3);
          } finally {
            setRecommendationLoading(false);
          }
          return;
        }

        // Single version
        const result = await api.optimizeFromVersion(selectedVersionIds[0]);
        setOptimizedResume(result);
        setCurrentResumeId(selectedVersionIds[0]);
        setStep(3);
        try {
          const sessionName = extractSessionName(jobDesc);
          const session = await api.createSession(sessionName, null, null, jobDesc);
          await api.updateSession(session.id, {
            optimization_result_json: JSON.stringify(result),
            ats_score: result.relevance_score || result.ats_compliance_score || 0,
            status: 'optimized',
          });
          setActiveSessionId(session.id);
          loadSessions();
        } catch { /* session save non-fatal */ }
        return;
      }

      // ── File / LinkedIn / GDrive path (existing flow) ────────────────────
      let resumeId = importedResumeId;

      if (!resumeId && resumeFile) {
        const resumeData = await api.uploadResume(resumeFile);
        resumeId = resumeData.resume_id;
      }

      if (!resumeId) {
        setError('No resume available. Please upload a file or import your LinkedIn profile.');
        setLoading(false);
        return;
      }

      // Upload additional resumes if provided
      let extraIds = [];
      if (additionalResumeFiles.length > 0) {
        try {
          const multiResult = await api.uploadMultipleResumes(additionalResumeFiles);
          extraIds = (multiResult.resumes || []).map(r => r.resume_id);
          setAdditionalResumeIds(extraIds);
        } catch {
          // Non-fatal — continue with primary resume only
        }
      }

      setCurrentResumeId(resumeId);
      await api.uploadJobDescription(jobDesc);

      // Step 2.5 — Multi-resume Compare mode: rank before optimizing
      const allIds = [resumeId, ...extraIds];
      if (compareMode === 'compare' && allIds.length > 1) {
        setLoading(false);
        setRecommendationLoading(true);
        setStep(2.5);
        try {
          const rec = await api.compareResumes({
            resumeIds: allIds,
            jobDescriptionText: jobDesc,
            skipRationale: false,
          });
          setRecommendation(rec);
        } catch {
          // Fall through to direct optimization on compare failure
          await _optimizeAndAdvance(resumeId, extraIds, jobDesc);
        } finally {
          setRecommendationLoading(false);
        }
        return;
      }

      const result = await api.optimizeResume(resumeId, extraIds.length > 0 ? extraIds : undefined);
      setOptimizedResume(result);
      setStep(3);

      // Auto-save to a new session with the optimization result
      try {
        const sessionName = extractSessionName(jobDesc);
        const session = await api.createSession(
          sessionName,
          resumeFile ? resumeId : null,
          importedResumeId || null,
          jobDesc,
        );
        // Save optimization result + score to the session
        await api.updateSession(session.id, {
          optimization_result_json: JSON.stringify(result),
          ats_score: result.relevance_score || result.ats_compliance_score || result.optimized_resume?.score || 0,
          status: 'optimized',
        });
        setActiveSessionId(session.id);
        loadSessions();
      } catch {
        // session save failed — optimization still succeeded
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Optimization failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const extractSessionName = (jobDesc) => {
    // Try to extract a meaningful name from the first line of the job description
    const firstLine = (jobDesc || '').split('\n')[0].trim();
    if (firstLine.length > 60) return firstLine.substring(0, 57) + '...';
    return firstLine || 'Untitled Session';
  };

  // Called from step 2.5 when user accepts or overrides the recommendation
  const handleRecommendationSelect = async (resumeId, resumeVersionId) => {
    setLoading(true);
    setError('');
    setCurrentResumeId(resumeId || resumeVersionId);
    setStep(3);
    try {
      // Use version optimize when no resumeId (version-only compare path)
      const result = resumeId
        ? await api.optimizeResume(resumeId)
        : await api.optimizeFromVersion(resumeVersionId);
      setOptimizedResume(result);
      try {
        const sessionName = extractSessionName(jobDescText);
        const session = await api.createSession(sessionName, resumeId, null, jobDescText);
        await api.updateSession(session.id, {
          optimization_result_json: JSON.stringify(result),
          ats_score: result.relevance_score || result.ats_compliance_score || result.optimized_resume?.score || 0,
          status: 'optimized',
        });
        setActiveSessionId(session.id);
        loadSessions();
      } catch { /* session save non-fatal */ }
    } catch (err) {
      const msg = err.response?.data?.error
        || (err.code === 'ERR_NETWORK' || err.message === 'Network Error'
            ? 'Cannot reach the server. Please ensure the backend is running and try again.'
            : null)
        || err.message
        || 'Optimization failed. Please try again.';
      setError(msg);
      setStep(2.5);
    } finally {
      setLoading(false);
    }
  };

  // Internal helper: optimize and advance to step 3 (used as compare fallback)
  const _optimizeAndAdvance = async (resumeId, extraIds, jobDesc) => {
    const result = await api.optimizeResume(resumeId, extraIds.length > 0 ? extraIds : undefined);
    setOptimizedResume(result);
    setStep(3);
  };

  const handleLoadSession = async (session) => {
    setLoading(true);
    setError('');
    try {
      const detail = await api.getSession(session.id);
      setActiveSessionId(session.id);
      setJobDescText(detail.job_description_text || '');
      setShowSkillsGap(false);

      // Restore resume context from session
      if (detail.resume_version_id) {
        setImportedResumeId(detail.resume_version_id);
        setCurrentResumeId(detail.resume_version_id);
        setResumeFile(null);
      } else if (detail.resume_id) {
        setImportedResumeId(null);
        setCurrentResumeId(detail.resume_id);
        setResumeFile(null);
      }

      if (detail.optimization_result && Object.keys(detail.optimization_result).length > 0) {
        // Session has saved results — jump to step 3
        setOptimizedResume(detail.optimization_result);
        setStep(3);
      } else if (detail.job_description_text && (detail.resume_id || detail.resume_version_id)) {
        // Has resume + job desc but no saved results — auto-run optimization
        try {
          const result = await api.optimizeSession(session.id);
          setOptimizedResume(result);
          setStep(3);
          loadSessions(); // refresh to show updated score
        } catch {
          // Optimization failed — fall back to step 2 with pre-filled job text
          setStep(2);
        }
      } else if (detail.job_description_text) {
        // Has job desc but no resume — go to step 1
        setStep(1);
      } else {
        // Empty session — go to step 1
        setStep(1);
      }
    } catch (err) {
      setError('Failed to load session');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSession = async (sessionId, e) => {
    e.stopPropagation();
    try {
      await api.deleteSession(sessionId);
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
      }
      loadSessions();
    } catch {
      setError('Failed to delete session');
    }
  };

  const handleStartOver = () => {
    setStep(1);
    setResumeFile(null);
    setImportedResumeId(null);
    setCurrentResumeId(null);
    setOptimizedResume(null);
    setJobDescText('');
    setShowSkillsGap(false);
    setActiveSessionId(null);
    setSelectedVersionIds([]);
    setError('');
  };

  const handleGDriveImport = (resumeId) => {
    setCurrentResumeId(resumeId);
  };

  const tabGroups = [
    {
      group: 'Resume',
      tabs: [
        { id: 'optimize', label: 'Optimize Resume' },
        { id: 'resume-interview', label: 'Build from Scratch' },
        { id: 'builder', label: 'Resume Builder' },
        { id: 'version-diff', label: 'Version Diff' },
        { id: 'templates', label: 'Templates' },
      ],
    },
    {
      group: 'Knowledge',
      tabs: [
        { id: 'projects', label: 'Client Projects' },
        { id: 'journey', label: 'AI Journey' },
        { id: 'deep-analysis', label: 'Deep Analysis' },
        { id: 'gdrive', label: 'Google Drive' },
      ],
    },
    {
      group: 'Marketing',
      tabs: [
        { id: 'campaigns', label: 'Campaigns' },
        { id: 'campaign-analytics', label: 'Campaign Analytics' },
        { id: 'linkedin-update', label: 'LinkedIn Update' },
        { id: 'portfolio', label: 'Portfolio' },
      ],
    },
    {
      group: 'Job Search',
      tabs: [
        { id: 'agents', label: 'AI Agents' },
        { id: 'experience', label: 'Experience Interview' },
        { id: 'cover-letter', label: 'Cover Letter' },
      ],
    },
    {
      group: 'Interview',
      tabs: [
        { id: 'interview-coach', label: 'Interview Coach' },
        { id: 'recommendations', label: 'Recommendations' },
      ],
    },
    {
      group: 'Analytics',
      tabs: [
        { id: 'analytics', label: 'Analytics' },
      ],
    },
  ];

  return (
    <div className="dashboard">
      {showOnboarding && (
        <Onboarding
          onDismiss={() => setShowOnboarding(false)}
          onNavigate={(tabId) => { setShowOnboarding(false); setActiveTab(tabId); }}
        />
      )}

      <header className="dashboard-header">
        <h1>Resume Optimizer</h1>
        <div className="user-info">
          <button onClick={() => setShowOnboarding(true)} className="btn-guide">Guide</button>
          <button onClick={() => setShowPasswordReset(true)} className="btn-reset-password">Reset Password</button>
          {user?.role === 'admin' && (
            <button onClick={() => window.location.href = '/admin'} className="btn-admin">Admin</button>
          )}
          <button onClick={onLogout} className="btn-logout">Logout</button>
        </div>
      </header>

      <PasswordReset
        show={showPasswordReset}
        onHide={() => setShowPasswordReset(false)}
        userEmail={user?.email || localStorage.getItem('user_email')}
      />

      <div className="dashboard-content">
        {error && (
          <div className="error-banner">
            {error}
            <button onClick={() => setError('')}>x</button>
          </div>
        )}

        {/* Tab Navigation — Grouped */}
        <div className="tab-nav-grouped">
          {tabGroups.map(group => (
            <div key={group.group} className="tab-group">
              <div className="tab-group-label">{group.group}</div>
              <div className="tab-group-buttons">
                {group.tabs.map(tab => (
                  <button
                    key={tab.id}
                    className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label}
                    {tab.id === 'agents' && reminderCount > 0 && (
                      <span style={{
                        background: '#ef4444', color: '#fff', borderRadius: '50%',
                        fontSize: 11, fontWeight: 700, padding: '1px 6px',
                        marginLeft: 6, verticalAlign: 'super',
                      }}>
                        {reminderCount}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Optimize Tab */}
        {activeTab === 'optimize' && (
          <>
            {/* Session list */}
            {sessions.length > 0 && (
              <div className="session-list">
                <div className="session-list-header">
                  <h3>Job Application Sessions</h3>
                  <button className="btn-new-session" onClick={handleStartOver}>
                    + New Session
                  </button>
                </div>
                <div className="session-cards">
                  {sessions.map(s => (
                    <div
                      key={s.id}
                      className={`session-card ${activeSessionId === s.id ? 'active' : ''}`}
                      onClick={() => handleLoadSession(s)}
                    >
                      <div className="session-card-top">
                        <span className="session-card-name">
                          {s.session_name || 'Untitled'}
                        </span>
                        <button
                          className="session-card-delete"
                          title="Delete session"
                          onClick={(e) => handleDeleteSession(s.id, e)}
                        >
                          &times;
                        </button>
                      </div>
                      <div className="session-card-bottom">
                        {s.status === 'optimized' && (
                          <span className="session-score-badge">
                            {Math.round(s.ats_score)}%
                          </span>
                        )}
                        <span className={`session-status ${s.status}`}>
                          {s.status}
                        </span>
                        {sessionPostings[s.id] && (
                          <span className={`session-pipeline-badge pipeline-stage-${sessionPostings[s.id].status}`}
                            title={`In Pipeline: ${sessionPostings[s.id].status.replace('_', ' ')}`}>
                            {sessionPostings[s.id].status.replace('_', ' ')}
                          </span>
                        )}
                        <span className="session-date">
                          {new Date(s.updated_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sessions.length === 0 && step === 1 && (
              <div className="session-empty-hint">
                Optimization results are automatically saved as sessions for easy comparison.
              </div>
            )}

            <div className="step-indicator">
              <div className={`step ${step >= 1 ? 'active' : ''}`}>
                <span className="step-number">1</span>
                <span className="step-label">Upload Resume</span>
              </div>
              <div className={`step ${step >= 2 ? 'active' : ''}`}>
                <span className="step-number">2</span>
                <span className="step-label">Job Description</span>
              </div>
              <div className={`step ${step >= 3 ? 'active' : ''}`}>
                <span className="step-number">3</span>
                <span className="step-label">Optimized Resume</span>
              </div>
            </div>

            {loading && (
              <div className="loading-overlay">
                <div className="spinner"></div>
                <p>Processing...</p>
              </div>
            )}

            {step === 1 && (
              <ResumeUpload
                onUpload={handleResumeUpload}
                onMultiUpload={handleMultiUpload}
                onLinkedInImport={handleLinkedInImport}
                onLinkedInFileUpload={handleLinkedInFileUpload}
                onGDriveImport={handleGDriveResumeImport}
                onModeChange={setCompareMode}
                loading={loading}
                onSavedResumeSelect={handleSavedResumeSelect}
                onLocalImport={handleLocalImport}
              />
            )}

            {step === 2 && (
              <JobDescriptionInput
                onSubmit={handleJobDescriptionSubmit}
                onBack={() => setStep(1)}
                resumeSource={importedResumeId ? 'imported' : 'file'}
                initialText={jobDescText}
              />
            )}

            {step === 2.5 && (
              <ResumeRecommendation
                recommendation={recommendation}
                loading={recommendationLoading}
                onSelect={handleRecommendationSelect}
                onRecompare={() => { setStep(2); setRecommendation(null); }}
                mode={compareMode}
                onModeChange={setCompareMode}
              />
            )}

            {step === 3 && optimizedResume && (
              <>
                <OptimizedResumeView
                  data={optimizedResume}
                  onStartOver={handleStartOver}
                  resumeSource={optimizedResume?.resume_source}
                  resumeName={optimizedResume?.resume_name}
                  jobDescTextFallback={jobDescText}
                  resumeId={currentResumeId}
                  jobSessionId={activeSessionId}
                  onSessionScoreUpdate={loadSessions}
                />

                {currentResumeId && !showSkillsGap && (
                  <div className="skills-gap-trigger">
                    <button
                      className="btn-skills-gap"
                      onClick={() => setShowSkillsGap(true)}
                    >
                      View Detailed Skills Gap Analysis
                    </button>
                  </div>
                )}

                {showSkillsGap && currentResumeId && (
                  <SkillsGap
                    resumeId={currentResumeId}
                    onClose={() => setShowSkillsGap(false)}
                  />
                )}
              </>
            )}
          </>
        )}

        {/* Resume Interview Tab — Build from Scratch */}
        {activeTab === 'resume-interview' && (
          <ResumeInterview onComplete={(versionId) => {
            setCurrentResumeId(versionId);
            setActiveTab('optimize');
          }} />
        )}

        {/* Resume Builder Tab */}
        {activeTab === 'builder' && (
          <ResumeBuilder />
        )}

        {/* Google Drive Tab */}
        {activeTab === 'gdrive' && (
          <GoogleDriveImport onResumeImported={handleGDriveImport} />
        )}

        {/* Experience Interview Tab */}
        {activeTab === 'experience' && (
          <ExperienceChat onExperienceCreated={(id) => console.log('Experience created:', id)} />
        )}

        {/* Client Projects Tab */}
        {activeTab === 'projects' && (
          <ProjectAnalyzer />
        )}

        {/* AI Journey Tab */}
        {activeTab === 'journey' && (
          <JourneyMiner />
        )}

        {/* Campaigns Tab */}
        {activeTab === 'campaigns' && (
          <CampaignManager
            onNavigateToSource={(ref) => {
              // Cross-link: navigate to Projects or Journey tab based on ref type
              if (ref.type === 'client') {
                setActiveTab('projects');
              } else if (ref.type === 'milestone' || ref.type === 'skill') {
                setActiveTab('journey');
              }
            }}
          />
        )}

        {/* Deep Analysis Tab */}
        {activeTab === 'deep-analysis' && (
          <DeepAnalysis />
        )}

        {/* Templates Tab */}
        {activeTab === 'templates' && (
          <ResumeTemplates />
        )}

        {/* LinkedIn Update Tab */}
        {activeTab === 'linkedin-update' && (
          <LinkedInProfileUpdate />
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <AnalyticsDashboard />
        )}

        {/* AI Agents Tab */}
        {activeTab === 'agents' && (
          <AgentDashboard onDismissReminder={dismissReminder} />
        )}

        {/* Interview Coach Tab */}
        {activeTab === 'interview-coach' && (
          <InterviewCoachUI />
        )}

        {/* Cover Letter Tab */}
        {activeTab === 'cover-letter' && (
          <CoverLetterUI />
        )}

        {/* Version Diff Tab */}
        {activeTab === 'version-diff' && (
          <VersionDiff />
        )}

        {/* Portfolio Tab */}
        {activeTab === 'portfolio' && (
          <PortfolioShowcase />
        )}

        {/* Recommendations Tab */}
        {activeTab === 'recommendations' && (
          <RecommendationDrafter />
        )}

        {/* Campaign Analytics Tab */}
        {activeTab === 'campaign-analytics' && (
          <CampaignAnalytics />
        )}
      </div>
    </div>
  );
}

export default Dashboard;
