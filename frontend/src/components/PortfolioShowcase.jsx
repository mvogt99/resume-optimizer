import React, { useState, useCallback } from 'react';
import api from '../services/api';

function PortfolioShowcase() {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.buildDeepProfile();
      setPortfolio(res);
    } catch (err) {
      setError('Failed to generate portfolio.');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleExport = async () => {
    setExporting(true);
    try {
      const sections = [];
      if (portfolio.career_phases) {
        sections.push('CAREER PHASES\n' + portfolio.career_phases.map(p =>
          `${p.phase || p.title || 'Phase'}: ${p.description || ''}`
        ).join('\n'));
      }
      if (portfolio.projects) {
        sections.push('PROJECTS\n' + portfolio.projects.map(p =>
          `${p.name || 'Project'} | ${p.client || ''} | ${p.role || ''}\nTech: ${(p.technologies || []).join(', ')}\nOutcomes: ${(p.outcomes || []).join('; ')}`
        ).join('\n\n'));
      }
      if (portfolio.skills_summary) {
        const skills = Array.isArray(portfolio.skills_summary)
          ? portfolio.skills_summary.map(s => typeof s === 'string' ? s : s.name || s.skill).join(', ')
          : JSON.stringify(portfolio.skills_summary);
        sections.push('SKILLS\n' + skills);
      }
      const text = sections.join('\n\n---\n\n');
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      setError('Clipboard access denied.');
    } finally {
      setExporting(false);
    }
  };

  const renderProjects = (projects) => (
    <div className="portfolio-projects">
      {projects.map((p, i) => (
        <div key={i} className="portfolio-project-card">
          <h4 className="portfolio-project-name">{p.name || p.title || `Project ${i + 1}`}</h4>
          {p.client && <span className="portfolio-project-client">{p.client}</span>}
          {p.role && <span className="portfolio-project-role">{p.role}</span>}
          {p.technologies && p.technologies.length > 0 && (
            <div className="portfolio-tech-tags">
              {p.technologies.map((t, j) => <span key={j} className="portfolio-tag">{t}</span>)}
            </div>
          )}
          {p.outcomes && p.outcomes.length > 0 && (
            <ul className="portfolio-outcomes">
              {p.outcomes.map((o, j) => <li key={j}>{typeof o === 'string' ? o : o.description || JSON.stringify(o)}</li>)}
            </ul>
          )}
        </div>
      ))}
    </div>
  );

  const renderSkills = (skills) => {
    const items = Array.isArray(skills) ? skills : Object.entries(skills || {}).map(([k, v]) => ({ name: k, level: v }));
    return (
      <div className="portfolio-skills-cloud">
        {items.map((s, i) => {
          const name = typeof s === 'string' ? s : s.name || s.skill || '';
          return <span key={i} className="portfolio-skill-tag">{name}</span>;
        })}
      </div>
    );
  };

  return (
    <div className="portfolio-container">
      <h2>Portfolio Showcase</h2>
      {error && <div className="portfolio-error">{error}</div>}

      {!portfolio && (
        <div className="portfolio-empty">
          <p>Generate a structured portfolio from your career data, projects, and skills.</p>
          <button className="btn-primary" onClick={handleGenerate} disabled={loading}>
            {loading ? 'Generating...' : 'Generate Portfolio'}
          </button>
        </div>
      )}

      {portfolio && (
        <div className="portfolio-content">
          <div className="portfolio-actions">
            <button className="btn-primary" onClick={handleExport} disabled={exporting}>
              {copied ? 'Copied!' : exporting ? 'Exporting...' : 'Export as Text'}
            </button>
            <button className="btn-secondary" onClick={handleGenerate} disabled={loading}>
              {loading ? 'Regenerating...' : 'Regenerate'}
            </button>
          </div>

          {portfolio.career_phases && portfolio.career_phases.length > 0 && (
            <div className="portfolio-section">
              <h3>Career Phases</h3>
              {portfolio.career_phases.map((phase, i) => (
                <div key={i} className="portfolio-phase">
                  <h4>{phase.phase || phase.title || `Phase ${i + 1}`}</h4>
                  <p>{phase.description || ''}</p>
                </div>
              ))}
            </div>
          )}

          {portfolio.projects && portfolio.projects.length > 0 && (
            <div className="portfolio-section">
              <h3>Projects</h3>
              {renderProjects(portfolio.projects)}
            </div>
          )}

          {portfolio.skills_summary && (
            <div className="portfolio-section">
              <h3>Skills</h3>
              {renderSkills(portfolio.skills_summary)}
            </div>
          )}

          {portfolio.differentiators && portfolio.differentiators.length > 0 && (
            <div className="portfolio-section">
              <h3>Differentiators</h3>
              <ul>{portfolio.differentiators.map((d, i) => <li key={i}>{typeof d === 'string' ? d : d.description || JSON.stringify(d)}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default PortfolioShowcase;
