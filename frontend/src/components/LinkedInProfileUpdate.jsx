import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

const SECTION_LABELS = {
  headline: 'Headline',
  about: 'About',
  current_job: 'Current Position',
  pwc: 'PwC',
  spr: 'SPR',
  nvisia: 'NVISIA',
  psc: 'PSC Group',
  skills: 'Skills',
  education: 'Education',
};

function ProfileSection({ title, children }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, marginBottom: 12, background: '#fff' }}>
      <button
        onClick={() => setExpanded(v => !v)}
        style={{
          width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '12px 16px', background: 'none', border: 'none', cursor: 'pointer',
          fontWeight: 600, fontSize: 14, color: '#1e3a5f', textAlign: 'left',
        }}
      >
        <span>{title}</span>
        <span style={{ fontSize: 12, color: '#6b7280' }}>{expanded ? '▲ collapse' : '▼ expand'}</span>
      </button>
      {expanded && (
        <div style={{ padding: '0 16px 16px', borderTop: '1px solid #f3f4f6' }}>
          {children}
        </div>
      )}
    </div>
  );
}

function SkillPill({ skill, endorsements }) {
  return (
    <span style={{
      display: 'inline-block', padding: '3px 10px', borderRadius: 12, fontSize: 12,
      background: endorsements > 0 ? '#eff6ff' : '#f9fafb',
      border: `1px solid ${endorsements > 0 ? '#bfdbfe' : '#e5e7eb'}`,
      color: endorsements > 0 ? '#1d4ed8' : '#6b7280',
      margin: '3px 4px 3px 0',
    }}>
      {skill}{endorsements > 0 ? ` · ${endorsements}` : ''}
    </span>
  );
}

function CurrentProfile({ profile }) {
  if (!profile) return null;

  const jobs = [
    profile.current_job,
    ...(profile.additional_positions || []),
    ...(profile.previous_jobs || []),
  ].filter(Boolean);

  return (
    <div style={{ marginBottom: 32 }}>
      {/* Identity bar */}
      <div style={{
        background: 'linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%)',
        borderRadius: 12, padding: '24px 28px', marginBottom: 16, color: '#fff',
      }}>
        <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>{profile.full_name}</div>
        <div style={{ fontSize: 14, opacity: 0.9, lineHeight: 1.5 }}>{profile.headline}</div>
        {profile.connections_count && (
          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.7 }}>
            {profile.connections_count} connections
          </div>
        )}
      </div>

      {/* About */}
      {profile.summary && (
        <ProfileSection title="About">
          <p style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.6, color: '#374151', margin: '12px 0 0' }}>
            {profile.summary}
          </p>
        </ProfileSection>
      )}

      {/* Experience */}
      {jobs.length > 0 && (
        <ProfileSection title={`Experience (${jobs.length} positions)`}>
          <div style={{ marginTop: 12 }}>
            {jobs.map((job, i) => (
              <div key={i} style={{ marginBottom: i < jobs.length - 1 ? 20 : 0 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: '#111827' }}>{job.title}</div>
                <div style={{ fontSize: 13, color: '#2563eb', marginBottom: 4 }}>
                  {job.company}
                  {job.started_on && (
                    <span style={{ color: '#6b7280', marginLeft: 8 }}>
                      {job.started_on} – {job.finished_on || 'Present'}
                    </span>
                  )}
                  {job.location && <span style={{ color: '#9ca3af', marginLeft: 8 }}>· {job.location}</span>}
                </div>
                {job.description && (
                  <p style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.55, color: '#374151', margin: 0 }}>
                    {job.description}
                  </p>
                )}
                {i < jobs.length - 1 && <hr style={{ border: 'none', borderTop: '1px solid #f3f4f6', margin: '16px 0 0' }} />}
              </div>
            ))}
          </div>
        </ProfileSection>
      )}

      {/* Education */}
      {profile.education_history?.length > 0 && (
        <ProfileSection title="Education">
          <div style={{ marginTop: 12 }}>
            {profile.education_history.map((edu, i) => (
              <div key={i} style={{ marginBottom: 8 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: '#111827' }}>{edu.school_name}</div>
                <div style={{ fontSize: 13, color: '#6b7280' }}>
                  {edu.degree_name}{edu.field_of_study ? `, ${edu.field_of_study}` : ''}
                </div>
              </div>
            ))}
          </div>
        </ProfileSection>
      )}

      {/* Skills */}
      {profile.skills_and_endorsements?.length > 0 && (
        <ProfileSection title={`Skills (${profile.skills_and_endorsements.length})`}>
          <div style={{ marginTop: 12 }}>
            {profile.skills_and_endorsements.map((s, i) => (
              <SkillPill key={i} skill={s.skill} endorsements={s.endorsements_count} />
            ))}
          </div>
        </ProfileSection>
      )}

      {/* Recommendations */}
      {profile.recommendations_received?.length > 0 && (
        <ProfileSection title={`Recommendations (${profile.recommendations_received.length})`}>
          <div style={{ marginTop: 12 }}>
            {profile.recommendations_received.map((r, i) => (
              <div key={i} style={{ marginBottom: 16 }}>
                <div style={{ fontWeight: 600, fontSize: 13, color: '#111827' }}>
                  {r.author_first_name} {r.author_last_name}
                  {r.author_job_title && (
                    <span style={{ fontWeight: 400, color: '#6b7280', marginLeft: 6 }}>· {r.author_job_title}</span>
                  )}
                </div>
                <p style={{ fontSize: 13, color: '#374151', lineHeight: 1.55, margin: '4px 0 0', fontStyle: 'italic' }}>
                  "{r.text}"
                </p>
                {i < profile.recommendations_received.length - 1 && (
                  <hr style={{ border: 'none', borderTop: '1px solid #f3f4f6', margin: '12px 0 0' }} />
                )}
              </div>
            ))}
          </div>
        </ProfileSection>
      )}
    </div>
  );
}

