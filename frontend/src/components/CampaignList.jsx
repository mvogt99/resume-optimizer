import React, { useState, useEffect } from 'react';
import api from '../services/api';

const STATUS_COLORS = {
  draft: '#94a3b8',
  ready: '#667eea',
  'in-progress': '#f59e0b',
  complete: '#22c55e',
};

function CampaignList({ onSelectCampaign, onNewCampaign, onDiscover }) {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCampaigns();
  }, []);

  const loadCampaigns = async () => {
    setLoading(true);
    try {
      const res = await api.listCampaigns();
      setCampaigns(res.campaigns || []);
    } catch (err) {
      console.error('Failed to load campaigns:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm('Delete this campaign and all its posts?')) return;
    try {
      await api.deleteCampaign(id);
      setCampaigns(prev => prev.filter(c => c.id !== id));
    } catch (err) {
      alert('Failed to delete campaign.');
    }
  };

  if (loading) {
    return <div className="campaign-loading">Loading campaigns...</div>;
  }

  return (
    <div className="campaign-list">
      <div className="campaign-list-header">
        <h2>Your Campaigns</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          {onDiscover && (
            <button className="btn-discover-trends" onClick={onDiscover} title="Find trending AI topics and get campaign suggestions">
              📡 Discover Trends
            </button>
          )}
          <button className="btn-primary" onClick={onNewCampaign}>
            + New Campaign
          </button>
        </div>
      </div>

      {campaigns.length === 0 ? (
        <div className="campaign-empty">
          <p>No campaigns yet. Start by creating one!</p>
          <button className="btn-primary" onClick={onNewCampaign}>
            Create Your First Campaign
          </button>
        </div>
      ) : (
        <div className="campaign-cards">
          {campaigns.map(c => (
            <div
              key={c.id}
              className="campaign-card"
              onClick={() => onSelectCampaign(c.id)}
            >
              <div className="campaign-card-header">
                <h3>{c.theme || 'Untitled Campaign'}</h3>
                <span
                  className="campaign-status-badge"
                  style={{ backgroundColor: STATUS_COLORS[c.status] || '#94a3b8' }}
                >
                  {c.status}
                </span>
              </div>
              <div className="campaign-card-meta">
                {c.audience && <span className="campaign-meta-item">Audience: {c.audience}</span>}
                {c.tone && <span className="campaign-meta-item">Tone: {c.tone}</span>}
              </div>
              <div className="campaign-card-footer">
                <span className="campaign-post-count">
                  {c.post_count || 0} post{(c.post_count || 0) !== 1 ? 's' : ''}
                </span>
                <button
                  className="btn-delete-campaign"
                  onClick={(e) => handleDelete(e, c.id)}
                  title="Delete campaign"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default CampaignList;
