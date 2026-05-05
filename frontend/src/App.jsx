import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import AdminPage from './components/AdminPage';
import ChatWidget from './components/ChatWidget';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);

  useEffect(() => {
    const userId = localStorage.getItem('user_id');
    const token = localStorage.getItem('auth_token');
    const role = localStorage.getItem('user_role');
    if (userId && token) {
      setIsAuthenticated(true);
      setUser({ id: userId, role: role || 'user' });
    }
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
