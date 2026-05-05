import React, { useState, useEffect } from 'react';
import api from '../services/api';
import '../styles/AdminPage.css';

function AdminPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserRole, setNewUserRole] = useState('user');
  const [editingUserId, setEditingUserId] = useState(null);
  const [updatingId, setUpdatingId] = useState(null);

  const currentUserId = parseInt(localStorage.getItem('user_id'), 10);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.adminGetUsers();
      setUsers(data);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load users');
      console.error('Error loading users:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async () => {
    if (!newUserEmail) {
      setError('Email is required');
      return;
    }
    try {
      setError(null);
      await api.adminCreateUser(newUserEmail, newUserRole);
      setNewUserEmail('');
      setNewUserRole('user');
      setShowCreateModal(false);
      await loadUsers();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to create user');
    }
  };

  const handleUpdateUser = async (userId, updates) => {
    if (userId === currentUserId) {
      setError('Cannot modify your own account');
      return;
    }
    try {
      setUpdatingId(userId);
      setError(null);
      await api.adminUpdateUser(userId, updates);
      await loadUsers();
      setEditingUserId(null);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to update user');
    } finally {
      setUpdatingId(null);
    }
  };

  const handleDeleteUser = async (userId) => {
    if (userId === currentUserId) {
      setError('Cannot delete your own account');
      return;
    }
    if (!window.confirm('Are you sure you want to delete this user?')) {
      return;
    }
    try {
      setUpdatingId(userId);
      setError(null);
      await api.adminDeleteUser(userId);
      await loadUsers();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to delete user');
    } finally {
      setUpdatingId(null);
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'active':
        return 'badge-active';
      case 'pending':
        return 'badge-pending';
      case 'disabled':
        return 'badge-disabled';
      default:
        return '';
    }
  };

  if (loading) {
    return <div className="admin-page"><p>Loading users...</p></div>;
  }

  return (
    <div className="admin-page">
      <div className="admin-header-bar">
        <button className="btn-back" onClick={() => window.location.href = '/dashboard'}>← Dashboard</button>
        <h1>User Management</h1>
      </div>

      {error && (
        <div className="error-message">
          <p>{error}</p>
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      <div className="admin-header">
        <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
          Create User
        </button>
      </div>

      {showCreateModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>Create New User</h2>
            <input
              type="email"
              placeholder="Email"
              value={newUserEmail}
              onChange={(e) => setNewUserEmail(e.target.value)}
              className="modal-input"
            />
            <select
              value={newUserRole}
              onChange={(e) => setNewUserRole(e.target.value)}
              className="modal-input"
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            <div className="modal-actions">
              <button className="btn-primary" onClick={handleCreateUser}>
                Create
              </button>
              <button
                className="btn-secondary"
                onClick={() => setShowCreateModal(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="users-table-wrapper">
        <table className="users-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.email}</td>
                <td>
                  {editingUserId === user.id ? (
                    <select
                      value={user.role}
                      onChange={(e) =>
                        handleUpdateUser(user.id, { role: e.target.value })
                      }
                      className="inline-select"
                      disabled={updatingId === user.id || user.id === currentUserId}
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                    </select>
                  ) : (
                    <span>{user.role}</span>
                  )}
                </td>
                <td>
                  <span className={`badge ${getStatusBadgeClass(user.status)}`}>
                    {user.status}
                  </span>
                </td>
                <td>
                  <div className="action-buttons">
                    {user.status === 'pending' && (
                      <button
                        className="btn-approve"
                        onClick={() =>
                          handleUpdateUser(user.id, { status: 'active' })
                        }
                        disabled={updatingId === user.id}
                      >
                        Approve
                      </button>
                    )}
                    {user.status === 'active' && user.id !== currentUserId && (
                      <button
                        className="btn-disable"
                        onClick={() =>
                          handleUpdateUser(user.id, { status: 'disabled' })
                        }
                        disabled={updatingId === user.id}
                      >
                        Disable
                      </button>
                    )}
                    {user.status === 'disabled' && user.id !== currentUserId && (
                      <button
                        className="btn-enable"
                        onClick={() =>
                          handleUpdateUser(user.id, { status: 'active' })
                        }
                        disabled={updatingId === user.id}
                      >
                        Enable
                      </button>
                    )}
                    {user.id !== currentUserId && (
                      <button
                        className="btn-delete"
                        onClick={() => handleDeleteUser(user.id)}
                        disabled={updatingId === user.id}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {users.length === 0 && (
        <p className="no-users">No users found.</p>
      )}
    </div>
  );
}

export default AdminPage;