function LinkedInProfileUpdate() {
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [updates, setUpdates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [comparison, setComparison] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editContent, setEditContent] = useState('');
  const [copied, setCopied] = useState(null);
  const [activeAction, setActiveAction] = useState(null); // 'optimize' | 'analyze' | null

  const loadProfile = useCallback(async () => {
    setProfileLoading(true);
    try {
      const res = await api.getLinkedInProfile();
      setProfile(res.data);
    } catch {
      setProfile(null);
    } finally {
      setProfileLoading(false);
    }
  }, []);

  const loadUpdates = useCallback(async () => {
    try {
      const res = await api.getLinkedInUpdates();
      setUpdates(res.data?.updates || []);
    } catch {
      // ignore on initial load
    }
  }, []);

  useEffect(() => {
    loadProfile();
    loadUpdates();
  }, [loadProfile, loadUpdates]);

  const handleOptimize = async () => {
    setGenerating(true);
    setError('');
    setActiveAction('optimize');
    try {
      await api.generateLinkedInUpdate();
      await loadUpdates();
    } catch (err) {
      setError('Failed to generate optimizations. ' + (err.response?.data?.error || ''));
    } finally {
      setGenerating(false);
    }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setError('');
    setActiveAction('analyze');
    try {
      const res = await api.compareLinkedIn();
      setComparison(res.data.comparison || []);
    } catch (err) {
      setError('Failed to analyze profile. ' + (err.response?.data?.error || ''));
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAction = async (id, status) => {
    setLoading(true);
    try {
      await api.updateLinkedInSection(id, { status });
      setUpdates(prev => prev.map(u => u.id === id ? { ...u, status } : u));
    } catch {
      setError('Failed to update section.');
    } finally {
      setLoading(false);
    }
  };

  const handleEditSave = async (id) => {
    setLoading(true);
    try {
      await api.updateLinkedInSection(id, { suggested_content: editContent });
      setUpdates(prev => prev.map(u =>
        u.id === id ? { ...u, suggested_content: editContent } : u
      ));
      setEditingId(null);
    } catch {
      setError('Failed to save edit.');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const statusBadge = (status) => {
    const colors = { pending: '#f59e0b', applied: '#10b981', rejected: '#ef4444' };
    return (
      <span style={{
        display: 'inline-block', padding: '2px 8px', borderRadius: 12,
        fontSize: 12, fontWeight: 600, color: '#fff',
        background: colors[status] || '#6b7280',
      }}>
        {status}
      </span>
    );
  };

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: '0 0 4px', color: '#111827' }}>LinkedIn Profile</h2>
        <p style={{ margin: 0, color: '#6b7280', fontSize: 14 }}>
          Review your current profile, then optimize or analyze it with AI assistance.
        </p>
      </div>

      {error && (
        <div className="alert alert-danger" style={{ marginBottom: 16 }}>{error}</div>
      )}

      {/* Current profile display */}
      {profileLoading ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>
          Loading profile...
        </div>
      ) : profile ? (
        <CurrentProfile profile={profile} />
      ) : (
        <div style={{
          textAlign: 'center', padding: 40, color: '#6b7280',
          background: '#f9fafb', borderRadius: 8, marginBottom: 24,
        }}>
          <p style={{ margin: 0 }}>No LinkedIn profile loaded. Import your profile to get started.</p>
        </div>
      )}

      {/* Action buttons */}
      <div style={{
        display: 'flex', gap: 12, marginBottom: 32,
        padding: '20px 24px', background: '#f8fafc',
        border: '1px solid #e2e8f0', borderRadius: 12,
      }}>
        <div style={{ flex: 1 }}>
          <button
            className="btn btn-primary"
            onClick={handleOptimize}
            disabled={generating || analyzing || !profile}
            style={{ width: '100%', padding: '10px 0', fontWeight: 600 }}
          >
            {generating ? 'Optimizing...' : 'Optimize Profile'}
          </button>
          <p style={{ margin: '6px 0 0', fontSize: 12, color: '#6b7280', textAlign: 'center' }}>
            AI rewrites each section to improve search ranking and impact
          </p>
        </div>
        <div style={{ flex: 1 }}>
          <button
            className="btn btn-secondary"
            onClick={handleAnalyze}
            disabled={generating || analyzing || !profile}
            style={{ width: '100%', padding: '10px 0', fontWeight: 600 }}
          >
            {analyzing ? 'Analyzing...' : 'Analyze Profile'}
          </button>
          <p style={{ margin: '6px 0 0', fontSize: 12, color: '#6b7280', textAlign: 'center' }}>
            Side-by-side comparison of current vs suggested content
          </p>
        </div>
      </div>

      {/* Analyze result: comparison view */}
      {activeAction === 'analyze' && comparison && (
        <div style={{ marginBottom: 32, background: '#f8f9fa', borderRadius: 8, padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, color: '#111827' }}>Profile Analysis: Current vs Suggested</h3>
            <button className="btn btn-sm" onClick={() => { setComparison(null); setActiveAction(null); }}>
              Close
            </button>
          </div>
          {comparison.length === 0 ? (
            <p style={{ color: '#6b7280' }}>No comparison data available. Run Optimize first.</p>
          ) : comparison.map((c, i) => (
            <div key={i} style={{ marginBottom: 20 }}>
              <h4 style={{ margin: '0 0 8px', color: '#374151' }}>
                {SECTION_LABELS[c.section_name] || c.section_name}
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 4 }}>CURRENT</div>
                  <p style={{ whiteSpace: 'pre-wrap', background: '#fff', padding: 12, borderRadius: 6, border: '1px solid #e5e7eb', fontSize: 13, margin: 0, minHeight: 60 }}>
                    {c.current_content || '(empty)'}
                  </p>
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#059669', marginBottom: 4 }}>SUGGESTED</div>
                  <p style={{ whiteSpace: 'pre-wrap', background: '#ecfdf5', padding: 12, borderRadius: 6, border: '1px solid #a7f3d0', fontSize: 13, margin: 0, minHeight: 60 }}>
                    {c.suggested_content || '(empty)'}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Optimize result: update cards */}
      {activeAction === 'optimize' && (
        <div>
          <h3 style={{ marginBottom: 16, color: '#111827' }}>
            Suggested Optimizations
            {updates.length > 0 && (
              <span style={{ fontSize: 14, fontWeight: 400, color: '#6b7280', marginLeft: 8 }}>
                ({updates.filter(u => u.status === 'pending').length} pending)
              </span>
            )}
          </h3>

          {updates.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#6b7280', background: '#f9fafb', borderRadius: 8 }}>
              <p>Click "Optimize Profile" to generate AI-powered suggestions.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {updates.map(u => (
                <div key={u.id} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, background: '#fff' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <h3 style={{ margin: 0, fontSize: 15, textTransform: 'capitalize' }}>
                      {SECTION_LABELS[u.section_name] || u.section_name}
                    </h3>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      {statusBadge(u.status)}
                      <button
                        className="btn btn-sm"
                        onClick={() => copyToClipboard(u.suggested_content, u.id)}
                        title="Copy suggested content"
                      >
                        {copied === u.id ? 'Copied!' : 'Copy'}
                      </button>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 12 }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 4 }}>CURRENT</div>
                      <p style={{ whiteSpace: 'pre-wrap', background: '#f9fafb', padding: 10, borderRadius: 6, fontSize: 13, minHeight: 60, margin: 0 }}>
                        {u.current_content || '(empty)'}
                      </p>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#059669', marginBottom: 4 }}>SUGGESTED</div>
                      {editingId === u.id ? (
                        <div>
                          <textarea
                            value={editContent}
                            onChange={e => setEditContent(e.target.value)}
                            rows={5}
                            style={{ width: '100%', padding: 10, borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, boxSizing: 'border-box' }}
                          />
                          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                            <button className="btn btn-sm btn-primary" onClick={() => handleEditSave(u.id)} disabled={loading}>Save</button>
                            <button className="btn btn-sm" onClick={() => setEditingId(null)}>Cancel</button>
                          </div>
                        </div>
                      ) : (
                        <p
                          style={{ whiteSpace: 'pre-wrap', background: '#ecfdf5', padding: 10, borderRadius: 6, fontSize: 13, minHeight: 60, margin: 0, cursor: 'pointer' }}
                          onClick={() => { setEditingId(u.id); setEditContent(u.suggested_content); }}
                          title="Click to edit"
                        >
                          {u.suggested_content || '(empty)'}
                        </p>
                      )}
                    </div>
                  </div>

                  {u.status === 'pending' && (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn-sm btn-success" onClick={() => handleAction(u.id, 'applied')} disabled={loading}>Accept</button>
                      <button className="btn btn-sm btn-danger" onClick={() => handleAction(u.id, 'rejected')} disabled={loading}>Reject</button>
                      <button className="btn btn-sm" onClick={() => { setEditingId(u.id); setEditContent(u.suggested_content); }}>Edit</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default LinkedInProfileUpdate;
