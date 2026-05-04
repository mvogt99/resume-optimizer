import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import ClientAnalysisView from './ClientAnalysisView';
import '../styles/ProjectAnalyzer.css';

function ProjectAnalyzer() {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [showFolderBrowser, setShowFolderBrowser] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Folder browser state
  const [folders, setFolders] = useState([]);
  const [folderStack, setFolderStack] = useState([]);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [clientName, setClientName] = useState('');

  // Job polling
  const [activeJobs, setActiveJobs] = useState({});

  const loadProjects = useCallback(async () => {
    try {
      const data = await api.listClientProjects();
      setProjects(data.projects || []);
    } catch (err) {
      setError('Failed to load projects');
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  // Poll active jobs
  useEffect(() => {
    const jobIds = Object.keys(activeJobs);
    if (jobIds.length === 0) return;

    const interval = setInterval(async () => {
      for (const jobId of jobIds) {
        try {
          const job = await api.getJobStatus(jobId);
          setActiveJobs(prev => ({ ...prev, [jobId]: job }));
          if (job.status === 'completed' || job.status === 'failed') {
            setActiveJobs(prev => {
              const next = { ...prev };
              delete next[jobId];
              return next;
            });
            loadProjects();
          }
        } catch {
          // ignore polling errors
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [activeJobs, loadProjects]);

  const handleBrowseFolders = async (parentId) => {
    setLoading(true);
    try {
      const data = await api.listDriveFolders(parentId);
      setFolders(data.folders || []);
      if (data.error) setError(data.error);
    } catch (err) {
      setError('Cannot access Google Drive. Check OAuth setup.');
    } finally {
      setLoading(false);
    }
  };

  const openFolderBrowser = () => {
    setShowFolderBrowser(true);
    setFolderStack([]);
    setSelectedFolder(null);
    setClientName('');
    handleBrowseFolders(null);
  };

  const navigateToFolder = (folder) => {
    setFolderStack(prev => [...prev, { folders, parentName: 'Root' }]);
    handleBrowseFolders(folder.id);
  };

  const navigateBack = () => {
    if (folderStack.length === 0) return;
    const prev = folderStack[folderStack.length - 1];
    setFolderStack(s => s.slice(0, -1));
    setFolders(prev.folders);
  };

  const selectFolder = (folder) => {
    setSelectedFolder(folder);
    if (!clientName) setClientName(folder.name);
  };

  const createProject = async () => {
    if (!selectedFolder || !clientName) return;
    setLoading(true);
    try {
      await api.createClientProject(clientName, selectedFolder.id, selectedFolder.name);
      setShowFolderBrowser(false);
      loadProjects();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  const startAnalysis = async (projectId) => {
    try {
      const data = await api.startProjectAnalysis(projectId);
      setActiveJobs(prev => ({ ...prev, [data.job_id]: { status: 'running' } }));
      loadProjects();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to start analysis');
    }
  };

  const startReanalysis = async (projectId) => {
    try {
      const data = await api.reanalyzeProject(projectId);
      setActiveJobs(prev => ({ ...prev, [data.job_id]: { status: 'running' } }));
      loadProjects();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to start re-analysis');
    }
  };

  const getJobForProject = (projectId) => {
    return Object.values(activeJobs).find(
      j => j.params_json?.client_id === projectId || j.progress_json?.phase
    );
  };

  if (selectedProject) {
    return (
      <ClientAnalysisView
        projectId={selectedProject}
        onBack={() => {
          setSelectedProject(null);
          loadProjects();
        }}
      />
    );
  }

  return (
    <div className="proj-container">
      <div className="proj-header">
        <h2>Client Project Analysis</h2>
        <button className="proj-btn-add" onClick={openFolderBrowser}>
          + Add Client Project
        </button>
      </div>

      {error && (
        <div className="error-banner">
          {error}
          <button onClick={() => setError('')}>x</button>
        </div>
      )}

      {projects.length === 0 ? (
        <div className="proj-empty">
          <h3>No client projects yet</h3>
          <p>Click "Add Client Project" to browse Google Drive and select a project folder.</p>
        </div>
      ) : (
        <div className="proj-cards">
          {projects.map(project => {
            const job = getJobForProject(project.id);
            const progress = job?.progress_json || {};
            const isRunning = project.analysis_status !== 'pending' &&
                              project.analysis_status !== 'completed' &&
                              project.analysis_status !== 'failed';

            return (
              <div className="proj-card" key={project.id}>
                <div className="proj-card-header">
                  <h3>{project.client_name}</h3>
                  <span className={`proj-status-badge ${project.analysis_status}`}>
                    {project.analysis_status}
                  </span>
                </div>

                <div className="proj-card-meta">
                  <span>{project.document_count} documents</span>
                  {project.folder_name && <span>{project.folder_name}</span>}
                </div>

                {isRunning && progress.total > 0 && (
                  <div className="proj-progress">
                    <div className="proj-progress-label">
                      <span>{progress.phase}: {progress.current_file || ''}</span>
                      <span>{progress.processed}/{progress.total}</span>
                    </div>
                    <div className="proj-progress-bar">
                      <div
                        className="proj-progress-fill"
                        style={{ width: `${(progress.processed / progress.total) * 100}%` }}
                      />
                    </div>
                  </div>
                )}

                <div className="proj-card-actions">
                  {project.analysis_status === 'pending' && (
                    <button
                      className="proj-btn proj-btn-primary"
                      onClick={() => startAnalysis(project.id)}
                    >
                      Start Analysis
                    </button>
                  )}
                  {project.analysis_status === 'completed' && (
                    <>
                      <button
                        className="proj-btn proj-btn-primary"
                        onClick={() => setSelectedProject(project.id)}
                      >
                        View Analysis
                      </button>
                      <button
                        className="proj-btn proj-btn-reanalyze"
                        onClick={() => startReanalysis(project.id)}
                        title="Re-run LLM extraction on existing documents (no re-crawl)"
                      >
                        Re-Analyze (skip crawl)
                      </button>
                    </>
                  )}
                  {project.analysis_status === 'failed' && (
                    <button
                      className="proj-btn proj-btn-primary"
                      onClick={() => startAnalysis(project.id)}
                    >
                      Retry
                    </button>
                  )}
                  <button
                    className="proj-btn proj-btn-secondary"
                    onClick={() => setSelectedProject(project.id)}
                  >
                    Details
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Folder Browser Modal */}
      {showFolderBrowser && (
        <div className="proj-folder-modal" onClick={() => setShowFolderBrowser(false)}>
          <div className="proj-folder-content" onClick={e => e.stopPropagation()}>
            <h3>Select Project Folder</h3>

            <input
              type="text"
              className="proj-folder-input"
              placeholder="Client name"
              value={clientName}
              onChange={e => setClientName(e.target.value)}
            />

            <p className="proj-folder-hint">
              Click a folder to select it. Click &#9654; to open and browse subfolders.
            </p>

            <div className="proj-folder-list">
              {folderStack.length > 0 && (
                <div className="proj-folder-item proj-folder-back" onClick={navigateBack}>
                  <span className="proj-folder-icon">&#8592;</span>
                  <span>Back</span>
                </div>
              )}

              {loading ? (
                <div style={{ padding: '20px', textAlign: 'center', color: '#888' }}>
                  Loading...
                </div>
              ) : folders.length === 0 ? (
                <div style={{ padding: '20px', textAlign: 'center', color: '#888' }}>
                  No folders found
                </div>
              ) : (
                folders.map(folder => (
                  <div
                    key={folder.id}
                    className={`proj-folder-item ${selectedFolder?.id === folder.id ? 'selected' : ''}`}
                    onClick={() => selectFolder(folder)}
                  >
                    <span className="proj-folder-icon">&#128193;</span>
                    <span className="proj-folder-name">{folder.name}</span>
                    <button
                      className="proj-folder-open-btn"
                      title="Open folder"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigateToFolder(folder);
                      }}
                    >
                      &#9654;
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="proj-folder-actions">
              <button
                className="proj-btn proj-btn-secondary"
                onClick={() => setShowFolderBrowser(false)}
              >
                Cancel
              </button>
              <button
                className="proj-btn proj-btn-primary"
                onClick={createProject}
                disabled={!selectedFolder || !clientName || loading}
              >
                Create Project
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProjectAnalyzer;
