import React, { useState } from 'react';
import PasswordReset from './PasswordReset';
import api from '../services/api';
import '../styles/Login.css';

function Login({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false);
  const [showPasswordReset, setShowPasswordReset] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        if (formData.password !== formData.confirmPassword) {
          setError('Passwords do not match');
          setLoading(false);
          return;
        }
        const regResponse = await api.register(formData.email, formData.password);
        onLogin(regResponse.user_id, regResponse.token, formData.email);
      } else {
        const response = await api.login(formData.email, formData.password);
        onLogin(response.user_id, response.token, formData.email);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Authentication failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>Resume Optimizer</h1>
        <h2>{isRegister ? 'Create Account' : 'Sign In'}</h2>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              placeholder="Enter your email"
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              placeholder="Enter your password"
            />
          </div>

          {isRegister && (
            <div className="form-group">
              <label>Confirm Password</label>
              <input
                type="password"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                required
                placeholder="Confirm your password"
              />
            </div>
          )}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Please wait...' : (isRegister ? 'Register' : 'Login')}
          </button>
        </form>

        <div className="toggle-form">
          {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
          <span onClick={() => setIsRegister(!isRegister)}>
            {isRegister ? 'Sign In' : 'Register'}
          </span>
        </div>

        {!isRegister && (
          <div className="forgot-password-link">
            <span onClick={() => setShowPasswordReset(true)}>Forgot password?</span>
          </div>
        )}
      </div>

      <PasswordReset
        show={showPasswordReset}
        onHide={() => setShowPasswordReset(false)}
        userEmail={formData.email}
      />
    </div>
  );
}

export default Login;
