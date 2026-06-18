import React from 'react';

const ENV_CONFIG = {
  production: { label: 'PRODUCTION', bg: '#166534', color: '#bbf7d0', border: '#15803d' },
  prod:       { label: 'PRODUCTION', bg: '#166534', color: '#bbf7d0', border: '#15803d' },
  staging:    { label: 'STAGING',    bg: '#92400e', color: '#fde68a', border: '#d97706' },
  aws:        { label: 'AWS TEST',   bg: '#1e3a5f', color: '#bfdbfe', border: '#3b82f6' },
  test:       { label: 'TEST',       bg: '#0f766e', color: '#99f6e4', border: '#14b8a6' },
  local:      { label: 'LOCAL DEV',  bg: '#374151', color: '#e5e7eb', border: '#6b7280' },
  dev:        { label: 'DEV',        bg: '#1e3a5f', color: '#bfdbfe', border: '#3b82f6' },
  unknown:    { label: 'ENV?',       bg: '#374151', color: '#9ca3af', border: '#4b5563' },
};

export default function EnvBadge() {
  // Priority: runtime env.js > VITE build-time env var > Vite dev mode fallback
  const viteEnv = typeof import.meta !== 'undefined' ? import.meta.env?.VITE_CLOUDLIFT_ENV : undefined;
  const viteDev = typeof import.meta !== 'undefined' && import.meta.env?.DEV;
  const rawEnv = (window.CLOUDLIFT_ENV || viteEnv || (viteDev ? 'dev' : 'unknown')).toLowerCase();
  const displayName = window.APP_ENV_NAME || (viteEnv ? viteEnv : (viteDev ? 'Dev (Vite)' : rawEnv));
  const config = ENV_CONFIG[rawEnv] || ENV_CONFIG.unknown;

  // Don't show badge for production to avoid cluttering the prod UI
  // (uncomment the line below to hide in production)
  // if (rawEnv === 'production' || rawEnv === 'prod') return null;

  return (
    <div style={{
      position: 'fixed',
      top: '8px',
      right: '8px',
      zIndex: 9999,
      padding: '3px 10px',
      borderRadius: '4px',
      fontSize: '11px',
      fontWeight: '700',
      letterSpacing: '0.08em',
      fontFamily: 'monospace',
      background: config.bg,
      color: config.color,
      border: `1px solid ${config.border}`,
      boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
      pointerEvents: 'none',
      userSelect: 'none',
    }}>
      {displayName.toUpperCase()}
    </div>
  );
}
