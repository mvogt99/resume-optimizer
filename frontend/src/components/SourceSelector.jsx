import React from 'react';

const SOURCE_CONFIG = {
  linkedin: {
    label: 'LinkedIn Profile',
    icon: 'in',
    color: '#0077b5',
    desc: 'Skills, accomplishments, recommendations',
  },
  projects: {
    label: 'Client Projects',
    icon: 'P',
    color: '#e65100',
    desc: 'Approved project analyses (Phase 9)',
  },
  journey: {
    label: 'AI Journey',
    icon: 'J',
    color: '#7b1fa2',
    desc: 'STAR narratives, skills timeline (Phase 10)',
  },
  experiences: {
    label: 'Experience Interviews',
    icon: 'E',
    color: '#2e7d32',
    desc: 'Extracted work experience (Phase 7)',
  },
};

function SourceSelector({ availableSources, selectedSources, onToggle }) {
  return (
    <div className="source-selector">
      <h3>Choose Data Sources</h3>
      <p className="source-selector-desc">
        Select which data to include in your resume. Each source adds relevant content.
      </p>
      <div className="source-cards">
        {Object.entries(SOURCE_CONFIG).map(([key, config]) => {
          const source = availableSources?.[key] || {};
          const isAvailable = source.available;
          const isSelected = selectedSources.includes(key);
          const count = source.skills_count || source.count || 0;

          return (
            <div
              key={key}
              className={`source-card ${isSelected ? 'selected' : ''} ${!isAvailable ? 'disabled' : ''}`}
              onClick={() => isAvailable && onToggle(key)}
            >
              <div className="source-card-icon" style={{ background: isAvailable ? config.color : '#ccc' }}>
                {config.icon}
              </div>
              <div className="source-card-content">
                <div className="source-card-label">{config.label}</div>
                <div className="source-card-desc">{config.desc}</div>
                {isAvailable ? (
                  <div className="source-card-count">
                    {key === 'linkedin' && (
                      <span>{source.skills_count || 0} skills, {source.experience_count || 0} roles, {source.recommendations_count || 0} recs</span>
                    )}
                    {key === 'projects' && <span>{count} approved project{count !== 1 ? 's' : ''}</span>}
                    {key === 'journey' && <span>{count} narrative{count !== 1 ? 's' : ''}</span>}
                    {key === 'experiences' && <span>{count} interview{count !== 1 ? 's' : ''}</span>}
                  </div>
                ) : (
                  <div className="source-card-unavailable">No data available</div>
                )}
              </div>
              <div className="source-card-check">
                {isSelected && <span className="check-mark">&#10003;</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default SourceSelector;
