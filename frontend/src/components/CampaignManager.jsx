import React, { useState } from 'react';
import api from '../services/api';
import CampaignList from './CampaignList';
import CampaignInterview from './CampaignInterview';
import CampaignCanvas from './CampaignCanvas';
import '../styles/Campaign.css';

function DiscoverView({ onUseTheme, onBack }) {
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [articles, setArticles] = useState([]);
  const [error, setError] = useState('');
  const [fetched, setFetched] = useState(false);

  const fetchTrends = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.discoverCampaignTrends();
      setSuggestions(data.suggestions || []);
      setArticles(data.trending_articles || []);
      setFetched(true);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch trending topics');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="campaign-discover">
      <div className="campaign-discover-header">
        <button className="btn-back" onClick={onBack}>← Back</button>
        <h2>Discover Trending AI Topics</h2>
        <button
          className="btn-search"
          onClick={fetchTrends}
          disabled={loading}
          style={{ minWidth: 160 }}
        >
          {loading ? 'Searching…' : fetched ? '↻ Refresh' : 'Search Trending Topics'}
        </button>
      </div>

      {error && (
        <div className="error-banner" style={{ margin: '12px 0' }}>
          {error}
          <button onClick={() => setError('')}>×</button>
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 48, color: '#667' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
          <p>Scanning HackerNews and dev.to for trending AI content…</p>
          <p style={{ fontSize: 13, color: '#999' }}>Synthesizing campaign suggestions with RTX 5090…</p>
        </div>
      )}

      {!loading && fetched && suggestions.length === 0 && (
        <div style={{ textAlign: 'center', padding: 32, color: '#999' }}>
          No suggestions generated. Try refreshing or check if RTX 5090 is available.
        </div>
      )}

      {!loading && suggestions.length > 0 && (
        <>
          <p style={{ color: '#666', marginBottom: 20, fontSize: 14 }}>
            {suggestions.length} campaign ideas based on today's trending AI content — matched to your journey corpus.
          </p>
          <div className="discover-suggestions-grid">
            {suggestions.map((s, i) => (
              <div key={i} className="discover-suggestion-card">
                <div className="discover-card-header">
                  <span className="discover-card-number">#{i + 1}</span>
                  <h3>{s.title}</h3>
                </div>
                <p className="discover-card-theme">{s.theme}</p>
                <p className="discover-card-angle">{s.angle}</p>
                <div className="discover-card-relevance">
                  <span className="discover-relevance-label">Why you?</span>
                  <span>{s.why_relevant}</span>
                </div>
                {s.example_post_hooks && s.example_post_hooks.length > 0 && (
                  <div className="discover-card-hooks">
                    <div className="discover-hooks-label">Opening hooks:</div>
                    {s.example_post_hooks.map((h, j) => (
                      <div key={j} className="discover-hook-line">"{h}"</div>
                    ))}
                  </div>
                )}
                {s.suggested_hashtags && (
                  <div className="discover-card-tags">
                    {s.suggested_hashtags.map((t, j) => (
                      <span key={j} className="discover-tag">{t.startsWith('#') ? t : `#${t}`}</span>
                    ))}
                  </div>
                )}
                <button
                  className="btn-search discover-use-btn"
                  onClick={() => onUseTheme(s.title + ' — ' + s.theme)}
                >
                  Start Campaign Interview →
                </button>
              </div>
            ))}
          </div>

          {articles.length > 0 && (
            <div className="discover-articles-section">
              <h3>Source Articles ({articles.length})</h3>
              <div className="discover-articles-list">
                {articles.slice(0, 15).map((a, i) => (
                  <div key={i} className="discover-article-row">
                    <span className="discover-article-source">{a.source}</span>
                    {a.url ? (
                      <a href={a.url} target="_blank" rel="noopener noreferrer" className="discover-article-title">
                        {a.title}
                      </a>
                    ) : (
                      <span className="discover-article-title">{a.title}</span>
                    )}
                    {a.points > 0 && (
                      <span className="discover-article-points">▲ {a.points}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {!loading && !fetched && (
        <div style={{ textAlign: 'center', padding: 64 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📡</div>
          <p style={{ color: '#555', fontSize: 16, marginBottom: 8 }}>
            Scan today's trending AI content and get personalized campaign ideas.
          </p>
          <p style={{ color: '#999', fontSize: 13 }}>
            Pulls from HackerNews and dev.to, then synthesizes angles that fit your AI journey corpus.
          </p>
        </div>
      )}
    </div>
  );
}

function CampaignManager({ onNavigateToSource }) {
  // State machine: list | interview | canvas | discover
  const [view, setView] = useState('list');
  const [selectedCampaignId, setSelectedCampaignId] = useState(null);
  const [prefilledTheme, setPrefilledTheme] = useState('');

  const handleNewCampaign = () => {
    setPrefilledTheme('');
    setView('interview');
  };

  const handleDiscover = () => {
    setView('discover');
  };

  const handleUseTheme = (theme) => {
    setPrefilledTheme(theme);
    setView('interview');
  };

  const handleSelectCampaign = (campaignId) => {
    setSelectedCampaignId(campaignId);
    setView('canvas');
  };

  const handleCampaignCreated = (campaignId) => {
    setSelectedCampaignId(campaignId);
    setView('canvas');
  };

  const handleBackToList = () => {
    setView('list');
    setSelectedCampaignId(null);
    setPrefilledTheme('');
  };

  if (view === 'discover') {
    return (
      <DiscoverView
        onUseTheme={handleUseTheme}
        onBack={handleBackToList}
      />
    );
  }

  if (view === 'interview') {
    return (
      <CampaignInterview
        initialTheme={prefilledTheme}
        onCampaignCreated={handleCampaignCreated}
        onBack={handleBackToList}
      />
    );
  }

  if (view === 'canvas' && selectedCampaignId) {
    return (
      <CampaignCanvas
        campaignId={selectedCampaignId}
        onBack={handleBackToList}
        onNavigateToSource={onNavigateToSource}
      />
    );
  }

  return (
    <CampaignList
      onSelectCampaign={handleSelectCampaign}
      onNewCampaign={handleNewCampaign}
      onDiscover={handleDiscover}
    />
  );
}

export default CampaignManager;
