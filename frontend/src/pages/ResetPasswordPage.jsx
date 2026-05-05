import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../services/api';

const SYMBOL_RE = /[!@#$%^&*()\-_=+\[\]{};:'",.<>/?\\|`~]/;

function validate(password, confirmPassword, email) {
  const errors = [];
  if (password.length < 8) errors.push('At least 8 characters');
  if (!/[A-Z]/.test(password)) errors.push('At least 1 uppercase letter');
  if (!/[a-z]/.test(password)) errors.push('At least 1 lowercase letter');
  if (!/\d/.test(password)) errors.push('At least 1 number');
  if (!SYMBOL_RE.test(password)) errors.push('At least 1 symbol (!@#$%…)');
  const prefix = (email || '').split('@')[0].toLowerCase();
  if (prefix && prefix.length >= 3 && password.toLowerCase().includes(prefix))
    errors.push('Must not contain your username');
  if (password && confirmPassword && password !== confirmPassword)
    errors.push('Passwords do not match');
  return errors;
}

function StrengthBar({ password, email }) {
  const checks = [
    password.length >= 8,
    /[A-Z]/.test(password),
    /[a-z]/.test(password),
    /\d/.test(password),
    SYMBOL_RE.test(password),
  ];
  const score = checks.filter(Boolean).length;
  const colors = ['#ef4444','#f97316','#eab308','#84cc16','#22c55e'];
  const labels = ['','Weak','Fair','Good','Strong','Very strong'];
  return (
    <div style={{margin:'8px 0'}}>
      <div style={{display:'flex',gap:4,marginBottom:4}}>
        {checks.map((ok,i) => (
          <div key={i} style={{flex:1,height:4,borderRadius:2,
            background: i < score ? colors[score-1] : '#e5e7eb',
            transition:'background 0.3s'}} />
        ))}
      </div>
      {password && <span style={{fontSize:'0.75rem',color: colors[score-1]||'#9ca3af'}}>
        {labels[score]}
      </span>}
    </div>
  );
}

export default function ResetPasswordPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [tokenStatus, setTokenStatus] = useState('checking'); // checking|valid|invalid
  const [userEmail, setUserEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [errors, setErrors] = useState([]);

  useEffect(() => {
    api.validateResetToken(token)
      .then(data => { setTokenStatus('valid'); setUserEmail(data.email || ''); })
      .catch(() => setTokenStatus('invalid'));
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate(password, confirm, userEmail);
    if (errs.length) { setErrors(errs); return; }
    setErrors([]);
    setLoading(true);
    try {
      await api.resetPasswordWithToken(token, password, confirm);
      setDone(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      const msg = err.response?.data?.error || err.response?.data?.errors?.join(', ') || 'Reset failed.';
      setErrors([msg]);
    } finally {
      setLoading(false);
    }
  };

  const containerStyle = {
    minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center',
    background:'#f3f4f6', fontFamily:'sans-serif'
  };
  const cardStyle = {
    background:'white', borderRadius:12, padding:'40px 32px', maxWidth:420, width:'90%',
    boxShadow:'0 10px 25px rgba(0,0,0,0.1)'
  };

  if (tokenStatus === 'checking') return (
    <div style={containerStyle}><div style={cardStyle}><p>Validating link…</p></div></div>
  );

  if (tokenStatus === 'invalid') return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <h2 style={{color:'#ef4444'}}>Link Expired or Invalid</h2>
        <p>This password reset link has expired or already been used.</p>
        <p>Reset links are valid for 15 minutes and can only be used once.</p>
        <button style={{marginTop:16,background:'#3b82f6',color:'white',border:'none',
          padding:'10px 20px',borderRadius:6,cursor:'pointer',fontWeight:600}}
          onClick={() => navigate('/login')}>Back to Login</button>
      </div>
    </div>
  );

  if (done) return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <h2 style={{color:'#22c55e'}}>✓ Password Updated</h2>
        <p>Your password has been changed. Redirecting to login…</p>
      </div>
    </div>
  );

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <h2 style={{marginBottom:8}}>Set New Password</h2>
        {userEmail && <p style={{color:'#6b7280',fontSize:'0.875rem',marginBottom:20}}>For: {userEmail}</p>}

        {errors.length > 0 && (
          <div style={{background:'#fef2f2',border:'1px solid #fca5a5',borderRadius:6,
            padding:'10px 14px',marginBottom:16}}>
            {errors.map((e,i) => <p key={i} style={{color:'#dc2626',margin:'2px 0',fontSize:'0.875rem'}}>• {e}</p>)}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <label style={{display:'block',marginBottom:6,fontWeight:500,fontSize:'0.875rem'}}>New Password</label>
          <div style={{position:'relative',marginBottom:8}}>
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={e => { setPassword(e.target.value); setErrors([]); }}
              style={{width:'100%',padding:'10px 44px 10px 12px',border:'1px solid #d1d5db',
                borderRadius:6,fontSize:'1rem',boxSizing:'border-box'}}
              placeholder="New password"
              autoFocus
            />
            <button type="button" onClick={() => setShowPassword(s => !s)}
              style={{position:'absolute',right:12,top:'50%',transform:'translateY(-50%)',
                background:'none',border:'none',cursor:'pointer',color:'#6b7280',fontSize:'0.85rem'}}>
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>

          <StrengthBar password={password} email={userEmail} />

          <label style={{display:'block',margin:'12px 0 6px',fontWeight:500,fontSize:'0.875rem'}}>Confirm Password</label>
          <input
            type={showPassword ? 'text' : 'password'}
            value={confirm}
            onChange={e => { setConfirm(e.target.value); setErrors([]); }}
            style={{width:'100%',padding:'10px 12px',border:'1px solid #d1d5db',
              borderRadius:6,fontSize:'1rem',boxSizing:'border-box',marginBottom:20}}
            placeholder="Confirm new password"
          />

          <div style={{background:'#f9fafb',borderRadius:6,padding:'10px 14px',marginBottom:20,fontSize:'0.8rem',color:'#6b7280'}}>
            <strong>Requirements:</strong>
            {[
              ['≥8 characters', password.length >= 8],
              ['Uppercase letter', /[A-Z]/.test(password)],
              ['Lowercase letter', /[a-z]/.test(password)],
              ['Number', /\d/.test(password)],
              ['Symbol', SYMBOL_RE.test(password)],
            ].map(([label,met]) => (
              <div key={label} style={{color: met ? '#22c55e' : '#6b7280', marginTop:2}}>
                {met ? '✓' : '○'} {label}
              </div>
            ))}
          </div>

          <button type="submit" disabled={loading}
            style={{width:'100%',background:'#3b82f6',color:'white',border:'none',
              padding:'12px',borderRadius:6,fontSize:'1rem',fontWeight:600,cursor:'pointer'}}>
            {loading ? 'Updating…' : 'Update Password'}
          </button>
        </form>
      </div>
    </div>
  );
}
