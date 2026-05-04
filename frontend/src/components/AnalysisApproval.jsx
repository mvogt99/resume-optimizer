import React from 'react';
import '../styles/ProjectAnalyzer.css';

function AnalysisApproval({ clientName, techCount, govCount, roleCount, onApprove, onCancel }) {
  return (
    <div className="proj-approval-overlay" onClick={onCancel}>
      <div className="proj-approval-dialog" onClick={e => e.stopPropagation()}>
        <h3>Approve & Store in Knowledge Graph</h3>
        <p>
          This will write the analysis for <strong>{clientName}</strong> to ArangoDB.
        </p>
        <div className="text-left text-lg text-secondary mb-24">
          <div className="mb-4">
            <strong>{techCount}</strong> technologies
          </div>
          <div className="mb-4">
            <strong>{govCount}</strong> governance controls
          </div>
          <div>
            <strong>{roleCount}</strong> role contributions
          </div>
        </div>
        <div className="proj-approval-actions">
          <button className="proj-btn proj-btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="proj-btn proj-btn-success" onClick={onApprove}>
            Approve & Store
          </button>
        </div>
      </div>
    </div>
  );
}

export default AnalysisApproval;
