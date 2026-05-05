import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import AdminPage from './components/AdminPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import ChatWidget from './components/ChatWidget';
import './App.css';

function _getRoleFromStorage() {
  const role = localStorage.getItem('user_role');
  if (role && role !== 'undefined' && role !== 'null') return role;
  // Fall back to decoding the JWT so existing sessions work without re-login
  try {
    const token = localStorage.getItem('auth_token');
    if (token) {
      const payload = JSON.parse(atob(token.split('.')[1]));
      if (payload.role) {
        localStorage.setItem('user_role', payload.role);
        return payload.role;
      }
    }
  } catch {}
  return 'user';
}

function App() {
  // Lazy init so auth state is available on the FIRST render (no flash-redirect)
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return !!(localStorage.getItem('user_id') && localStorage.getItem('auth_token'));
  });
  const [user, setUser] = useState(() => {
    const userId = localStorage.getItem('user_id');
    const token  = localStorage.getItem('auth_token');
    if (!userId || !token) return null;
    return {
      id:    userId,
      email: localStorage.getItem('user_email') || '',
      role:  _getRoleFromStorage(),
    };
  });

  // Keep useEffect only to handle the case where another tab logs out
  useEffect(() => {
    const sync = () => {
      const userId = localStorage.getItem('user_id');
      const token  = localStorage.getItem('auth_token');
      if (!userId || !token) { setIsAuthenticated(false); setUser(null); }
    };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, []);

  const handleLogin = (userId, token, email, role = 'user') => {
    localStorage.setItem('user_id', userId);
    if (token) {
      localStorage.setItem('auth_token', token);
    }
    if (email) {
      localStorage.setItem('user_email', email);
    }
    if (role) {
      localStorage.setItem('user_role', role);
    }
    setIsAuthenticated(true);
    setUser({ id: userId, email, role });
  };

  const handleLogout = () => {
    localStorage.removeItem('user_id');
    localStorage.removeItem('auth_token');
    setIsAuthenticated(false);
    setUser(null);
  };

  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="App">
        <Routes>
          <Route
            path="/login"
            element={
              isAuthenticated ?
                <Navigate to="/dashboard" replace /> :
                <Login onLogin={handleLogin} />
            }
          />
          <Route
            path="/dashboard"
            element={
              isAuthenticated ?
                <Dashboard user={user} onLogout={handleLogout} /> :
                <Navigate to="/login" replace />
            }
          />
          <Route
            path="/admin"
            element={
              isAuthenticated && user?.role === 'admin' ?
                <AdminPage /> :
                isAuthenticated ?
                  <Navigate to="/dashboard" replace /> :
                  <Navigate to="/login" replace />
            }
          />
          <Route
            path="/reset-password/:token"
            element={<ResetPasswordPage />}
          />
          <Route
            path="/"
            element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />}
          />
        </Routes>
        {isAuthenticated && <ChatWidget userId={user?.id} />}
      </div>
    </Router>
  );
}

export default App;
