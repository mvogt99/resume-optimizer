import axios from 'axios';

// Use explicit env var if set; otherwise derive from the page's own origin
// so network users (http://192.168.x.x:3000) automatically point to
// http://192.168.x.x:5000/api instead of their own localhost.
const _defaultApiUrl = (() => {
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:5000/api`;
  }
  return 'http://localhost:5000/api';
})();
const API_BASE_URL = import.meta.env.VITE_API_URL || _defaultApiUrl;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth headers to all requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  // Legacy fallback — keep user-id header until backend removes support
  const userId = localStorage.getItem('user_id');
  if (userId) {
    config.headers['user-id'] = userId;
  }
  return config;
});

// Handle 401 responses — clear auth and redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_id');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

const api = {
  register: async (email, password) => {
    const response = await apiClient.post('/register', { email, password });
    return response.data;
  },

  login: async (email, password) => {
    const response = await apiClient.post('/login', { email, password });
    return response.data;
  },

  uploadResume: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post('/resume/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  uploadMultipleResumes: async (files) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));

    const response = await apiClient.post('/resume/upload-multiple', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  uploadJobDescription: async (jobDescription) => {
    const response = await apiClient.post('/job-description/upload', {
      job_text: jobDescription,
    });
    return response.data;
  },

  optimizeResume: async (resumeId, additionalResumeIds) => {
    const body = additionalResumeIds?.length ? { additional_resume_ids: additionalResumeIds } : {};
    const response = await apiClient.post(`/optimize-resume/${resumeId}`, body);
    return response.data;
  },

  createResumeFromLinkedIn: async () => {
    const response = await apiClient.post('/resume/from-linkedin');
    return response.data;
  },

  uploadLinkedInProfile: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post('/import/linkedin/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Phase 3: Skills gap
  getSkillsGap: async (resumeId) => {
    const response = await apiClient.get(`/skills-gap/${resumeId}`);
    return response.data;
  },

  rescoreSkillsGap: async (resumeId, confirmedSkills, removedSkills, addedSkills) => {
    const response = await apiClient.post(`/skills-gap/${resumeId}/rescore`, {
      confirmed_skills: confirmedSkills || [],
      removed_skills: removedSkills || [],
      added_skills: addedSkills || [],
    });
    return response.data;
  },

  // Phase 4: Google Drive
  listGDriveFiles: async (folder, folderId) => {
    const params = {};
    if (folderId) params.folder_id = folderId;
    else if (folder) params.folder = folder;
    const response = await apiClient.get('/resumes/gdrive', { params });
    return response.data;
  },

  importGDriveFile: async (fileId) => {
    const response = await apiClient.post('/resumes/gdrive/import', { file_id: fileId });
    return response.data;
  },

  getResumeVersions: async () => {
    const response = await apiClient.get('/resumes/versions');
    return response.data;
  },

  getResumeVersion: async (id) => {
    const response = await apiClient.get(`/resumes/versions/${id}`);
    return response.data;
  },

  updateResumeVersion: async (id, text) => {
    const response = await apiClient.put(`/resumes/versions/${id}`, { parsed_text: text });
    return response.data;
  },

  reimportGDriveFile: async (versionId) => {
    const response = await apiClient.post(`/resumes/gdrive/reimport/${versionId}`);
    return response.data;
  },

  // Phase 7: Experience chat
  startExperienceSession: async (employer, client) => {
    const response = await apiClient.post('/experience/start', { employer, client });
    return response.data;
  },

  sendExperienceMessage: async (sessionId, message) => {
    const response = await apiClient.post('/experience/message', { session_id: sessionId, message });
    return response.data;
  },

  uploadExperienceContext: async (sessionId, file) => {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('file', file);

    const response = await apiClient.post('/experience/upload-context', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getExperienceSummary: async (sessionId) => {
    const response = await apiClient.get(`/experience/summary/${sessionId}`);
    return response.data;
  },

  finalizeExperience: async (sessionId, edits) => {
    const response = await apiClient.post(`/experience/finalize/${sessionId}`, { edits });
    return response.data;
  },

  applyExperience: async (sessionId) => {
    const response = await apiClient.post(`/experience/apply/${sessionId}`);
    return response.data;
  },

  // --- Shared: Batch jobs ---

  getJobStatus: async (jobId) => {
    const response = await apiClient.get(`/jobs/${jobId}/status`);
    return response.data;
  },

  // --- Phase 9: Client projects ---

  listClientProjects: async () => {
    const response = await apiClient.get('/projects');
    return response.data;
  },

  createClientProject: async (clientName, folderId, folderName) => {
    const response = await apiClient.post('/projects', {
      client_name: clientName,
      folder_id: folderId,
      folder_name: folderName,
    });
    return response.data;
  },

  startProjectAnalysis: async (projectId) => {
    const response = await apiClient.post(`/projects/${projectId}/analyze`);
    return response.data;
  },

  getProjectAnalysis: async (projectId) => {
    const response = await apiClient.get(`/projects/${projectId}/analysis`);
    return response.data;
  },

  updateProjectAnalysis: async (projectId, updates) => {
    const response = await apiClient.put(`/projects/${projectId}/analysis`, updates);
    return response.data;
  },

  approveProjectAnalysis: async (projectId) => {
    const response = await apiClient.post(`/projects/${projectId}/approve`);
    return response.data;
  },

  listProjectDocuments: async (projectId) => {
    const response = await apiClient.get(`/projects/${projectId}/documents`);
    return response.data;
  },

  listDriveFolders: async (parentId) => {
    const response = await apiClient.get('/projects/folders', { params: { parent_id: parentId } });
    return response.data;
  },

  // --- Phase 10: Journey mining ---

  startJourneyMining: async (opts = {}) => {
    const response = await apiClient.post('/journey/mine', opts);
    return response.data;
  },

  getMiningHistory: async (limit = 10) => {
    const response = await apiClient.get('/journey/mining-history', {
      params: { limit },
    });
    return response.data;
  },

  rescoreJourneyEvents: async () => {
    const response = await apiClient.post('/journey/rescore', {});
    return response.data;
  },

  getJourneyTimeline: async (page, perPage, category, minSignificance = 1) => {
    const response = await apiClient.get('/journey/timeline', {
      params: { page, per_page: perPage, category, min_significance: minSignificance },
    });
    return response.data;
  },

  getJourneySkills: async () => {
    const response = await apiClient.get('/journey/skills');
    return response.data;
  },

  getJourneyAchievements: async () => {
    const response = await apiClient.get('/journey/achievements');
    return response.data;
  },

  getJourneyNarratives: async () => {
    const response = await apiClient.get('/journey/narratives');
    return response.data;
  },

  updateJourneyNarratives: async (narratives) => {
    const response = await apiClient.put('/journey/narratives', { narratives });
    return response.data;
  },

  approveJourneyNarratives: async (narrativeIds) => {
    const response = await apiClient.post('/journey/approve', { narrative_ids: narrativeIds });
    return response.data;
  },

  resetJourneySources: async () => {
    const response = await apiClient.delete('/journey/reset');
    return response.data;
  },

  // --- Campaign trending topics ---

  discoverCampaignTrends: async () => {
    const response = await apiClient.post('/campaigns/discover-trends');
    return response.data;
  },

  // --- Phase 11: Campaign interview ---

  startCampaignInterview: async (theme) => {
    const response = await apiClient.post('/campaigns/interview/start', { theme });
    return response.data;
  },

  sendCampaignMessage: async (sessionId, message) => {
    const response = await apiClient.post('/campaigns/interview/message', {
      session_id: sessionId,
      message,
    });
    return response.data;
  },

  createCampaignFromInterview: async (sessionId) => {
    const response = await apiClient.post('/campaigns/create', { session_id: sessionId });
    return response.data;
  },

  // --- Phase 11: Campaign CRUD ---

  listCampaigns: async () => {
    const response = await apiClient.get('/campaigns');
    return response.data;
  },

  getCampaign: async (campaignId) => {
    const response = await apiClient.get(`/campaigns/${campaignId}`);
    return response.data;
  },

  updateCampaign: async (campaignId, updates) => {
    const response = await apiClient.put(`/campaigns/${campaignId}`, updates);
    return response.data;
  },

  deleteCampaign: async (campaignId) => {
    const response = await apiClient.delete(`/campaigns/${campaignId}`);
    return response.data;
  },

  // --- Phase 11: Post management ---

  generateCampaignPosts: async (campaignId) => {
    const response = await apiClient.post(`/campaigns/${campaignId}/generate`);
    return response.data;
  },

  listCampaignPosts: async (campaignId) => {
    const response = await apiClient.get(`/campaigns/${campaignId}/posts`);
    return response.data;
  },

  updateCampaignPost: async (campaignId, postId, updates) => {
    const response = await apiClient.put(`/campaigns/${campaignId}/posts/${postId}`, updates);
    return response.data;
  },

  regenerateCampaignPost: async (campaignId, postId, feedback) => {
    const response = await apiClient.post(
      `/campaigns/${campaignId}/posts/${postId}/regenerate`,
      { feedback },
    );
    return response.data;
  },

  deleteCampaignPost: async (campaignId, postId) => {
    const response = await apiClient.delete(`/campaigns/${campaignId}/posts/${postId}`);
    return response.data;
  },

  reorderCampaignPosts: async (campaignId, order) => {
    const response = await apiClient.put(`/campaigns/${campaignId}/posts/reorder`, { order });
    return response.data;
  },

  // --- Phase 11: Export ---

  exportCampaign: async (campaignId) => {
    const response = await apiClient.get(`/campaigns/${campaignId}/export`);
    return response.data;
  },

  updatePostEngagement: async (campaignId, postId, engagement) => {
    const response = await apiClient.put(`/campaigns/${campaignId}/posts/${postId}/engagement`, engagement);
    return response.data;
  },

  getCampaignEngagement: async (campaignId) => {
    const response = await apiClient.get(`/campaigns/${campaignId}/engagement-summary`);
    return response.data;
  },

  // Update interview (re-plan existing campaign)
  updateCampaignInterview: async (campaignId) => {
    const response = await apiClient.post(`/campaigns/${campaignId}/update-interview`);
    return response.data;
  },

  // --- Multi-session job applications ---

  createSession: async (sessionName, resumeId, resumeVersionId, jobText) => {
    const response = await apiClient.post('/sessions', {
      session_name: sessionName,
      resume_id: resumeId || null,
      resume_version_id: resumeVersionId || null,
      job_description_text: jobText || '',
    });
    return response.data;
  },

  listSessions: async () => {
    const response = await apiClient.get('/sessions');
    return response.data;
  },

  getSession: async (sessionId) => {
    const response = await apiClient.get(`/sessions/${sessionId}`);
    return response.data;
  },

  updateSession: async (sessionId, updates) => {
    const response = await apiClient.put(`/sessions/${sessionId}`, updates);
    return response.data;
  },

  deleteSession: async (sessionId) => {
    const response = await apiClient.delete(`/sessions/${sessionId}`);
    return response.data;
  },

  getSessionPostingStatus: async (sessionId) => {
    const response = await apiClient.get(`/sessions/${sessionId}/posting-status`);
    return response.data;
  },

  getSessionPostingStatuses: async () => {
    const response = await apiClient.get('/sessions/posting-statuses');
    return response.data;
  },

  getSessionInsights: async () => {
    const response = await apiClient.get('/sessions/insights');
    return response.data;
  },

  optimizeSession: async (sessionId) => {
    const response = await apiClient.post(`/sessions/${sessionId}/optimize`);
    return response.data;
  },

  // --- Skills Interview ---

  startSkillsInterview: async (resumeId, skills) => {
    const response = await apiClient.post('/skills-interview/start', { resume_id: resumeId, skills });
    return response.data;
  },

  sendSkillsInterviewMessage: async (sessionId, message) => {
    const response = await apiClient.post('/skills-interview/message', { session_id: sessionId, message });
    return response.data;
  },

  finalizeSkillsInterview: async (sessionId) => {
    const response = await apiClient.post(`/skills-interview/${sessionId}/finalize`);
    return response.data;
  },

  // --- Project status reset ---

  resetProjectStatus: async (projectId) => {
    const response = await apiClient.post(`/projects/${projectId}/reset-status`);
    return response.data;
  },

  // --- Journey Review / Narrative Interview ---

  startJourneyReview: async (reviewType) => {
    const response = await apiClient.post('/journey/review/start', { review_type: reviewType });
    return response.data;
  },

  sendJourneyReviewMessage: async (sessionId, message) => {
    const response = await apiClient.post('/journey/review/message', { session_id: sessionId, message });
    return response.data;
  },

  applyJourneyReviewChanges: async (sessionId) => {
    const response = await apiClient.post('/journey/review/apply', { session_id: sessionId });
    return response.data;
  },

  // --- ATS Score Improvement Chat ---

  startAtsImprovement: async (resumeId, scoreData) => {
    const response = await apiClient.post('/ats-improve/start', {
      resume_id: resumeId,
      score_data: scoreData,
    });
    return response.data;
  },

  sendAtsImprovementMessage: async (sessionId, message) => {
    const response = await apiClient.post('/ats-improve/message', {
      session_id: sessionId,
      message,
    });
    return response.data;
  },

  listCorrections: async (resumeId = null) => {
    const params = resumeId != null ? { resume_id: resumeId } : {};
    const response = await apiClient.get('/ats-improve/corrections', { params });
    return response.data;
  },

  addCorrection: async (oldText, newText, resumeId = null) => {
    const response = await apiClient.post('/ats-improve/corrections', {
      old_text: oldText,
      new_text: newText,
      resume_id: resumeId,
    });
    return response.data;
  },

  deleteCorrection: async (correctionId) => {
    const response = await apiClient.delete(`/ats-improve/corrections/${correctionId}`);
    return response.data;
  },

  // Re-analyze project (skip crawl)
  reanalyzeProject: async (projectId) => {
    const response = await apiClient.post(`/projects/${projectId}/reanalyze`);
    return response.data;
  },

  // --- Phase 12: Resume Builder ---

  getBuilderSources: async () => {
    const response = await apiClient.get('/builder/sources');
    return response.data;
  },

  startBuilderSession: async (baseVersionId, jobText, sources) => {
    const response = await apiClient.post('/builder/start', {
      base_version_id: baseVersionId,
      job_text: jobText,
      sources,
    });
    return response.data;
  },

  getBuilderPreview: async (sessionId) => {
    const response = await apiClient.get(`/builder/preview/${sessionId}`);
    return response.data;
  },

  startBuilderInterview: async (sessionId) => {
    const response = await apiClient.post('/builder/interview/start', {
      session_id: sessionId,
    });
    return response.data;
  },

  sendBuilderInterviewMessage: async (sessionId, message) => {
    const response = await apiClient.post('/builder/interview/message', {
      session_id: sessionId,
      message,
    });
    return response.data;
  },

  compileBuilderResume: async (sessionId, interviewSessionId) => {
    const response = await apiClient.post(`/builder/compile/${sessionId}`, {
      interview_session_id: interviewSessionId,
    });
    return response.data;
  },

  editBuilderResume: async (sessionId, text) => {
    const response = await apiClient.put(`/builder/edit/${sessionId}`, { text });
    return response.data;
  },

  saveBuilderResume: async (sessionId) => {
    const response = await apiClient.post(`/builder/save/${sessionId}`);
    return response.data;
  },

  importExperienceToBuilder: async (experienceId, jobText) => {
    const response = await apiClient.post(`/builder/import-experience/${experienceId}`, {
      job_text: jobText || '',
    });
    return response.data;
  },

  // --- Deep Profile ---
  buildDeepProfile: async () => {
    const response = await apiClient.post('/deep-profile/build');
    return response.data;
  },

  getDeepProfile: async () => {
    const response = await apiClient.get('/deep-profile');
    return response.data;
  },

  getRoleSynthesis: async (jobText) => {
    const response = await apiClient.post('/deep-profile/role-synthesis', {
      job_text: jobText,
    });
    return response.data;
  },

  // --- Deep Interview ---
  startDeepInterview: async (mode, jobText) => {
    const response = await apiClient.post('/deep-interview/start', {
      mode: mode || 'comprehensive',
      job_text: jobText || null,
    });
    return response.data;
  },

  sendDeepInterviewMessage: async (sessionId, message) => {
    const response = await apiClient.post('/deep-interview/message', {
      session_id: sessionId,
      message,
    });
    return response.data;
  },

  finalizeDeepInterview: async (sessionId) => {
    const response = await apiClient.post(`/deep-interview/${sessionId}/finalize`);
    return response.data;
  },

  // --- Phase 8: AI Agents ---

  // Job Scout
  scoutSearch: async (criteriaId) => {
    const body = criteriaId ? { criteria_id: criteriaId } : {};
    const response = await apiClient.post('/agents/scout/search', body);
    return response.data;
  },

  scoutListPostings: async (status, minScore, limit) => {
    const response = await apiClient.get('/agents/scout/postings', {
      params: { status, min_score: minScore || 0, limit: limit || 50 },
    });
    return response.data;
  },

  scoutUpdatePosting: async (postingId, updates) => {
    const response = await apiClient.put(`/agents/scout/postings/${postingId}`, updates);
    return response.data;
  },

  scoutDeletePosting: async (postingId) => {
    const response = await apiClient.delete(`/agents/scout/postings/${postingId}`);
    return response.data;
  },

  scoutAddPosting: async (data) => {
    const response = await apiClient.post('/agents/scout/postings', data);
    return response.data;
  },

  scoutRescorePosting: async (postingId) => {
    const response = await apiClient.post(`/agents/scout/postings/${postingId}/rescore`);
    return response.data;
  },

  scoutSaveCriteria: async (criteria) => {
    const response = await apiClient.post('/agents/scout/criteria', criteria);
    return response.data;
  },

  attachPostingResume: async (postingId, file) => {
    const form = new FormData();
    form.append('file', file);
    const response = await apiClient.post(
      `/agents/scout/postings/${postingId}/resume`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },

  getPostingResume: async (postingId) => {
    const response = await apiClient.get(`/agents/scout/postings/${postingId}/resume`);
    return response.data;
  },

  scoutListCriteria: async () => {
    const response = await apiClient.get('/agents/scout/criteria');
    return response.data;
  },

  scoutSkillDemand: async () => {
    const response = await apiClient.get('/agents/scout/skill-demand');
    return response.data;
  },

  // Application Pipeline
  getPipeline: async () => {
    const response = await apiClient.get('/agents/pipeline');
    return response.data;
  },

  movePosting: async (postingId, status, notes) => {
    const response = await apiClient.put(`/agents/pipeline/${postingId}`, { status, notes });
    return response.data;
  },

  getPipelineAnalytics: async () => {
    const response = await apiClient.get('/agents/pipeline/analytics');
    return response.data;
  },

  getPipelineReminders: async () => {
    const response = await apiClient.get('/agents/pipeline/reminders');
    return response.data;
  },

  getCorrelations: async () => {
    const response = await apiClient.get('/agents/pipeline/correlations');
    return response.data;
  },

  getPipelineChecklist: async (postingId) => {
    const response = await apiClient.get(`/agents/pipeline/${postingId}/checklist`);
    return response.data;
  },

  generateFollowup: async (postingId) => {
    const response = await apiClient.post(`/agents/pipeline/${postingId}/followup`);
    return response.data;
  },

  analyzePerformance: async () => {
    // posting_id is unused by the backend but route requires it
    const response = await apiClient.post('/agents/pipeline/_/analyze');
    return response.data;
  },

  // Agent system
  getAgentStatus: async () => {
    const response = await apiClient.get('/agents/status');
    return response.data;
  },

  getAgentRuns: async (limit = 50, agentType = null) => {
    const params = { limit };
    if (agentType) params.agent_type = agentType;
    const response = await apiClient.get('/agents/runs', { params });
    return response.data;
  },

  // --- Resume Tailor ---

  tailorResume: async (postingId) => {
    const response = await apiClient.post(`/agents/tailor/${postingId}`);
    return response.data;
  },

  getTailoredResume: async (postingId) => {
    const response = await apiClient.get(`/agents/tailor/${postingId}`);
    return response.data;
  },

  // --- Cover Letter ---

  generateCoverLetter: async (postingId) => {
    const response = await apiClient.post(`/agents/cover-letter/${postingId}`);
    return response.data;
  },

  getCoverLetterForPosting: async (postingId) => {
    const response = await apiClient.get(`/agents/cover-letter/${postingId}`);
    return response.data;
  },

  updateCoverLetter: async (letterId, updates) => {
    const response = await apiClient.put(`/agents/cover-letters/${letterId}`, updates);
    return response.data;
  },

  deleteCoverLetter: async (letterId) => {
    const response = await apiClient.delete(`/agents/cover-letters/${letterId}`);
    return response.data;
  },

  regenerateCoverLetter: async (letterId, feedback) => {
    const response = await apiClient.post(`/agents/cover-letters/${letterId}/regenerate`, { feedback });
    return response.data;
  },

  // --- Interview Coach ---

  coachStart: async (postingId, persona, questionCount) => {
    const response = await apiClient.post('/agents/coach/start', {
      posting_id: postingId || '',
      persona: persona || 'hiring_manager',
      question_count: questionCount || 5,
    });
    return response.data;
  },

  coachAnswer: async (sessionId, answer) => {
    const response = await apiClient.post('/agents/coach/answer', {
      session_id: sessionId,
      answer,
    });
    return response.data;
  },

  coachGetSession: async (sessionId) => {
    const response = await apiClient.get(`/agents/coach/${sessionId}`);
    return response.data;
  },

  coachListSessions: async () => {
    const response = await apiClient.get('/agents/coach/sessions');
    return response.data;
  },

  // --- Career Advisor ---

  advisorAnalyze: async () => {
    const response = await apiClient.post('/agents/advisor/analyze');
    return response.data;
  },

  advisorSkillsRoadmap: async (targetRole) => {
    const response = await apiClient.post('/agents/advisor/skills-roadmap', { target_role: targetRole });
    return response.data;
  },

  advisorRoleRecommendations: async () => {
    const response = await apiClient.post('/agents/advisor/role-recommendations');
    return response.data;
  },

  advisorSalaryInsights: async () => {
    const response = await apiClient.get('/agents/advisor/salary-insights');
    return response.data;
  },

  // --- Resume Templates (Phase 13) ---
  getTemplates: () => apiClient.get('/templates'),
  getTemplate: (id) => apiClient.get(`/templates/${id}`),
  createTemplate: (data) => apiClient.post('/templates', data),
  updateTemplate: (id, data) => apiClient.put(`/templates/${id}`, data),
  deleteTemplate: (id) => apiClient.delete(`/templates/${id}`),
  customizeTemplate: (id, data) => apiClient.post(`/templates/${id}/customize`, data),
  downloadTemplate: (id, fmt, text) => apiClient.post(`/templates/${id}/download/${fmt}`, { text }, { responseType: 'blob' }),

  // --- Job Scraper (Phase 13) ---
  scrapeJobUrl: (url) => apiClient.post('/agents/scout/scrape-url', { url }),
  importJobUrl: (url) => apiClient.post('/agents/scout/import-url', { url }),
  bulkImportUrls: (urls) => apiClient.post('/agents/scout/bulk-import', { urls }),

  // --- LinkedIn Profile Generator (Phase 13) ---
  getLinkedInProfile: () => apiClient.get('/profile/linkedin'),
  generateLinkedInUpdate: () => apiClient.post('/linkedin/generate-update'),
  getLinkedInUpdates: async () => { const r = await apiClient.get('/linkedin/updates'); return r.data; },
  updateLinkedInSection: (id, data) => apiClient.put(`/linkedin/updates/${id}`, data),
  compareLinkedIn: () => apiClient.get('/linkedin/compare'),

  // --- Application Orchestrator (Phase 13) ---
  applyToJob: (postingId, templateId) => apiClient.post('/agents/apply', { posting_id: postingId, template_id: templateId }),
  getApplicationBundle: (postingId) => apiClient.get(`/agents/apply/${postingId}/bundle`),
  recordFeedback: (data) => apiClient.post('/agents/feedback', data),
  getFeedback: () => apiClient.get('/agents/feedback'),
  getFeedbackInsights: () => apiClient.get('/agents/feedback/insights'),
  getFeedbackAnalysis: async () => { const r = await apiClient.get('/agents/feedback/analysis'); return r.data; },

  // --- Analytics (Phase 13) ---
  getAnalyticsOverview: async () => { const r = await apiClient.get('/analytics/overview'); return r.data; },
  getAnalyticsFunnel: async () => { const r = await apiClient.get('/analytics/funnel'); return r.data; },
  getScoreTrends: async () => { const r = await apiClient.get('/analytics/score-trends'); return r.data; },
  getSkillsDemand: async () => { const r = await apiClient.get('/analytics/skills-demand'); return r.data; },
  getAgentUsage: async () => { const r = await apiClient.get('/analytics/agent-usage'); return r.data; },
  getFeedbackSummary: async () => { const r = await apiClient.get('/analytics/feedback-summary'); return r.data; },

  // --- Agent Enhancements (Phase 13) ---
  generatePrepSheet: async (postingId) => { const r = await apiClient.post(`/agents/coach/prep-sheet/${postingId}`); return r.data; },
  getMarketInsights: async () => { const r = await apiClient.get('/agents/advisor/market-insights'); return r.data; },
  getAdvisorFeedbackAnalysis: async () => { const r = await apiClient.get('/agents/advisor/feedback-analysis'); return r.data; },

  // --- Phase 15: Version Diffing ---
  listVersionsForDiff: async () => {
    const response = await apiClient.get('/versions/for-diff');
    return response.data;
  },
  diffVersions: async (versionA, versionB) => {
    const response = await apiClient.post('/versions/diff', { version_a: versionA, version_b: versionB });
    return response.data;
  },

  // --- Phase 15: Portfolio ---
  generatePortfolio: async () => {
    const response = await apiClient.post('/portfolio/generate');
    return response.data;
  },
  exportPortfolioText: async () => {
    const response = await apiClient.get('/portfolio/export');
    return response.data;
  },

  // --- Phase 15: Recommendation Drafts ---
  draftRecommendation: async (targetName, relationship, sharedProjects, specificSkills) => {
    const response = await apiClient.post('/recommendations/draft', { target_name: targetName, relationship, shared_projects: sharedProjects, specific_skills: specificSkills });
    return response.data;
  },
  listRecommendationDrafts: async () => {
    const response = await apiClient.get('/recommendations/drafts');
    return response.data;
  },
  updateRecommendationDraft: async (draftId, text) => {
    const response = await apiClient.put(`/recommendations/drafts/${draftId}`, { text });
    return response.data;
  },
  deleteRecommendationDraft: async (draftId) => {
    const response = await apiClient.delete(`/recommendations/drafts/${draftId}`);
    return response.data;
  },

  // --- Phase 15: Campaign Analytics & Suggestions ---
  getCrossCampaignAnalytics: async () => {
    const response = await apiClient.get('/campaigns/cross-analytics');
    return response.data;
  },
  getCampaignComparison: async () => {
    const response = await apiClient.get('/campaigns/comparison');
    return response.data;
  },
  getCampaignSuggestions: async (maxSuggestions = 5) => {
    const response = await apiClient.get(`/campaigns/suggestions?max_suggestions=${maxSuggestions}`);
    return response.data;
  },
  getUncoveredTopics: async () => {
    const response = await apiClient.get('/campaigns/uncovered-topics');
    return response.data;
  },

  // --- Phase 15: Architecture Analysis ---
  analyzeArchitecture: async (projectId) => {
    const response = await apiClient.post('/architecture/analyze', { project_id: projectId });
    return response.data;
  },
  getArchitectureSummary: async () => {
    const response = await apiClient.get('/architecture/summary');
    return response.data;
  },

  // --- Phase 15: Orchestrator ---
  orchestrateApply: async (postingId) => {
    const response = await apiClient.post('/agents/orchestrate/apply', { posting_id: postingId });
    return response.data;
  },
  orchestrateCareerDive: async (postingId) => {
    const response = await apiClient.post('/agents/orchestrate/career-dive', { posting_id: postingId });
    return response.data;
  },
  getOrchestrateStatus: async () => {
    const response = await apiClient.get('/agents/orchestrate/status');
    return response.data;
  },

  // --- Guided Resume Interview (from-scratch builder) ---
  startResumeInterview: async () => {
    const response = await apiClient.post('/resume-interview/start');
    return response.data;
  },

  sendResumeInterviewMessage: async (sessionId, message) => {
    const response = await apiClient.post('/resume-interview/message', {
      session_id: sessionId,
      message,
    });
    return response.data;
  },

  getResumeInterviewState: async (sessionId) => {
    const response = await apiClient.get(`/resume-interview/state/${sessionId}`);
    return response.data;
  },

  previewResumeInterview: async (sessionId) => {
    const response = await apiClient.get(`/resume-interview/preview/${sessionId}`);
    return response.data;
  },

  finalizeResumeInterview: async (sessionId, edits) => {
    const response = await apiClient.post(`/resume-interview/finalize/${sessionId}`, { edits });
    return response.data;
  },

  // --- Phase 15: Resume Recommendation ---

  compareResumes: async ({ resumeIds = [], resumeVersionIds = [], jobDescriptionText, skipRationale = false }) => {
    const response = await apiClient.post('/resumes/compare', {
      resume_ids: resumeIds,
      resume_version_ids: resumeVersionIds,
      job_description_text: jobDescriptionText,
      skip_rationale: skipRationale,
    });
    return response.data;
  },

  selectRecommendation: async (recommendationId, { resumeId, resumeVersionId }) => {
    const response = await apiClient.post(`/resumes/recommendations/${recommendationId}/select`, {
      resume_id: resumeId,
      resume_version_id: resumeVersionId,
    });
    return response.data;
  },

  listRecommendations: async () => {
    const response = await apiClient.get('/resumes/recommendations');
    return response.data;
  },

  // ── Local folder browse / import ──────────────────────────────────────────

  browseLocalFolder: async (path) => {
    const params = path ? { path } : {};
    const response = await apiClient.get('/resumes/local-browse', { params });
    return response.data;
  },

  importLocalFile: async (filePath) => {
    const response = await apiClient.post('/resumes/local-import', { file_path: filePath });
    return response.data;
  },

  optimizeFromVersion: async (versionId) => {
    const response = await apiClient.post(`/optimize-resume/from-version/${versionId}`);
    return response.data;
  },

  // ── Expert AI comparison ──────────────────────────────────────────────────

  runExpertComparison: async ({ ourVersionText, expertVersionText, jobDescription }) => {
    const response = await apiClient.post('/resume/expert-compare', {
      our_version_text: ourVersionText,
      expert_version_text: expertVersionText,
      job_description: jobDescription || '',
    });
    return response.data;
  },

  sendExpertInterviewMessage: async ({ history, currentQuestion, userAnswer, userFinished, context }) => {
    const response = await apiClient.post('/resume/expert-compare/interview', {
      history,
      current_question: currentQuestion,
      user_answer: userAnswer,
      user_finished: userFinished || false,
      context,
    });
    return response.data;
  },

  generateMergedResume: async ({ ourText, expertText, interviewHistory, jobDescription }) => {
    const response = await apiClient.post('/resume/expert-compare/merge', {
      our_text: ourText,
      expert_text: expertText,
      interview_history: interviewHistory || [],
      job_description: jobDescription || '',
    });
    return response.data;
  },

  saveMergedResume: async (text, label) => {
    const response = await apiClient.post('/resume/expert-compare/save-merged', {
      text,
      label: label || 'Expert Comparison Merged',
    });
    return response.data;
  },

  // ── Keyword Grouping & Equivalency ──────────────────────────────────────

  groupKeywords: async (keywords, jobDescription) => {
    const response = await apiClient.post('/keywords/group', {
      keywords,
      job_description: jobDescription || '',
    });
    return response.data;
  },

  sendEquivalencyInterview: async (payload) => {
    const response = await apiClient.post('/keywords/equivalency/interview', {
      history: payload.history || [],
      current_question: payload.currentQuestion,
      user_answer: payload.userAnswer,
      keyword_groups: payload.keywordGroups || [],
      resume_text: payload.resumeText || '',
      job_description: payload.jobDescription || '',
      user_finished: payload.userFinished || false,
    });
    return response.data;
  },

  generateEquivalencyRewrites: async (resolvedKeywords, resumeText, jobDescription, originalText) => {
    const response = await apiClient.post('/keywords/equivalency/rewrite', {
      resolved_keywords: resolvedKeywords,
      resume_text: resumeText,
      job_description: jobDescription || '',
      original_text: originalText || '',
    });
    return response.data;
  },

  saveEquivalencies: async (resolved) => {
    const response = await apiClient.post('/keywords/equivalencies', { resolved });
    return response.data;
  },

  getEquivalencies: async () => {
    const response = await apiClient.get('/keywords/equivalencies');
    return response.data;
  },

  matchEquivalencies: async (missingKeywords, jobDescription) => {
    const response = await apiClient.post('/keywords/equivalency/match', {
      missing_keywords: missingKeywords,
      job_description: jobDescription || '',
    });
    return response.data;
  },

  disputeKeyword: async (keyword, resumeText, jobDescription) => {
    const response = await apiClient.post('/keywords/dispute', {
      keyword,
      resume_text: resumeText || '',
      job_description: jobDescription || '',
    });
    return response.data; // {covered, confidence, needs_interview, rationale, suggested_equivalent}
  },

  getRewriteHistory: async () => {
    const response = await apiClient.get('/keywords/rewrite-history');
    return response.data; // {history: [{id, created_at, rewrite_count, keywords_addressed, rewrites}]}
  },

  getIgnoredKeywords: async () => {
    const response = await apiClient.get('/keywords/ignores');
    return response.data; // {ignored: [str]}
  },

  ignoreKeywords: async (keywords) => {
    const response = await apiClient.post('/keywords/ignore', { keywords });
    return response.data; // {saved: int}
  },

  unignoreKeyword: async (keyword) => {
    const response = await apiClient.delete(`/keywords/ignore/${encodeURIComponent(keyword)}`);
    return response.data; // {deleted: bool}
  },

  exportResumeText: async (text, format) => {
    const response = await apiClient.post(
      '/resume/export-text',
      { text, format },
      { responseType: 'blob' },
    );
    return response.data; // Blob
  },

  scoreResumeText: async (text, jobDescription) => {
    const response = await apiClient.post('/resume/score-text', { text, job_description: jobDescription || '' });
    return response.data;
  },

  saveResumeVersion: async (text, label) => {
    const response = await apiClient.post('/resume/save-version', { text, label: label || 'ATS Improved' });
    return response.data;
  },

  getChatHistory: async (sessionType, sessionId) => {
    const response = await apiClient.get(`/chat-history/${sessionType}/${sessionId}`);
    return response.data; // {session_type, label, messages: [{role, content, created_at}]}
  },

  // Alignment pipeline — Phase A+B+C
  runAlignmentAnalysis: async (resumeId, jobDescText) => {
    const response = await apiClient.post('/alignment/analyze', {
      resume_id: resumeId,
      job_text: jobDescText,
    });
    return response.data; // {gaps, scores, summary, requirements, gap_summary}
  },

  generateAlignmentArtifacts: async (resumeId, jobDescText, artifacts) => {
    const body = {
      resume_id: resumeId,
      job_text: jobDescText,
    };
    if (artifacts) body.artifacts = artifacts;
    const response = await apiClient.post('/alignment/artifacts', body);
    return response.data; // {artifacts, summary}
  },

  runClaimAudit: async (resumeId, jobDescText) => {
    const response = await apiClient.post('/alignment/audit-claims', {
      resume_id: resumeId,
      job_text: jobDescText,
      use_llm: false,
    });
    return response.data; // {audits, summary}
  },

  applyRewrite: async (resumeId, target, jobDescText) => {
    const response = await apiClient.post('/alignment/apply-rewrite', {
      resume_id: resumeId,
      target,
      job_text: jobDescText,
    });
    return response.data; // {target_id, original_snippet, suggested_text, diff_hint}
  },

};

export default api;
