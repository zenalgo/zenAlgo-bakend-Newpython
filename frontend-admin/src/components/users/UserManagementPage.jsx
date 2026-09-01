import React, { useState, useEffect } from 'react';
import { Users, UserCheck, UserX, Shield, Plus } from 'lucide-react';
import { usersApi } from '../../api/usersApi';
import { useToast } from '../../context/ToastContext';

export const UserManagementPage = () => {
  const { addToast } = useToast();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadUsers = async () => {
    try {
      const res = await usersApi.getUsers();
      setUsers(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleToggleStatus = async (userId, currentActive) => {
    try {
      await usersApi.updateUserStatus(userId, !currentActive);
      addToast(`User #${userId} status updated!`, 'success');
      loadUsers();
    } catch (err) {
      addToast(err.message || 'Status update failed', 'error');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>User Directory & Permissions</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Manage subscribers, administrators, role permissions, and active statuses.</p>
      </div>

      <div className="glass-panel" style={{ padding: '24px' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>User ID</th>
                <th>Email Address</th>
                <th>Role</th>
                <th>Referral Code</th>
                <th>Account Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    Loading platform users...
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>#{u.id}</td>
                    <td style={{ fontWeight: 600 }}>{u.email}</td>
                    <td>
                      <span className="badge" style={{
                        background: u.role === 'SUPER_ADMIN' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(56, 189, 248, 0.15)',
                        color: u.role === 'SUPER_ADMIN' ? 'var(--accent-purple)' : 'var(--accent-cyan)',
                      }}>
                        {u.role}
                      </span>
                    </td>
                    <td className="font-mono" style={{ color: 'var(--text-dim)' }}>{u.referralCode || 'REF-STD'}</td>
                    <td>
                      <span className={`badge ${u.isActive ? 'badge-running' : 'badge-failed'}`}>
                        {u.isActive ? 'ACTIVE' : 'SUSPENDED'}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={() => handleToggleStatus(u.id, u.isActive)}
                        className={`btn ${u.isActive ? 'btn-danger' : 'btn-emerald'}`}
                        style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                      >
                        {u.isActive ? <UserX size={12} /> : <UserCheck size={12} />}
                        <span>{u.isActive ? 'Deactivate' : 'Activate'}</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default UserManagementPage;
