import React, { useState } from 'react';
import api from '../services/api';

function PasswordReset({ show, onHide, userEmail }) {
  const [email, setEmail] = useState(userEmail || localStorage.getItem('user_email') || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);

  if (!show) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) { setError('Email is required'); return; }
    setLoading(true);
    setError('');
    try {
      await api.forgotPassword(email.trim());
      setSent(true);
    } catch (err) {
      setError(err.response?.data?.error || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onHide}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{maxWidth:420}}>
        <h2>Reset Password</h2>
        {sent ? (
          <>
            <p style={{color:'#22c55e',fontWeight:600}}>✓ Reset link sent!</p>
            <p>If that email address is registered, you'll receive a password reset link shortly. Check your inbox (and spam folder).</p>
            <p style={{fontSize:'0.85rem',color:'#666'}}>The link expires in 15 minutes.</p>
            <button className="btn-primary" style={{width:'100%',marginTop:16}} onClick={onHide}>Close</button>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <p style={{color:'#666',marginBottom:16}}>Enter your email address and we'll send you a link to reset your password.</p>
            {error && <p style={{color:'#ef4444',marginBottom:12}}>{error}</p>}
            <input
              type="email"
              className="modal-input"
              placeholder="Your email address"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoFocus
            />
            <div className="modal-actions">
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? 'Sending…' : 'Send Reset Link'}
              </button>
              <button type="button" className="btn-secondary" onClick={onHide}>Cancel</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default PasswordReset;
