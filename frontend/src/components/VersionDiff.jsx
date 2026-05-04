import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

function VersionDiff() {
  const [versions, setVersions] = useState([]);
  const [versionA, setVersionA] = useState('');
  const [versionB, setVersionB] = useState('');
  const [diff, setDiff] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadVersions = useCallback(async () => {
    try {
      const res = await api.getResumeVersions();
      setVersions(res.versions || []);
    } catch (err) {
      setError('Failed to load versions.');
    }
  }, []);

  useEffect(() => { loadVersions(); }, [loadVersions]);

  const computeDiff = (textA, textB) => {
    const linesA = (textA || '').split('\n');
    const linesB = (textB || '').split('\n');
    const maxLen = Math.max(linesA.length, linesB.length);
    const unified = [];
    let added = 0, removed = 0, changed = 0;

    for (let i = 0; i < maxLen; i++) {
      const a = linesA[i];
      const b = linesB[i];
      if (a === b) {
        unified.push({ type: 'same', text: a || '' });
      } else {
        if (a !== undefined && b !== undefined) {
          unified.push({ type: 'removed', text: a });
          unified.push({ type: 'added', text: b });
          changed++;
        } else if (a !== undefined) {
          unified.push({ type: 'removed', text: a });
          removed++;
        } else {
          unified.push({ type: 'added', text: b });
          added++;
        }
      }
    }
    return { unified, stats: { added: added + changed, removed: removed + changed, sections: changed } };
  };

  const handleCompare = async () => {
    if (!versionA || !versionB) return;
    setLoading(true);
    setError(null);
    try {
      const [resA, resB] = await Promise.all([
        api.getResumeVersion(versionA),
        api.getResumeVersion(versionB),
      ]);
      const result = computeDiff(resA.parsed_text || '', resB.parsed_text || '');
      setDiff({ ...result, textA: resA.parsed_text || '', textB: resB.parsed_text || '', nameA: resA.source || `v${versionA}`, nameB: resB.source || `v${versionB}` });
    } catch (err) {
      setError('Failed to load version content.');
    } finally {
      setLoading(false);
    }
  };

  const vLabel = (v) => `${v.source || 'Version'} (ID: ${v.id})`;

  return (
    <div className="version-diff-container">
      <h2>Version Comparison</h2>
      {error && <div className="version-diff-error">{error}</div>}

      <div className="version-diff-controls">
        <div className="form-group">
          <label>Version A</label>
          <select value={versionA} onChange={e => setVersionA(e.target.value)}>
            <option value="">Select version...</option>
            {versions.map(v => <option key={v.id} value={v.id}>{vLabel(v)}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Version B</label>
          <select value={versionB} onChange={e => setVersionB(e.target.value)}>
            <option value="">Select version...</option>
            {versions.map(v => <option key={v.id} value={v.id}>{vLabel(v)}</option>)}
          </select>
        </div>
        <button className="btn-primary" onClick={handleCompare}
          disabled={!versionA || !versionB || versionA === versionB || loading}>
          {loading ? 'Comparing...' : 'Compare'}
        </button>
      </div>

      {diff && (
        <>
          <div className="version-diff-stats">
            <span className="diff-stat diff-stat-added">+{diff.stats.added} added</span>
            <span className="diff-stat diff-stat-removed">-{diff.stats.removed} removed</span>
            <span className="diff-stat diff-stat-changed">{diff.stats.sections} sections changed</span>
          </div>

          {/* Unified diff */}
          <div className="version-diff-unified">
            <h3>Unified Diff</h3>
            <div className="diff-lines">
              {diff.unified.map((line, i) => (
                <div key={i} className={`diff-line diff-line-${line.type}`}>
                  <span className="diff-prefix">
                    {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
                  </span>
                  <span className="diff-text">{line.text || '\u00A0'}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Side by side */}
          <div className="version-diff-side-by-side">
            <h3>Side-by-Side Preview</h3>
            <div className="diff-panels">
              <div className="diff-panel">
                <h4>{diff.nameA}</h4>
                <pre className="diff-panel-content">{diff.textA}</pre>
              </div>
              <div className="diff-panel">
                <h4>{diff.nameB}</h4>
                <pre className="diff-panel-content">{diff.textB}</pre>
              </div>
            </div>
          </div>
        </>
      )}

      {!diff && !loading && (
        <div className="version-diff-empty">
          <p>Select two resume versions to compare their content differences.</p>
        </div>
      )}
    </div>
  );
}

export default VersionDiff;
