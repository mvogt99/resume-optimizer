import React, { useState, useEffect } from 'react';
import api from '../services/api';

function CorrelationDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const result = await api.getCorrelations();
        setData(result);
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return <div data-testid="correlations-loading" style={{ color: '#888', fontSize: 14 }}>Loading correlation data...</div>;
  }

  if (!data || data.total_applications === 0) {
    return (
      <div data-testid="correlations-empty" className="analytics-panel">
        <h3>Callback Correlations</h3>
        <p style={{ color: '#888', fontSize: 14 }}>
          No feedback data yet. Record application outcomes to see patterns.
        </p>
      </div>
    );
  }

  return (
    <div data-testid="correlations-dashboard" className="analytics-panel">
      <h3>Callback Correlations</h3>
      <div className="analytics-stats">
        <div className="analytics-stat">
          <div className="stat-value" data-testid="callback-rate">{data.callback_rate}%</div>
          <div className="stat-label">Callback Rate</div>
        </div>
        <div className="analytics-stat">
          <div className="stat-value" data-testid="total-applications">{data.total_applications}</div>
          <div className="stat-label">Applications Tracked</div>
        </div>
        {data.avg_ats_callback != null && (
          <div className="analytics-stat">
            <div className="stat-value" data-testid="avg-ats-callback">{Math.round(data.avg_ats_callback)}</div>
            <div className="stat-label">Avg ATS (Callbacks)</div>
          </div>
        )}
        {data.avg_ats_rejected != null && (
          <div className="analytics-stat">
            <div className="stat-value" data-testid="avg-ats-rejected">{Math.round(data.avg_ats_rejected)}</div>
            <div className="stat-label">Avg ATS (Rejected)</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default CorrelationDashboard;
