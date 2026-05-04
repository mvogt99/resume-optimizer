import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import PostEditor from './PostEditor';
import CampaignTimeline from './CampaignTimeline';

const STATUS_OPTIONS = ['draft', 'ready', 'in-progress', 'complete'];

function CampaignCanvas({ campaignId, onBack, onNavigateToSource }) {
  const [campaign, setCampaign] = useState(null);
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [editingPost, setEditingPost] = useState(null);
  const [dragIdx, setDragIdx] = useState(null);
  const [dragOverIdx, setDragOverIdx] = useState(null);
  const [showTimeline, setShowTimeline] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [cRes, pRes] = await Promise.all([
        api.getCampaign(campaignId),
        api.listCampaignPosts(campaignId),
      ]);
      setCampaign(cRes);
      setPosts(pRes.posts || []);
    } catch (err) {
      console.error('Failed to load campaign:', err);
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll job status while generating
  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      try {
        const job = await api.getJobStatus(jobId);
        if (job.status === 'completed' || job.status === 'failed') {
          setGenerating(false);
          setJobId(null);
          loadData();
        }
      } catch (err) {
        // ignore polling errors
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [jobId, loadData]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await api.generateCampaignPosts(campaignId);
      setJobId(res.job_id);
    } catch (err) {
      setGenerating(false);
      alert('Failed to start post generation.');
    }
  };

  const handleStatusChange = async (newStatus) => {
    try {
      await api.updateCampaign(campaignId, { status: newStatus });
      setCampaign(prev => ({ ...prev, status: newStatus }));
    } catch (err) {
      alert('Failed to update status.');
    }
  };

  const handleSavePost = async (postId, updates) => {
    await api.updateCampaignPost(campaignId, postId, updates);
    await loadData();
  };

  const handleRegeneratePost = async (postId, feedback) => {
    const result = await api.regenerateCampaignPost(campaignId, postId, feedback);
    await loadData();
    return result;
  };

  const handleDeletePost = async (postId) => {
    if (!window.confirm('Delete this post?')) return;
    try {
      await api.deleteCampaignPost(campaignId, postId);
      setPosts(prev => prev.filter(p => p.id !== postId));
    } catch (err) {
      alert('Failed to delete post.');
    }
  };

  const handleExport = async () => {
    try {
      const res = await api.exportCampaign(campaignId);
      // Copy to clipboard
      await navigator.clipboard.writeText(res.text);
      alert(`Copied ${res.post_count} posts to clipboard!`);
    } catch (err) {
      alert('Failed to export. Check browser clipboard permissions.');
    }
  };

  // Drag and drop
  const handleDragStart = (idx) => {
    setDragIdx(idx);
  };

  const handleDragOver = (e, idx) => {
    e.preventDefault();
    setDragOverIdx(idx);
  };

  const handleDrop = async (idx) => {
    if (dragIdx === null || dragIdx === idx) {
      setDragIdx(null);
      setDragOverIdx(null);
      return;
    }

    const newPosts = [...posts];
    const [moved] = newPosts.splice(dragIdx, 1);
    newPosts.splice(idx, 0, moved);
    setPosts(newPosts);
    setDragIdx(null);
    setDragOverIdx(null);

    try {
      await api.reorderCampaignPosts(campaignId, newPosts.map(p => p.id));
    } catch (err) {
      // Revert on failure
      loadData();
    }
  };

  if (loading) {
    return <div className="campaign-loading">Loading campaign...</div>;
  }

  if (!campaign) {
    return <div className="campaign-error">Campaign not found.</div>;
  }

  const hasContent = posts.some(p => p.content && p.status !== 'stub');

  return (
    <div className="campaign-canvas">
      {/* Header */}
      <div className="campaign-canvas-header">
        <button className="btn-back" onClick={onBack}>&larr; Back</button>
        <div className="campaign-canvas-title">
          <h2>{campaign.theme || 'Untitled Campaign'}</h2>
          <div className="campaign-canvas-meta">
            <span>Audience: {campaign.audience || 'N/A'}</span>
            <span>Tone: {campaign.tone || 'N/A'}</span>
          </div>
        </div>
        <div className="campaign-canvas-actions">
          <select
            value={campaign.status}
            onChange={e => handleStatusChange(e.target.value)}
            className="campaign-status-select"
          >
            {STATUS_OPTIONS.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <button
            className="btn-generate"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? 'Generating...' : 'Generate Posts'}
          </button>
          {hasContent && (
            <button className="btn-export" onClick={handleExport}>
              Export All
            </button>
          )}
          {posts.length > 0 && (
            <button
              className={`btn-timeline ${showTimeline ? 'active' : ''}`}
              onClick={() => setShowTimeline(v => !v)}
            >
              {showTimeline ? 'Hide Timeline' : 'Timeline'}
            </button>
          )}
        </div>
      </div>

      {/* Timeline View */}
      {showTimeline && posts.length > 0 && campaign && (
        <CampaignTimeline
          posts={posts}
          campaign={campaign}
          onSelectPost={(postId) => {
            const post = posts.find(p => p.id === postId);
            if (post) setEditingPost(post);
          }}
        />
      )}

      {generating && (
        <div className="campaign-generating-banner">
          Generating post drafts... This may take a few minutes.
        </div>
      )}

      {/* Post Cards */}
      <div className="campaign-post-grid">
        {posts.length === 0 && !generating && (
          <div className="campaign-no-posts">
            <p>No posts yet. Click "Generate Posts" to create drafts from your campaign plan.</p>
          </div>
        )}

        {posts.map((post, idx) => (
          <div
            key={post.id}
            className={`campaign-post-card ${
              dragOverIdx === idx ? 'drag-over' : ''
            } ${post.status === 'stub' ? 'post-stub' : ''}`}
            draggable
            onDragStart={() => handleDragStart(idx)}
            onDragOver={(e) => handleDragOver(e, idx)}
            onDrop={() => handleDrop(idx)}
            onDragEnd={() => { setDragIdx(null); setDragOverIdx(null); }}
          >
            <div className="post-card-header">
              <span className="post-position">{idx + 1}</span>
              <h4 className="post-title">{post.title || `Post ${idx + 1}`}</h4>
              <span className={`post-status post-status-${post.status}`}>
                {post.status}
              </span>
            </div>

            <div className="post-card-content">
              {post.content ? (
                <p>{post.content.substring(0, 200)}{post.content.length > 200 ? '...' : ''}</p>
              ) : (
                <p className="post-placeholder">No content yet</p>
              )}
            </div>

            {post.hashtags && (
              <div className="post-card-hashtags">{post.hashtags}</div>
            )}

            <div className="post-card-footer">
              {post.char_count > 0 && (
                <span className="post-char-count">{post.char_count} chars</span>
              )}
              <div className="post-card-actions">
                <button
                  className="btn-edit-post"
                  onClick={() => setEditingPost(post)}
                >
                  Edit
                </button>
                <button
                  className="btn-delete-post"
                  onClick={() => handleDeletePost(post.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Post Editor Modal */}
      {editingPost && (
        <PostEditor
          post={editingPost}
          campaignId={campaignId}
          onSave={handleSavePost}
          onRegenerate={handleRegeneratePost}
          onClose={() => { setEditingPost(null); loadData(); }}
          onNavigateToSource={onNavigateToSource}
        />
      )}
    </div>
  );
}

export default CampaignCanvas;
