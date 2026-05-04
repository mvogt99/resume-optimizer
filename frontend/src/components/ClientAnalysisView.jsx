import React, { useState, useEffect } from 'react';
import api from '../services/api';
import AnalysisApproval from './AnalysisApproval';
import '../styles/ProjectAnalyzer.css';

// Safely convert any value to a renderable string (handles dict/list from LLM)
const safeStr = (v) => {
  if (!v) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (Array.isArray(v)) return v.map(x => typeof x === 'string' ? x : JSON.stringify(x)).join(', ');
  if (typeof v === 'object') return Object.entries(v).map(([k, val]) => `${k}: ${val}`).join(', ');
  return String(v);
};

function ClientAnalysisView({ projectId, onBack }) {
  const [analysis, setAnalysis] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [showApproval, setShowApproval] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [outcomeFilter, setOutcomeFilter] = useState('all');
  const [outcomeSort, setOutcomeSort] = useState('confidence');
  const [expandedOutcome, setExpandedOutcome] = useState(null);

  useEffect(() => {
    loadData();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadData = async () => {
    setLoading(true);
    try {
      const [analysisData, docsData] = await Promise.all([
        api.getProjectAnalysis(projectId),
        api.listProjectDocuments(projectId),
      ]);
      setAnalysis(analysisData);
      setDocuments(docsData.documents || []);

      // Parse JSON fields — handle both array and object formats
      const parseAnalysisField = (raw, arrayKey) => {
        let parsed = raw;
        if (typeof parsed === 'string') {
          try { parsed = JSON.parse(parsed || '{}'); } catch { parsed = {}; }
        }
        if (!parsed) return [];
        // Already an array — use directly
        if (Array.isArray(parsed)) return parsed;
        // Object with nested array (e.g., {technologies: [...]})
        if (typeof parsed === 'object' && arrayKey && Array.isArray(parsed[arrayKey])) {
          return parsed[arrayKey];
        }
        // Object — try to find any array value inside it
        if (typeof parsed === 'object') {
          for (const val of Object.values(parsed)) {
            if (Array.isArray(val) && val.length > 0) return val;
          }
        }
        return [];
      };

      const tech = parseAnalysisField(analysisData.technical_analysis_json, 'technologies');
      const gov = parseAnalysisField(analysisData.governance_analysis_json, 'compliance_frameworks');
      const role = parseAnalysisField(analysisData.role_analysis_json, 'contributions');
      const outcomes = parseAnalysisField(analysisData.business_outcomes_json, 'outcomes');

      // Parse correlation data for outcome-skill links
      let correlation = {};
      if (analysisData.correlation_json) {
        try {
          correlation = typeof analysisData.correlation_json === 'string'
            ? JSON.parse(analysisData.correlation_json || '{}')
            : analysisData.correlation_json;
        } catch { correlation = {}; }
      }

      setEditData({ technical: tech, governance: gov, role: role, outcomes: outcomes, correlation });
    } catch (err) {
      setError('Failed to load analysis');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      await api.updateProjectAnalysis(projectId, {
        technical_analysis_json: editData.technical,
        governance_analysis_json: editData.governance,
        role_analysis_json: editData.role,
      });
      setEditing(false);
      loadData();
    } catch (err) {
      setError('Failed to save changes');
    }
  };

  const handleApprove = async () => {
    try {
      await api.approveProjectAnalysis(projectId);
      setShowApproval(false);
      loadData();
    } catch (err) {
      setError('Failed to approve analysis');
    }
  };

  if (loading) {
    return <div className="proj-empty"><p>Loading analysis...</p></div>;
  }

  if (!analysis) {
    return <div className="proj-empty"><p>No analysis data found.</p></div>;
  }

  const tech = editData.technical || [];
  const gov = editData.governance || [];
  const role = editData.role || [];

  const OUTCOME_TYPE_RANK = {
    revenue_growth: 11, cost_reduction: 10, efficiency_improvement: 9,
    scale_achievement: 8, quality_improvement: 7, customer_satisfaction: 6,
    risk_reduction: 5, team_org_impact: 4, process_automation: 3,
    capability_enablement: 2, time_savings: 1,
  };

  const allOutcomes = editData.outcomes || [];
  const allOutcomeTypes = [...new Set(allOutcomes.map(o => o.outcome_type).filter(Boolean))];
  const filteredOutcomes = outcomeFilter === 'all'
    ? allOutcomes
    : allOutcomes.filter(o => o.outcome_type === outcomeFilter);
  const outcomes = [...filteredOutcomes].sort((a, b) => {
    if (outcomeSort === 'impact') {
      return (OUTCOME_TYPE_RANK[b.outcome_type] || 0) - (OUTCOME_TYPE_RANK[a.outcome_type] || 0);
    }
    return (b.confidence || 0) - (a.confidence || 0);
  });
  const outcomeSkillLinks = editData.correlation?.outcome_skill_links || [];

  const getOutcomeTypeBadgeColor = (type) => {
    switch (type) {
      case 'revenue_growth': return '#28a745';
      case 'cost_reduction': return '#17a2b8';
      case 'efficiency_improvement': return '#007bff';
      case 'scale_achievement': return '#6f42c1';
      case 'quality_improvement': return '#fd7e14';
      case 'customer_satisfaction': return '#e83e8c';
      case 'risk_reduction': return '#dc3545';
      case 'time_savings': return '#20c997';
      default: return '#6c757d';
    }
  };

  const getConfidenceColor = (conf) => {
    if (conf >= 0.85) return '#28a745';
    if (conf >= 0.70) return '#ffc107';
    return '#6c757d';
  };

  return (
    <div className="proj-container">
      <div className="proj-header">
        <div>
          <button className="proj-btn proj-btn-secondary" onClick={onBack}>
            &#8592; Back
          </button>
          <h2 style={{ display: 'inline', marginLeft: '16px' }}>
            {analysis.client_name}
          </h2>
          <span className={`proj-status-badge ${analysis.analysis_status}`} style={{ marginLeft: '12px' }}>
            {analysis.analysis_status}
          </span>
          {analysis.approved === 1 && (
            <span className="proj-status-badge completed" style={{ marginLeft: '8px' }}>
              Approved
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {!editing && analysis.analysis_status === 'completed' && (
            <>
              <button className="proj-btn proj-btn-secondary" onClick={() => setEditing(true)}>
                Edit
              </button>
              {!analysis.approved && (
                <button className="proj-btn proj-btn-success" onClick={() => setShowApproval(true)}>
                  Approve & Store
                </button>
              )}
            </>
          )}
          {editing && (
            <>
              <button className="proj-btn proj-btn-secondary" onClick={() => setEditing(false)}>
                Cancel
              </button>
              <button className="proj-btn proj-btn-primary" onClick={handleSave}>
                Save
              </button>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="error-banner">
          {error}
          <button onClick={() => setError('')}>x</button>
        </div>
      )}

      {/* 3-column analysis grid */}
      <div className="proj-analysis-grid">
        {/* Technical */}
        <div className="proj-analysis-section">
          <h3>Technical Picture ({tech.length})</h3>
          {tech.length === 0 ? (
            <p style={{ color: '#888', fontSize: '13px' }}>No technologies extracted yet.</p>
          ) : (
            tech.map((item, i) => {
              const name = typeof item === 'string' ? item : safeStr(item.name || item.technology || '');
              const category = typeof item === 'string' ? '' : safeStr(item.category || '');
              const context = typeof item === 'string' ? '' : safeStr(item.context || item.description || '');
              return (
                <div key={i} className="proj-item-card">
                  <h4>
                    {name}
                    {category && (
                      <span className="proj-chip" style={{ marginLeft: '8px' }}>
                        {category}
                      </span>
                    )}
                  </h4>
                  {context && <p>{context}</p>}
                </div>
              );
            })
          )}
        </div>

        {/* Governance */}
        <div className="proj-analysis-section">
          <h3>Governance ({gov.length})</h3>
          {gov.length === 0 ? (
            <p style={{ color: '#888', fontSize: '13px' }}>No governance elements extracted yet.</p>
          ) : (
            gov.map((item, i) => {
              const name = typeof item === 'string' ? item : safeStr(item.name || item.framework || '');
              const category = typeof item === 'string' ? '' : safeStr(item.category || '');
              const desc = typeof item === 'string' ? '' : safeStr(item.description || '');
              return (
                <div key={i} className="proj-item-card">
                  <h4>
                    {name}
                    {category && (
                      <span className="proj-chip governance" style={{ marginLeft: '8px' }}>
                        {category}
                      </span>
                    )}
                  </h4>
                  {desc && <p>{desc}</p>}
                </div>
              );
            })
          )}
        </div>

        {/* Role & Impact */}
        <div className="proj-analysis-section">
          <h3>Role & Impact ({role.length})</h3>
          {role.length === 0 ? (
            <p style={{ color: '#888', fontSize: '13px' }}>No contributions extracted yet.</p>
          ) : (
            role.map((item, i) => {
              const title = typeof item === 'string' ? item : safeStr(item.title || item.name || item.contribution || '');
              const type = typeof item === 'string' ? '' : safeStr(item.type || '');
              const desc = typeof item === 'string' ? '' : safeStr(item.description || '');
              const metrics = typeof item === 'string' ? '' : safeStr(item.metrics || '');
              return (
                <div key={i} className="proj-item-card">
                  <h4>
                    {title}
                    {type && (
                      <span className="proj-chip role" style={{ marginLeft: '8px' }}>
                        {type}
                      </span>
                    )}
                  </h4>
                  {desc && <p>{desc}</p>}
                  {metrics && (
                    <p style={{ fontWeight: '600', color: '#28a745' }}>{metrics}</p>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Business Outcomes */}
      <div className="proj-analysis-section" style={{ marginBottom: '24px' }}>
        <h3>Business Outcomes ({outcomes.length}{outcomeFilter !== 'all' ? ` of ${allOutcomes.length}` : ''})</h3>

        {/* Filter & Sort controls */}
        {allOutcomes.length > 0 && (
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '12px', color: '#888' }}>Filter:</span>
              <select
                value={outcomeFilter}
                onChange={(e) => setOutcomeFilter(e.target.value)}
                style={{
                  background: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: '4px',
                  padding: '3px 8px', fontSize: '12px', cursor: 'pointer',
                }}
              >
                <option value="all">All types</option>
                {allOutcomeTypes.map(t => (
                  <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ fontSize: '12px', color: '#888' }}>Sort:</span>
              <button
                onClick={() => setOutcomeSort('confidence')}
                style={{
                  padding: '3px 10px', fontSize: '12px', borderRadius: '4px', cursor: 'pointer',
                  border: '1px solid #dee2e6',
                  background: outcomeSort === 'confidence' ? '#007bff' : '#f8f9fa',
                  color: outcomeSort === 'confidence' ? '#fff' : '#333',
                }}
              >
                Confidence
              </button>
              <button
                onClick={() => setOutcomeSort('impact')}
                style={{
                  padding: '3px 10px', fontSize: '12px', borderRadius: '4px', cursor: 'pointer',
                  border: '1px solid #dee2e6',
                  background: outcomeSort === 'impact' ? '#007bff' : '#f8f9fa',
                  color: outcomeSort === 'impact' ? '#fff' : '#333',
                }}
              >
                Impact
              </button>
            </div>
          </div>
        )}

        {outcomes.length === 0 ? (
          <p style={{ color: '#888', fontSize: '13px' }}>No business outcomes extracted yet.</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '12px' }}>
            {outcomes.map((item, i) => {
              const title = typeof item === 'string' ? item : safeStr(item.outcome_title || item.title || '');
              const outcomeType = typeof item === 'string' ? '' : safeStr(item.outcome_type || '');
              const desc = typeof item === 'string' ? '' : safeStr(item.description || '');
              const metricVal = typeof item === 'string' ? '' : safeStr(item.metric_value || '');
              const baseline = typeof item === 'string' ? '' : safeStr(item.baseline || '');
              const result = typeof item === 'string' ? '' : safeStr(item.result || '');
              const timePeriod = typeof item === 'string' ? '' : safeStr(item.time_period || '');
              const beneficiary = typeof item === 'string' ? '' : safeStr(item.beneficiary || '');
              const confidence = typeof item === 'string' ? 0 : (item.confidence || 0);
              const typeLabel = outcomeType.replace(/_/g, ' ');

              // Find skill links from correlation data
              const skillLink = outcomeSkillLinks.find(l => (l.outcome_title || l.outcome) === title);
              const drivenBySkills = skillLink?.skills || item.related_skills || item.technologies || [];

              return (
                <div key={i} className="proj-item-card">
                  <h4>
                    {metricVal && (
                      <span style={{ color: '#28a745', marginRight: '6px', fontWeight: '700' }}>
                        {metricVal}
                      </span>
                    )}
                    {title}
                  </h4>
                  {outcomeType && (
                    <span
                      className="proj-chip"
                      style={{
                        backgroundColor: getOutcomeTypeBadgeColor(outcomeType),
                        color: '#fff',
                        textTransform: 'capitalize',
                        marginBottom: '6px',
                        display: 'inline-block',
                      }}
                    >
                      {typeLabel}
                    </span>
                  )}
                  {desc && <p>{desc}</p>}
                  {(baseline || result) && (
                    <p style={{ fontSize: '12px', color: '#666', margin: '4px 0' }}>
                      {baseline && <span>{baseline}</span>}
                      {baseline && result && <span> &rarr; </span>}
                      {result && <span style={{ fontWeight: '600', color: '#28a745' }}>{result}</span>}
                    </p>
                  )}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                    <div style={{ fontSize: '11px', color: '#888' }}>
                      {timePeriod && <span>{timePeriod}</span>}
                      {timePeriod && beneficiary && <span> &middot; </span>}
                      {beneficiary && <span>{beneficiary}</span>}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <div style={{
                        width: '48px', height: '6px', backgroundColor: '#e9ecef',
                        borderRadius: '3px', overflow: 'hidden',
                      }}>
                        <div style={{
                          width: `${Math.round(confidence * 100)}%`, height: '100%',
                          backgroundColor: getConfidenceColor(confidence),
                          borderRadius: '3px',
                        }} />
                      </div>
                      <span style={{ fontSize: '11px', color: getConfidenceColor(confidence), fontWeight: '600' }}>
                        {Math.round(confidence * 100)}%
                      </span>
                    </div>
                  </div>

                  {/* Driven by — expandable skill links */}
                  <div style={{ marginTop: '8px', borderTop: '1px solid #eee', paddingTop: '6px' }}>
                    <span
                      onClick={() => setExpandedOutcome(expandedOutcome === i ? null : i)}
                      style={{
                        fontSize: '11px', color: '#007bff', cursor: 'pointer',
                        userSelect: 'none',
                      }}
                    >
                      {expandedOutcome === i ? '▾' : '▸'} Driven by
                    </span>
                    {expandedOutcome === i && (
                      <div style={{ marginTop: '4px', fontSize: '12px', color: '#555' }}>
                        {drivenBySkills.length > 0 ? (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                            {drivenBySkills.map((skill, si) => (
                              <span key={si} className="proj-chip" style={{ fontSize: '11px' }}>
                                {typeof skill === 'string' ? skill : safeStr(skill.name || skill)}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span style={{ fontStyle: 'italic', color: '#aaa' }}>No skill data available</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Documents list */}
      <div className="proj-analysis-section" style={{ marginBottom: '24px' }}>
        <h3>Analyzed Documents ({documents.length})</h3>
        <div className="proj-docs-list">
          {documents.map(doc => (
            <div key={doc.id} className="proj-doc-row">
              <span className="proj-doc-name">{doc.file_name}</span>
              <span className="proj-doc-path">{doc.folder_path}</span>
              <span className={`proj-doc-status ${doc.status}`}>
                {doc.status}
              </span>
              {doc.text_length > 0 && (
                <span style={{ marginLeft: '8px', color: '#888', fontSize: '12px' }}>
                  {(doc.text_length / 1000).toFixed(1)}k chars
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Approval dialog */}
      {showApproval && (
        <AnalysisApproval
          clientName={analysis.client_name}
          techCount={tech.length}
          govCount={gov.length}
          roleCount={role.length}
          outcomesCount={outcomes.length}
          onApprove={handleApprove}
          onCancel={() => setShowApproval(false)}
        />
      )}
    </div>
  );
}

export default ClientAnalysisView;
