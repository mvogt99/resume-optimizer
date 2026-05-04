import React, { useState } from 'react';
import api from '../services/api';

function PasswordReset({ show, onHide, userEmail }) {
  const [formData, setFormData] = useState({
    email: userEmail || '',
    old_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess(false);

    if (!formData.email || !formData.old_password || !formData.new_password || !formData.confirm_password) {
      setError('All fields are required');
      return;
    }

    if (formData.new_password !== formData.confirm_password) {
      setError('New passwords do not match');
      return;
    }

    if (formData.new_password.length < 8) {
      setError('New password must be at least 8 characters');
      return;
    }

    if (formData.old_password === formData.new_password) {
      setError('New password must be different from old password');
      return;
    }

    setLoading(true);
    try {
      await api.post('/reset-password', {
        email: formData.email,
        old_password: formData.old_password,
        new_password: formData.new_password
      });
      setSuccess(true);
      setFormData({
        email: userEmail || '',
        old_password: '',
        new_password: '',
        confirm_password: ''
      });
      setTimeout(() => {
        onHide();
        setSuccess(false);
      }, 2000);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to reset password');
    } finally {
      setLoading(false);
    }
  };

  if (!show) return null;

  return (
    <div className="password-reset-overlay" onClick={onHide}>
      <div className="password-reset-modal" onClick={e => e.stopPropagation()}>
        <div className="password-reset-header">
          <h3>Reset Password</h3>
          <button className="btn-close" onClick={onHide}>&times;</button>
        </div>

        <div className="password-reset-body">
          {error && <div className="alert alert-error">{error}</div>}
          {success && <div className="alert alert-success">Password reset successfully!</div>}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                disabled
                className="input-disabled"
              />
            </div>

            <div className="form-group">
              <label>Current Password</label>
              <input
                type="password"
                name="old_password"
                placeholder="Enter current password"
                value={formData.old_password}
                onChange={handleChange}
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label>New Password</label>
              <input
                type="password"
                name="new_password"
                placeholder="Enter new password (min 8 chars)"
                value={formData.new_password}
                onChange={handleChange}
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label>Confirm New Password</label>
              <input
                type="password"
                name="confirm_password"
                placeholder="Confirm new password"
                value={formData.confirm_password}
                onChange={handleChange}
                disabled={loading}
              />
            </div>

            <div className="form-actions">
              <button
                type="submit"
                disabled={loading}
                className="btn-primary"
              >
                {loading ? 'Resetting...' : 'Reset Password'}
              </button>
              <button
                type="button"
                onClick={onHide}
                disabled={loading}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default PasswordReset;
