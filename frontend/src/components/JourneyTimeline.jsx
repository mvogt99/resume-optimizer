import React, { useState, useEffect } from 'react';
import api from '../services/api';
import '../styles/JourneyMiner.css';

const CATEGORIES = ['all', 'milestone', 'achievement', 'learning', 'fix', 'development', 'planning'];

function JourneyTimeline() {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState('all');
  const [minSignificance, setMinSignificance] = useState(1);
  const [expandedId, setExpandedId] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTimeline();
  }, [page, category, minSignificance]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadTimeline = async () => {
    setLoading(true);
    try {
      const cat = category === 'all' ? undefined : category;
      const data = await api.getJourneyTimeline(page, 30, cat, minSignificance);
      setEvents(data.events || []);
      setTotal(data.total || 0);
    } catch {
      // empty
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(total / 30);

  if (loading && events.length === 0) {
    return <div className="journey-empty"><p>Loading timeline...</p></div>;
  }

  if (events.length === 0) {
    return (
      <div className="journey-empty">
        <h3>No timeline events yet</h3>
        <p>Click "Start Mining" to scan your AI journey and build a timeline.</p>
      </div>
    );
  }

  return (
    <div>
      {/* Filters */}
      <div className="journey-filters">
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            className={`journey-filter-btn ${category === cat ? 'active' : ''}`}
            onClick={() => { setCategory(cat); setPage(1); }}
          >
            {cat}
          </button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <label style={{ fontSize: 12, color: '#666' }}>Min Significance:</label>
          <select
            value={minSignificance}
            onChange={(e) => { setMinSignificance(parseInt(e.target.value)); setPage(1); }}
            style={{
              padding: '4px 8px',
              fontSize: 12,
              border: '1px solid #ddd',
              borderRadius: 4,
              backgroundColor: '#fff'
            }}
          >
            <option value={1}>1+ (All)</option>
            <option value={2}>2+ (Important)</option>
            <option value={3}>3+ (Key)</option>
            <option value={4}>4+ (Major)</option>
            <option value={5}>5 (Critical)</option>
          </select>
        </div>
      </div>

      {/* Timeline */}
      <div className="journey-timeline">
        {events.map(event => {
          const isExpanded = expandedId === event.id;
          const technologies = Array.isArray(event.technologies) ? event.technologies : [];

          return (
            <div
              key={event.id}
              className={`journey-event ${event.category} ${isExpanded ? 'expanded' : ''}`}
              onClick={() => setExpandedId(isExpanded ? null : event.id)}
            >
              <div className="journey-event-date">{event.event_date}</div>
              <div className="journey-event-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <div className="journey-event-title">{event.title}</div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span className={`journey-category-badge ${event.category}`}>
                      {event.category}
                    </span>
                    {event.significance_score && (
                      <span className={`journey-significance-badge significance-${event.significance_score}`}>
                        ⭐ {event.significance_score}
                      </span>
                    )}
                  </div>
                </div>
                <div className="journey-event-desc">{event.description}</div>
                {technologies.length > 0 && (
                  <div className="journey-event-tags">
                    {technologies.map(tech => (
                      <span key={tech} className="journey-tag">{tech}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="journey-pagination">
          <button
            className="journey-page-btn"
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
          >
            Previous
          </button>
          <span style={{ padding: '8px 12px', color: '#666' }}>
            Page {page} of {totalPages}
          </span>
          <button
            className="journey-page-btn"
            disabled={page >= totalPages}
            onClick={() => setPage(p => p + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

export default JourneyTimeline;
