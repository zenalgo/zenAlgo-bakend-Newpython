import React, { useState, useEffect } from 'react';
import { Users, Search, RefreshCw, Filter, CheckCircle2, TrendingUp, Cpu, Mail, Calendar, DollarSign } from 'lucide-react';
import { partnerApi } from '../../api/partnerApi';
import { Pagination } from '../common/Pagination';
import { useToast } from '../../context/ToastContext';

export const ReferredClientsPage = () => {
  const { addToast } = useToast();
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  const loadClients = async () => {
    setLoading(true);
    try {
      const res = await partnerApi.getReferredClients({ page, size: pageSize, search: search || undefined });
      setClients(res.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load referred clients', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadClients();
  }, [page, pageSize]);

  useEffect(() => {
    const handler = setTimeout(() => {
      setPage(0);
      loadClients();
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Referred Clients & Sub-Fleet</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Inspect client trader accounts, subscription plan status, and strategy execution copies.
          </p>
        </div>

        <button onClick={loadClients} disabled={loading} className="btn btn-secondary">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Clients</span>
        </button>
      </div>

      {/* Search Toolbar */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '260px', maxWidth: '420px' }}>
          <Search size={18} color="var(--text-dim)" />
          <input
            type="text"
            placeholder="Search referred clients by name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-field"
          />
        </div>

        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Total Referred: <strong style={{ color: 'var(--accent-cyan)' }}>{clients.length}</strong> Traders
        </div>
      </div>

      {/* Clients Table */}
      <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Client User</th>
                <th>Email Address</th>
                <th>Registration Date</th>
                <th>Active Plan</th>
                <th>Fleet Copies</th>
                <th>Commission Generated</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    Loading referred client accounts...
                  </td>
                </tr>
              ) : clients.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No referred clients found matching search.
                  </td>
                </tr>
              ) : (
                clients.map((c) => (
                  <tr key={c.userId}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div
                          style={{
                            width: '32px',
                            height: '32px',
                            borderRadius: '50%',
                            background: 'rgba(56, 189, 248, 0.15)',
                            color: 'var(--accent-cyan)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: 700,
                            fontSize: '0.8rem',
                          }}
                        >
                          {c.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <strong style={{ color: '#fff', fontSize: '0.85rem' }}>{c.name}</strong>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>User #{c.userId}</div>
                        </div>
                      </div>
                    </td>
                    <td className="font-mono" style={{ fontSize: '0.8rem' }}>{c.email}</td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {new Date(c.registeredAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                    </td>
                    <td>
                      <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)' }}>
                        {c.planName}
                      </span>
                    </td>
                    <td>
                      <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                        {c.activeStrategyCount} Strategies Active
                      </span>
                    </td>
                    <td>
                      <strong style={{ color: 'var(--accent-emerald)', fontSize: '0.9rem' }}>
                        ₹{Number(c.totalCommissionContributed).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </strong>
                    </td>
                    <td>
                      <span className={`badge ${c.status === 'ACTIVE' ? 'badge-active' : 'badge-inactive'}`}>
                        {c.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="glass-panel" style={{ padding: '12px 24px' }}>
        <Pagination
          currentPage={page}
          pageSize={pageSize}
          totalItems={clients.length >= pageSize ? (page + 2) * pageSize : (page * pageSize) + clients.length}
          onPageChange={(p) => setPage(p)}
          onPageSizeChange={(s) => { setPageSize(s); setPage(0); }}
        />
      </div>
    </div>
  );
};

export default ReferredClientsPage;
