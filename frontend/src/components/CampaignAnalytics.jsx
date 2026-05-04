import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

function CampaignAnalytics() {
  const [analytics, setAnalytics] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [analyticsRes, campaignsRes] = await Promise.all([
        api.getAnalyticsOverview(),
        api.listCampaigns(),
      ]);
      setAnalytics(analyticsRes);
      setCampaigns(campaignsRes.campaigns || []);
    } catch (err) {
      setError('Failed to load analytics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const totalPosts = campaigns.reduce((sum, c) => sum + (c.post_count || 0), 0);
  const avgPosts = campaigns.length > 0 ? Math.round(totalPosts / campaigns.length) : 0;

  // Aggregate theme distribution
  const themeMap = {};
  campaigns.forEach(c => {
    const theme = c.theme || 'Other';
    themeMap[theme] = (themeMap[theme] || 0) + 1;
  });
  const themes = Object.entries(themeMap).sort((a, b) => b[1] - a[1]);
  const maxThemeCount = themes.length > 0 ? themes[0][1] : 1;

  // Aggregate tone distribution
  const toneMap = {};
  campaigns.forEach(c => {
    const tone = c.tone || 'neutral';
    toneMap[tone] = (toneMap[tone] || 0) + 1;
  });
  const tones = Object.entries(toneMap).sort((a, b) => b[1] - a[1]);

  // Aggregate hashtags
  const hashtagMap = {};
  campaigns.forEach(c => {
    (c.hashtags || '').split(/[,\s]+/).filter(Boolean).forEach(h => {
      const tag = h.startsWith('#') ? h : `#${h}`;
      hashtagMap[tag] = (hashtagMap[tag] || 0) + 1;
    });
  });
  const topHashtags = Object.entries(hashtagMap).sort((a, b) => b[1] - a[1]).slice(0, 15);

  if (loading && !analytics) {
    return <div className="campaign-analytics-loading">Loading analytics...</div>;
  }

  return (
    <div className="campaign-analytics-container">
      <h2>Campaign Analytics</h2>
      {error && <div className="campaign-analytics-error">{error}</div>}

      {/* Summary cards */}
      <div className="campaign-analytics-cards">
        <div className="analytics-card">
          <span className="analytics-card-value">{campaigns.length}</span>
          <span className="analytics-card-label">Total Campaigns</span>
        </div>
        <div className="analytics-card">
          <span className="analytics-card-value">{totalPosts}</span>
          <span className="analytics-card-label">Total Posts</span>
        </div>
        <div className="analytics-card">
          <span className="analytics-card-value">{avgPosts}</span>
          <span className="analytics-card-label">Avg Posts/Campaign</span>
        </div>
      </div>

      {/* Theme distribution */}
      {themes.length > 0 && (
        <div className="campaign-analytics-section">
          <h3>Theme Distribution</h3>
          <div className="analytics-bar-chart">
            {themes.map(([theme, count]) => (
              <div key={theme} className="analytics-bar-row">
                <span className="analytics-bar-label">{theme}</span>
                <div className="analytics-bar-track">
                  <div className="analytics-bar-fill"
                    style={{ width: `${(count / maxThemeCount) * 100}%` }} />
                </div>
                <span className="analytics-bar-value">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tone distribution */}
      {tones.length > 0 && (
        <div className="campaign-analytics-section">
          <h3>Tone Distribution</h3>
          <div className="analytics-tone-grid">
            {tones.map(([tone, count]) => (
              <div key={tone} className="analytics-tone-item">
                <span className="analytics-tone-label">{tone}</span>
                <span className="analytics-tone-count">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top hashtags */}
      {topHashtags.length > 0 && (
        <div className="campaign-analytics-section">
          <h3>Top Hashtags</h3>
          <div className="analytics-hashtag-list">
            {topHashtags.map(([tag, count]) => (
              <span key={tag} className="analytics-hashtag">{tag} ({count})</span>
            ))}
          </div>
        </div>
      )}

      {/* Comparison table */}
      {campaigns.length > 0 && (
        <div className="campaign-analytics-section">
          <h3>Campaign Comparison</h3>
          <div className="analytics-table-wrap">
            <table className="analytics-table">
              <thead>
                <tr>
                  <th>Theme</th>
                  <th>Audience</th>
                  <th>Tone</th>
                  <th>Posts</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map(c => (
                  <tr key={c.id}>
                    <td>{c.theme || 'N/A'}</td>
                    <td>{c.audience || 'N/A'}</td>
                    <td>{c.tone || 'N/A'}</td>
                    <td>{c.post_count || 0}</td>
                    <td><span className={`analytics-status analytics-status-${c.status}`}>{c.status || 'draft'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {campaigns.length === 0 && !loading && (
        <div className="campaign-analytics-empty">
          <p>No campaigns found. Create campaigns to see analytics here.</p>
        </div>
      )}
    </div>
  );
}

export default CampaignAnalytics;
