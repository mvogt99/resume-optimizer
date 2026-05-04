import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

function JobScout() {
  // Criteria form
  const [roles, setRoles] = useState('');
  const [locations, setLocations] = useState('');
  const [remotePreference, setRemotePreference] = useState('any');
  const [salaryMin, setSalaryMin] = useState('');
  const [savedCriteria, setSavedCriteria] = useState([]);

  // Search state
  const [searching, setSearching] = useState(false);
  const [searchJobId, setSearchJobId] = useState(null);
  const [searchProgress, setSearchProgress] = useState(null);

  // Postings
  const [postings, setPostings] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [expandedId, setExpandedId] = useState(null);

  // Add posting form
  const [showAddForm, setShowAddForm] = useState(false);
  const [addTitle, setAddTitle] = useState('');
  const [addCompany, setAddCompany] = useState('');
  const [addUrl, setAddUrl] = useState('');
  const [addDescription, setAddDescription] = useState('');

  // Orchestration state
  const [applyingId, setApplyingId] = useState(null);
  const [applyResult, setApplyResult] = useState(null);

  // URL import
  const [importUrl, setImportUrl] = useState('');
  const [importingUrl, setImportingUrl] = useState(false);
  const [bulkUrls, setBulkUrls] = useState('');
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [bulkImporting, setBulkImporting] = useState(false);

  // Rescore loading
  const [rescoringId, setRescoringId] = useState(null);

  const loadPostings = useCallback(async () => {
    try {
      const data = await api.scoutListPostings(statusFilter || undefined, minScore);
      setPostings(data.postings || []);
    } catch {
      // ignore
    }
  }, [statusFilter, minScore]);

  const loadCriteria = useCallback(async () => {
    try {
      const data = await api.scoutListCriteria();
      setSavedCriteria(data.criteria || []);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadPostings();
    loadCriteria();
  }, [loadPostings, loadCriteria]);

  // Poll search progress
  useEffect(() => {
    if (!searchJobId) return;
    const interval = setInterval(async () => {
      try {
        const job = await api.getJobStatus(searchJobId);
        setSearchProgress(job.progress_json || {});
        if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
          setSearching(false);
          setSearchJobId(null);
          setSearchProgress(null);
          loadPostings();
        }
      } catch {
        // ignore
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [searchJobId, loadPostings]);

  const handleSearch = async (criteriaId) => {
    setSearching(true);
    try {
      const data = await api.scoutSearch(criteriaId);
      setSearchJobId(data.job_id);
    } catch (err) {
      setSearching(false);
      alert('Search failed: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleSaveCriteria = async () => {
    const criteria = {
      search_name: roles || 'Custom Search',
      target_roles: roles.split(',').map(r => r.trim()).filter(Boolean),
      locations: locations.split(',').map(l => l.trim()).filter(Boolean),
      remote_preference: remotePreference,
      salary_min: parseFloat(salaryMin) || 0,
    };
    await api.scoutSaveCriteria(criteria);
    loadCriteria();
  };

  const handleStar = async (id, currentStarred) => {
    await api.scoutUpdatePosting(id, { is_starred: currentStarred ? 0 : 1 });
    loadPostings();
  };

  const handleStatusChange = async (id, newStatus) => {
    await api.scoutUpdatePosting(id, { status: newStatus });
    loadPostings();
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this posting?')) return;
    await api.scoutDeletePosting(id);
    loadPostings();
  };

  const handleRescore = async (id) => {
    setRescoringId(id);
    try {
      await api.scoutRescorePosting(id);
      loadPostings();
    } finally {
      setRescoringId(null);
    }
  };

  const handleQuickApply = async (postingId) => {
    setApplyingId(postingId);
    setApplyResult(null);
    try {
      const result = await api.orchestrateApply(postingId);
      setApplyResult({ postingId, ...result });
      loadPostings(); // Refresh to show updated status
    } catch (err) {
      setApplyResult({
        postingId,
        status: 'failed',
        errors: [{ step: 'orchestration', error: err?.response?.data?.error || err.message }],
      });
    } finally {
      setApplyingId(null);
    }
  };

  const handleAddPosting = async () => {
    if (!addTitle) return;
    await api.scoutAddPosting({
      title: addTitle,
      company: addCompany,
      url: addUrl,
      description: addDescription,
    });
    setShowAddForm(false);
    setAddTitle('');
    setAddCompany('');
    setAddUrl('');
    setAddDescription('');
    loadPostings();
  };

  const handleImportUrl = async () => {
    if (!importUrl.trim()) return;
    setImportingUrl(true);
    try {
      await api.importJobUrl(importUrl.trim());
      setImportUrl('');
      loadPostings();
    } catch (err) {
      alert('Import failed: ' + (err?.response?.data?.error || err.message));
    } finally {
      setImportingUrl(false);
    }
  };

  const handleBulkImport = async () => {
    const urls = bulkUrls.split('\n').map(u => u.trim()).filter(Boolean);
    if (urls.length === 0) return;
    setBulkImporting(true);
    try {
      await api.bulkImportUrls(urls);
      setBulkUrls('');
      setShowBulkImport(false);
      loadPostings();
    } catch (err) {
      alert('Bulk import failed: ' + (err?.response?.data?.error || err.message));
    } finally {
      setBulkImporting(false);
    }
  };

  const scoreColor = (score) => {
    if (score >= 70) return 'score-high';
    if (score >= 40) return 'score-medium';
    return 'score-low';
  };

  const stages = [
    'discovered', 'bookmarked', 'tailored', 'applied',
    'phone_screen', 'interview', 'offered',
    'accepted', 'rejected', 'withdrawn',
  ];

  return (
    <div className="scout-container">
      {/* Search criteria */}
      <div className="scout-criteria-form">
        <h3>Job Search</h3>
        <div className="criteria-grid">
          <div className="criteria-field">
            <label>Target Roles (comma-separated)</label>
            <input
              value={roles}
              onChange={e => setRoles(e.target.value)}
              placeholder="Data Architect, Analytics Lead, Enterprise Architect"
            />
          </div>
          <div className="criteria-field">
            <label>Locations</label>
            <input
              value={locations}
              onChange={e => setLocations(e.target.value)}
              placeholder="Remote, New York, Chicago"
            />
          </div>
          <div className="criteria-field">
            <label>Remote Preference</label>
            <select value={remotePreference} onChange={e => setRemotePreference(e.target.value)}>
              <option value="any">Any</option>
              <option value="remote_only">Remote Only</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site</option>
            </select>
          </div>
          <div className="criteria-field">
            <label>Min Salary ($)</label>
            <input
              type="number"
              value={salaryMin}
              onChange={e => setSalaryMin(e.target.value)}
              placeholder="100000"
            />
          </div>
        </div>
        <div className="criteria-actions">
          <button
            className="btn-search"
            onClick={() => handleSearch()}
            disabled={searching}
          >
            {searching ? 'Searching...' : 'Search Jobs'}
          </button>
          <button className="btn-save-criteria" onClick={handleSaveCriteria}>
            Save Criteria
          </button>
        </div>

        {/* Saved criteria quick-search */}
        {savedCriteria.length > 0 && (
          <div style={{ marginTop: 12, fontSize: 13, color: '#666' }}>
            Saved: {savedCriteria.map(c => (
              <button
                key={c.id}
                onClick={() => handleSearch(c.id)}
                disabled={searching}
                style={{
                  border: '1px solid #ddd', background: '#f9fafc', borderRadius: 4,
                  padding: '3px 10px', margin: '0 4px', cursor: 'pointer', fontSize: 12,
                }}
              >
                {c.search_name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Search progress */}
      {searching && searchProgress && (
        <div className="agent-loading">
          <div className="agent-spinner" />
          <span>
            {searchProgress.stage === 'scraping' && 'Scraping job boards...'}
            {searchProgress.stage === 'scoring' && (
              `Scoring postings with RTX 5090... ${searchProgress.scored || 0}/${searchProgress.total || '?'}`
            )}
            {!searchProgress.stage && 'Starting search...'}
          </span>
        </div>
      )}

      {/* URL Import */}
      <div className="url-import-section" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            value={importUrl}
            onChange={e => setImportUrl(e.target.value)}
            placeholder="Paste job URL to import..."
            style={{ flex: 1, padding: '8px 12px', border: '1px solid #ddd', borderRadius: 4 }}
          />
          <button
            className="btn-search"
            onClick={handleImportUrl}
            disabled={importingUrl || !importUrl.trim()}
            style={{ whiteSpace: 'nowrap' }}
          >
            {importingUrl ? 'Importing...' : 'Import from URL'}
          </button>
          <button
            className="btn-save-criteria"
            onClick={() => setShowBulkImport(!showBulkImport)}
            style={{ whiteSpace: 'nowrap' }}
          >
            Bulk Import
          </button>
        </div>
        {showBulkImport && (
          <div style={{ marginTop: 8 }}>
            <textarea
              value={bulkUrls}
              onChange={e => setBulkUrls(e.target.value)}
              placeholder="Paste multiple job URLs, one per line..."
              rows={4}
              style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4, resize: 'vertical' }}
            />
            <button
              className="btn-search"
              onClick={handleBulkImport}
              disabled={bulkImporting || !bulkUrls.trim()}
              style={{ marginTop: 4 }}
            >
              {bulkImporting ? 'Importing...' : 'Import All URLs'}
            </button>
          </div>
        )}
      </div>

      {/* Postings list */}
      <div className="postings-section">
        <div className="postings-header">
          <h3>Job Postings ({postings.length})</h3>
          <div className="postings-filters">
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All Statuses</option>
              {stages.map(s => (
                <option key={s} value={s}>{s.replace('_', ' ')}</option>
              ))}
            </select>
            <label style={{ fontSize: 13 }}>
              Min Score:
              <input
                type="number"
                value={minScore}
                onChange={e => { setMinScore(Number(e.target.value)); }}
                style={{ width: 60, marginLeft: 4 }}
              />
            </label>
            <button className="btn-icon" onClick={() => loadPostings()}>Refresh</button>
            <button className="btn-icon" onClick={() => setShowAddForm(!showAddForm)}>
              + Add
            </button>
          </div>
        </div>

        {/* Add posting form */}
        {showAddForm && (
          <div className="add-posting-form" style={{ marginBottom: 16 }}>
            <h3>Add Posting Manually</h3>
            <div className="form-row">
              <label>Title *</label>
              <input value={addTitle} onChange={e => setAddTitle(e.target.value)} />
            </div>
            <div className="form-row">
              <label>Company</label>
              <input value={addCompany} onChange={e => setAddCompany(e.target.value)} />
            </div>
            <div className="form-row">
              <label>URL</label>
              <input value={addUrl} onChange={e => setAddUrl(e.target.value)} />
            </div>
            <div className="form-row">
              <label>Description</label>
              <textarea value={addDescription} onChange={e => setAddDescription(e.target.value)} />
            </div>
            <div className="criteria-actions">
              <button className="btn-search" onClick={handleAddPosting}>Add</button>
              <button className="btn-save-criteria" onClick={() => setShowAddForm(false)}>Cancel</button>
            </div>
          </div>
        )}

        {postings.length === 0 ? (
          <div className="empty-state">
            <p>No job postings yet. Run a search or add one manually.</p>
          </div>
        ) : (
          <table className="postings-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Company</th>
                <th>Location</th>
                <th>Score</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {postings.map(p => (
                <React.Fragment key={p.id}>
                  <tr onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}>
                    <td style={{ fontWeight: 500 }}>
                      {p.title}
                      {p.is_test === 1 && (
                        <span className="pipeline-card-test-badge" style={{ marginLeft: 6 }} title="Test / demo posting">TEST</span>
                      )}
                    </td>
                    <td>{p.company}</td>
                    <td>{p.location}</td>
                    <td>
                      <div className="score-bar">
                        <div className="score-bar-fill">
                          <div
                            className={`score-bar-inner ${scoreColor(p.match_score)}`}
                            style={{ width: `${Math.min(p.match_score, 100)}%` }}
                          />
                        </div>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>
                          {Math.round(p.match_score)}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className={`status-badge status-${p.status}`}>
                        {(p.status || 'discovered').replace('_', ' ')}
                      </span>
                    </td>
                    <td>
                      <div className="posting-actions">
                        <button
                          className={`btn-icon ${p.is_starred ? 'starred' : ''}`}
                          onClick={e => { e.stopPropagation(); handleStar(p.id, p.is_starred); }}
                          title="Star"
                        >
                          {p.is_starred ? '\u2605' : '\u2606'}
                        </button>
                        <select
                          value={p.status}
                          onClick={e => e.stopPropagation()}
                          onChange={e => handleStatusChange(p.id, e.target.value)}
                          style={{ fontSize: 11, padding: '2px 4px' }}
                        >
                          {stages.map(s => (
                            <option key={s} value={s}>{s.replace('_', ' ')}</option>
                          ))}
                        </select>
                        <button
                          className="btn-icon"
                          onClick={e => { e.stopPropagation(); handleDelete(p.id); }}
                          title="Delete"
                        >
                          x
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expandedId === p.id && (
                    <tr>
                      <td colSpan={6}>
                        <div className="posting-detail">
                          <h4>Score Breakdown</h4>
                          {(() => {
                            const llm = typeof p.llm_score_json === 'string'
                              ? (() => { try { return JSON.parse(p.llm_score_json); } catch { return null; } })()
                              : p.llm_score_json;
                            if (!llm || !llm.overall_recommendation) return null;
                            return (
                              <>
                                <div className="posting-scores">
                                  {['culture_fit', 'seniority_match', 'growth_potential', 'skills_alignment', 'overall_recommendation'].map(key => (
                                    <div key={key} className="posting-score-item">
                                      <div className="score-value">{llm[key] || '—'}</div>
                                      <div className="score-label">{key.replace(/_/g, ' ')}</div>
                                    </div>
                                  ))}
                                </div>
                                {llm.reasoning && (
                                  <p style={{ color: '#555', fontSize: 13, fontStyle: 'italic' }}>
                                    {llm.reasoning}
                                  </p>
                                )}
                              </>
                            );
                          })()}

                          {(() => {
                            let overlap = p.skills_overlap;
                            if (typeof overlap === 'string') { try { overlap = JSON.parse(overlap); } catch { overlap = []; } }
                            if (!Array.isArray(overlap) || overlap.length === 0) return null;
                            return (
                              <div>
                                <strong style={{ fontSize: 12 }}>Matching Skills:</strong>
                                <div className="skills-tags">
                                  {overlap.slice(0, 20).map(s => (
                                    <span key={s} className="skill-tag overlap">{s}</span>
                                  ))}
                                </div>
                              </div>
                            );
                          })()}

                          {(() => {
                            let missing = p.skills_missing;
                            if (typeof missing === 'string') { try { missing = JSON.parse(missing); } catch { missing = []; } }
                            if (!Array.isArray(missing) || missing.length === 0) return null;
                            return (
                              <div>
                                <strong style={{ fontSize: 12 }}>Missing Skills:</strong>
                                <div className="skills-tags">
                                  {missing.slice(0, 20).map(s => (
                                    <span key={s} className="skill-tag missing">{s}</span>
                                  ))}
                                </div>
                              </div>
                            );
                          })()}

                          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
                            <button
                              className="btn-search"
                              style={{ fontSize: 12, padding: '6px 14px' }}
                              onClick={() => handleRescore(p.id)}
                              disabled={rescoringId === p.id}
                            >
                              {rescoringId === p.id ? 'Re-scoring...' : 'Re-score (RTX 5090)'}
                            </button>
                            <button
                              className="btn-search"
                              style={{ fontSize: 12, padding: '6px 14px', background: '#4caf50' }}
                              onClick={() => handleQuickApply(p.id)}
                              disabled={applyingId === p.id}
                              title="Tailor resume + generate cover letter + move to pipeline"
                            >
                              {applyingId === p.id ? 'Applying...' : 'Quick Apply'}
                            </button>
                            {p.url && (
                              <a
                                href={p.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn-save-criteria"
                                style={{ textDecoration: 'none', textAlign: 'center' }}
                              >
                                View Original
                              </a>
                            )}
                          </div>

                          {/* Orchestration result */}
                          {applyResult && applyResult.postingId === p.id && (
                            <div style={{
                              marginTop: 12, padding: 12, borderRadius: 6,
                              background: applyResult.status === 'complete' ? '#e8f5e9' : applyResult.status === 'partial' ? '#fff3e0' : '#fce4ec',
                              fontSize: 13,
                            }}>
                              <strong>
                                {applyResult.status === 'complete' ? 'Application Ready' :
                                 applyResult.status === 'partial' ? 'Partially Complete' : 'Apply Failed'}
                              </strong>
                              <div style={{ marginTop: 6 }}>
                                {applyResult.steps_completed?.includes('resume_tailor') && (
                                  <div style={{ color: '#2e7d32' }}>
                                    Resume tailored (ATS: {applyResult.tailored_resume?.ats_score || '—'})
                                  </div>
                                )}
                                {applyResult.steps_completed?.includes('cover_letter') && (
                                  <div style={{ color: '#2e7d32' }}>
                                    Cover letter generated
                                  </div>
                                )}
                                {applyResult.steps_completed?.includes('interview_prep') && (
                                  <div style={{ color: '#2e7d32' }}>
                                    Interview prep ready
                                  </div>
                                )}
                                {applyResult.errors?.map((e, i) => (
                                  <div key={i} style={{ color: '#c62828' }}>
                                    {e.step}: {e.error}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {p.description && (
                            <details style={{ marginTop: 12 }}>
                              <summary style={{ cursor: 'pointer', color: '#667eea', fontSize: 13 }}>
                                Full Description
                              </summary>
                              <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: '#444', marginTop: 8 }}>
                                {p.description}
                              </pre>
                            </details>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default JobScout;
