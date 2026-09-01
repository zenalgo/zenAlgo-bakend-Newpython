import React, { useState, useEffect } from 'react';
import { Users, UserCheck, UserX, Shield, Plus, RefreshCw, Search, Filter } from 'lucide-react';
import { usersApi } from '../../api/usersApi';
import { Modal } from '../common/Modal';
import { Pagination } from '../common/Pagination';
import { useToast } from '../../context/ToastContext';

export const UserManagementPage = () => {
  const { addToast } = useToast();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // New User Form State
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [password, setPassword] = useState('pass1234');
  const [role, setRole] = useState('TRADER');
  const [referredByCode, setReferredByCode] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const params = {
        page,
        size: pageSize,
        search: search || undefined,
        role: roleFilter !== 'ALL' ? roleFilter : undefined,
        is_active: statusFilter === 'ACTIVE' ? true : (statusFilter === 'SUSPENDED' ? false : undefined),
      };
      const res = await usersApi.getUsers(params);
      setUsers(res.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to fetch users', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [page, pageSize, roleFilter, statusFilter]);

  // Debounced search trigger
  useEffect(() => {
    const handler = setTimeout(() => {
      setPage(0);
      loadUsers();
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  const handleToggleStatus = async (userId, currentActive) => {
    try {
      await usersApi.updateUserStatus(userId, !currentActive);
      addToast(`User #${userId} status updated to ${!currentActive ? 'ACTIVE' : 'DEACTIVATED'}!`, 'success');
      loadUsers();
    } catch (err) {
      addToast(err.message || 'Status update failed', 'error');
    }
  };

  const handleProvisionUser = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await usersApi.provisionUser({
        email,
        firstName,
        lastName,
        password,
        role,
        referredByCode: referredByCode || null,
      });
      addToast(`User account for ${email} provisioned successfully!`, 'success');
      setIsModalOpen(false);
      setEmail('');
      setFirstName('');
      setLastName('');
      setPassword('pass1234');
      loadUsers();
    } catch (err) {
      addToast(err.message || 'Failed to provision user', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>User Directory & Permissions</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Manage subscribers, administrators, role permissions, and active statuses.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={loadUsers} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button onClick={() => setIsModalOpen(true)} className="btn btn-primary">
            <Plus size={16} />
            <span>Provision User</span>
          </button>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Search & Filter Toolbar */}
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '260px', maxWidth: '450px' }}>
            <Search size={18} color="var(--text-dim)" />
            <input
              type="text"
              placeholder="Search by email, name, or referral code..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field"
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Filter size={14} color="var(--text-dim)" />
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Role:</span>
              <select
                value={roleFilter}
                onChange={(e) => { setRoleFilter(e.target.value); setPage(0); }}
                className="input-field"
                style={{ width: '130px', padding: '6px 10px' }}
              >
                <option value="ALL">All Roles</option>
                <option value="TRADER">TRADER</option>
                <option value="ADMIN">ADMIN</option>
                <option value="SUPER_ADMIN">SUPER_ADMIN</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
                className="input-field"
                style={{ width: '130px', padding: '6px 10px' }}
              >
                <option value="ALL">All Status</option>
                <option value="ACTIVE">ACTIVE</option>
                <option value="SUSPENDED">SUSPENDED</option>
              </select>
            </div>
          </div>
        </div>

        {/* User Table */}
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>User ID</th>
                <th>Trader Identity</th>
                <th>Email Address</th>
                <th>Role</th>
                <th>Referral Code</th>
                <th>Account Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    Loading platform users...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    No users found matching the selected filters.
                  </td>
                </tr>
              ) : (
                users.map((u) => {
                  const isActive = u.isActive !== undefined ? u.isActive : u.is_active;
                  const referral = u.referralCode || u.referral_code || 'REF-STD';
                  const fullName = `${u.firstName || ''} ${u.lastName || ''}`.trim() || (u.role === 'SUPER_ADMIN' ? 'Super Admin' : `Trader #${u.id}`);

                  return (
                    <tr key={u.id}>
                      <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>#{u.id}</td>
                      <td>
                        <div style={{ fontWeight: 700, color: '#fff' }}>{fullName}</div>
                      </td>
                      <td style={{ color: 'var(--text-main)', fontSize: '0.875rem' }}>{u.email}</td>
                      <td>
                        <span className="badge" style={{
                          background: u.role === 'SUPER_ADMIN' ? 'rgba(168, 85, 247, 0.2)' :
                                      u.role === 'ADMIN' ? 'rgba(56, 189, 248, 0.2)' : 'rgba(16, 185, 129, 0.15)',
                          color: u.role === 'SUPER_ADMIN' ? 'var(--accent-purple)' :
                                 u.role === 'ADMIN' ? 'var(--accent-cyan)' : 'var(--accent-emerald)',
                        }}>
                          {u.role}
                        </span>
                      </td>
                      <td className="font-mono" style={{ color: 'var(--text-dim)' }}>{referral}</td>
                      <td>
                        <span className={`badge ${isActive ? 'badge-running' : 'badge-failed'}`}>
                          {isActive ? 'ACTIVE' : 'SUSPENDED'}
                        </span>
                      </td>
                      <td>
                        <button
                          onClick={() => handleToggleStatus(u.id, isActive)}
                          className={`btn ${isActive ? 'btn-danger' : 'btn-emerald'}`}
                          style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                        >
                          {isActive ? <UserX size={12} /> : <UserCheck size={12} />}
                          <span>{isActive ? 'Deactivate' : 'Activate'}</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <Pagination
          currentPage={page}
          pageSize={pageSize}
          totalItems={users.length >= pageSize ? (page + 2) * pageSize : (page * pageSize) + users.length}
          onPageChange={(newPage) => setPage(newPage)}
          onPageSizeChange={(newSize) => { setPageSize(newSize); setPage(0); }}
          pageSizeOptions={[5, 10, 20, 50]}
        />
      </div>

      {/* Provision User Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Provision New User Account">
        <form onSubmit={handleProvisionUser} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>First Name</label>
              <input
                type="text"
                placeholder="First Name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="input-field"
              />
            </div>
            <div>
              <label>Last Name</label>
              <input
                type="text"
                placeholder="Last Name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="input-field"
              />
            </div>
          </div>

          <div>
            <label>Email Address</label>
            <input
              type="email"
              placeholder="user@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
              required
            />
          </div>

          <div>
            <label>Initial Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Account Role</label>
              <select value={role} onChange={(e) => setRole(e.target.value)} className="input-field">
                <option value="TRADER">TRADER (Subscriber)</option>
                <option value="ADMIN">ADMIN</option>
                <option value="SUPER_ADMIN">SUPER_ADMIN</option>
              </select>
            </div>
            <div>
              <label>Referred By (Optional)</label>
              <input
                type="text"
                placeholder="REF-CODE"
                value={referredByCode}
                onChange={(e) => setReferredByCode(e.target.value)}
                className="input-field"
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" onClick={() => setIsModalOpen(false)} className="btn btn-secondary">Cancel</button>
            <button type="submit" disabled={submitting} className="btn btn-primary">
              {submitting ? 'Provisioning...' : 'Create Account'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default UserManagementPage;
