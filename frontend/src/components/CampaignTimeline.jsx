import React, { useMemo } from 'react';

const STATUS_COLORS = {
  draft: '#999',
  ready: '#4a90d9',
  'in-progress': '#e8a838',
  complete: '#4caf50',
  stub: '#ccc',
};

function cadenceToDays(cadence) {
  if (!cadence) return 7;
  const c = cadence.toLowerCase();
  if (c.includes('daily') || c === '1') return 1;
  if (c.includes('3x') || c.includes('thrice')) return 2.33;
  if (c.includes('biweekly') || c.includes('bi-weekly')) return 14;
  if (c.includes('monthly')) return 30;
  return 7; // default weekly
}

function CampaignTimeline({ posts, campaign, onSelectPost }) {
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const timeline = useMemo(() => {
    if (!posts || posts.length === 0 || !campaign) return [];
    const start = new Date(campaign.created_at || Date.now());
    const interval = cadenceToDays(campaign.cadence);

    return posts.map((post, idx) => {
      let date;
      if (post.scheduled_date) {
        date = new Date(post.scheduled_date);
      } else {
        date = new Date(start);
        date.setDate(start.getDate() + Math.round(idx * interval));
      }
      return { ...post, projected_date: date };
    });
  }, [posts, campaign]);

  if (timeline.length === 0) {
    return <div className="campaign-timeline-empty">No posts to display on timeline.</div>;
  }

  // Calculate date range for positioning
  const minDate = timeline[0].projected_date.getTime();
  const maxDate = timeline[timeline.length - 1].projected_date.getTime();
  const range = maxDate - minDate || 1;
  const todayPct = Math.max(0, Math.min(100, ((today.getTime() - minDate) / range) * 100));
  const showToday = today.getTime() >= minDate && today.getTime() <= maxDate + 86400000;

  const formatDate = (d) =>
    d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  return (
    <div className="campaign-timeline-container">
      <div className="campaign-timeline-header">
        <span className="campaign-timeline-label">Timeline</span>
        <span className="campaign-timeline-cadence">
          {campaign.cadence || 'weekly'} cadence
        </span>
      </div>

      <div className="campaign-timeline-scroll">
        <div className="campaign-timeline-track" style={{ minWidth: Math.max(600, timeline.length * 140) }}>
          {/* Horizontal line */}
          <div className="campaign-timeline-line" />

          {/* Today marker */}
          {showToday && (
            <div
              className="campaign-timeline-today"
              style={{ left: `${todayPct}%` }}
            >
              <div className="campaign-timeline-today-label">Today</div>
              <div className="campaign-timeline-today-line" />
            </div>
          )}

          {/* Post nodes */}
          {timeline.map((post, idx) => {
            const pct = timeline.length === 1
              ? 50
              : ((post.projected_date.getTime() - minDate) / range) * 100;

            return (
              <div
                key={post.id}
                className="campaign-timeline-node"
                style={{ left: `${pct}%` }}
                onClick={() => onSelectPost && onSelectPost(post.id)}
              >
                <div className="campaign-timeline-date-label">
                  {formatDate(post.projected_date)}
                </div>
                <div
                  className="campaign-timeline-dot"
                  style={{ backgroundColor: STATUS_COLORS[post.status] || '#999' }}
                >
                  {idx + 1}
                </div>
                <div className="campaign-timeline-post-info">
                  <div className="campaign-timeline-post-title">
                    {(post.title || `Post ${idx + 1}`).substring(0, 40)}
                    {(post.title || '').length > 40 ? '...' : ''}
                  </div>
                  <div
                    className="campaign-timeline-status-badge"
                    style={{ backgroundColor: STATUS_COLORS[post.status] || '#999' }}
                  >
                    {post.status}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default CampaignTimeline;
