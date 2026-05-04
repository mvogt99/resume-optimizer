import React, { useState, useEffect } from 'react';
import api from '../services/api';
import '../styles/JourneyMiner.css';

function JourneySkills() {
  const [skills, setSkills] = useState([]);
  const [sortBy, setSortBy] = useState('count');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSkills();
  }, []);

  const loadSkills = async () => {
    setLoading(true);
    try {
      const data = await api.getJourneySkills();
      setSkills(data.skills || []);
    } catch {
      // empty
    } finally {
      setLoading(false);
    }
  };

  const sortedSkills = [...skills].sort((a, b) => {
    if (sortBy === 'count') return b.event_count - a.event_count;
    if (sortBy === 'name') return a.name.localeCompare(b.name);
    if (sortBy === 'recent') return (b.last_seen || '').localeCompare(a.last_seen || '');
    return 0;
  });

  if (loading) {
    return <div className="journey-empty"><p>Loading skills...</p></div>;
  }

  if (skills.length === 0) {
    return (
      <div className="journey-empty">
        <h3>No skills tracked yet</h3>
        <p>Run mining to extract skills from your AI journey.</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
        <span style={{ color: '#888', fontSize: '14px' }}>{skills.length} skills found</span>
        <div style={{ display: 'flex', gap: '8px' }}>
          {[
            { key: 'count', label: 'By frequency' },
            { key: 'name', label: 'A-Z' },
            { key: 'recent', label: 'Most recent' },
          ].map(opt => (
            <button
              key={opt.key}
              className={`journey-filter-btn ${sortBy === opt.key ? 'active' : ''}`}
              onClick={() => setSortBy(opt.key)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="journey-skills-grid">
        {sortedSkills.map(skill => (
          <div key={skill.name} className="journey-skill-card">
            <div className="journey-skill-count">{skill.event_count}</div>
            <div className="journey-skill-info">
              <div className="journey-skill-name">{skill.name}</div>
              <div className="journey-skill-meta">
                First: {skill.first_seen || 'unknown'}
                {skill.last_seen && skill.last_seen !== skill.first_seen && (
                  <> &middot; Last: {skill.last_seen}</>
                )}
              </div>
              {skill.categories && skill.categories.length > 0 && (
                <div style={{ marginTop: '4px' }}>
                  {skill.categories.map(cat => (
                    <span key={cat} className={`journey-category-badge ${cat}`} style={{ marginRight: '4px' }}>
                      {cat}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default JourneySkills;
