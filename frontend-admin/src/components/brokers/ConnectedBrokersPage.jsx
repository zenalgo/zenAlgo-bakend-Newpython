import React, { useState, useEffect, useCallback } from 'react';
import {
  Link2, RefreshCw, Search, CheckCircle, XCircle, AlertTriangle,
  Clock, Users, Shield, WifiOff, Wifi, Filter, Calendar
} from 'lucide-react';
import { brokerConnectionsApi } from '../../api/executionApi';

const BROKER_COLORS = {
  DHAN: { color: '#38bdf8', bg: 'rgba(56,189,248,0.12)' },
  ZERODHA: { color: '#a78bfa', bg: 'rgba(167,139,250,0.12)' },
  UPSTOX: { color: '#fb923c', bg: 'rgba(251,146,60,0.12)' },
  MOCK: { color: '#6b7280', bg: 'rgba(107,114,128,0.12)' },
};

const STATUS_CONFIG = {
  ACTIVE: { color: '#10b981', bg: 'rgba(16,185,129,0.12)', icon: CheckCircle, label: 'Active' },
  EXPIRED: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', icon: AlertTriangle, label: 'Expired' },
  DISABLED: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', icon: XCircle, label: 'Disabled' },
};

function StatCard({ icon: Icon, label, value, color, sub }) {
  return (
    <div style={{
      padding: '20px 22px', borderRadius: '14px',
      background: 'rgba(255,255,255,0.04)',
      border: `1px solid ${color}30`,
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: -12, right: -12, opacity: 0.06 }}>
        <Icon size={80} color={color} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <div style={{ padding: '7px', borderRadius: '9px', background: `${color}18` }}>
          <Icon size={16} color={color} />
        </div>
        <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
      </div>
      <div style={{ fontSize: '2rem', fontWeight: 800, color }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '0.73rem', color: '#475569', marginTop: '4px' }}>{sub}</div>}
    </div>
  );
}

function BrokerBadge({ brokerCode }) {
  const cfg = BROKER_COLORS[brokerCode] || { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)' };
  return (
    <span style={{
      padding: '3px 10px', borderRadius: '12px',
      background: cfg.bg, color: cfg.color,
      fontSize: '0.75rem', fontWeight: 800, letterSpacing: '0.03em'
    }}>{brokerCode}</span>
  );
}

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || { color: '#6b7280', bg: 'rgba(107,114,128,0.12)', icon: Clock, label: status };
  const Icon = cfg.icon;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      padding: '4px 10px', borderRadius: '20px',
      background: cfg.bg, color: cfg.color,
      fontSize: '0.75rem', fontWeight: 700,
    }}>
      <Icon size={11} />
      {cfg.label}
    </span>
  );
}

function TodayBadge({ isConnectedToday }) {
  return isConnectedToday ? (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: '#10b981', fontWeight: 700 }}>
      <Wifi size={11} /> Today
    </span>
  ) : (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: '#475569' }}>
      <WifiOff size={11} /> —
    </span>
  );
}

function formatExpiry(dt) {
  if (!dt) return '—';
  const d = new Date(dt);
  const now = new Date();
  const diff = d - now;
  if (diff < 0) return <span style={{ color: '#ef4444', fontWeight: 700 }}>Expired</span>;
  const hrs = Math.floor(diff / 3600000);
  if (hrs < 24) return <span style={{ color: '#f59e0b', fontWeight: 700 }}>{hrs}h left</span>;
  return <span style={{ color: '#10b981' }}>{d.toLocaleDateString('en-IN')}</span>;
}

export const ConnectedBrokersPage = () => {
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filterBroker, setFilterBroker] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [page, setPage] = useState(0);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [usersRes, statsRes] = await Promise.all([
        brokerConnectionsApi.listConnectedUsers({
          page, size: 50,
          ...(search && { search }),
          ...(filterBroker && { brokerCode: filterBroker }),
          ...(filterStatus && { status: filterStatus }),
        }),
        brokerConnectionsApi.getStats(),
      ]);
      setUsers(usersRes.data?.data || []);
      setStats(statsRes.data?.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [page, search, filterBroker, filterStatus]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSearchChange = (e) => { setSearch(e.target.value); setPage(0); };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px' }}>
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '10px', margin: 0 }}>
            <Link2 size={26} color="#a78bfa" /> Connected Broker Accounts
          </h1>
          <p style={{ color: '#64748b', fontSize: '0.875rem', marginTop: '4px' }}>All users and their broker connection status, token expiry, and daily activity</p>
        </div>
        <button onClick={fetchData} disabled={loading} style={{
          display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 18px',
          background: 'rgba(167,139,250,0.12)', border: '1px solid rgba(167,139,250,0.3)',
          color: '#a78bfa', borderRadius: '9px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600,
        }}>
          <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '14px', marginBottom: '28px' }}>
          <StatCard icon={Users} label="Total Accounts" value={stats.totalAccounts} color="#94a3b8" />
          <StatCard icon={Shield} label="Active" value={stats.activeAccounts} color="#10b981" sub="Valid tokens" />
          <StatCard icon={Wifi} label="Connected Today" value={stats.connectedToday} color="#38bdf8" sub={new Date().toLocaleDateString('en-IN')} />
          <StatCard icon={AlertTriangle} label="Expired Tokens" value={stats.expiredTokens} color="#f59e0b" sub="Need re-auth" />
          <StatCard icon={XCircle} label="Disabled" value={stats.disabledAccounts} color="#ef4444" sub="Blocked" />
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '9px 14px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '9px', flex: 1, maxWidth: '280px' }}>
          <Search size={14} color="#64748b" />
          <input
            value={search}
            onChange={handleSearchChange}
            placeholder="Search by email or client ID…"
            style={{ background: 'transparent', border: 'none', outline: 'none', color: '#e2e8f0', fontSize: '0.82rem', width: '100%' }}
          />
        </div>

        <select value={filterBroker} onChange={e => { setFilterBroker(e.target.value); setPage(0); }}
          style={{ padding: '9px 14px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '9px', color: filterBroker ? '#e2e8f0' : '#64748b', fontSize: '0.82rem', cursor: 'pointer' }}>
          <option value="">All Brokers</option>
          <option value="DHAN">Dhan</option>
          <option value="ZERODHA">Zerodha</option>
          <option value="MOCK">Mock</option>
        </select>

        <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setPage(0); }}
          style={{ padding: '9px 14px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '9px', color: filterStatus ? '#e2e8f0' : '#64748b', fontSize: '0.82rem', cursor: 'pointer' }}>
          <option value="">All Statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="EXPIRED">Expired</option>
          <option value="DISABLED">Disabled</option>
        </select>

        {(search || filterBroker || filterStatus) && (
          <button onClick={() => { setSearch(''); setFilterBroker(''); setFilterStatus(''); setPage(0); }}
            style={{ padding: '9px 14px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444', borderRadius: '9px', fontSize: '0.82rem', cursor: 'pointer' }}>
            Clear
          </button>
        )}

        <div style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#64748b' }}>
          {users.length} account{users.length !== 1 ? 's' : ''} shown
        </div>
      </div>

      {/* Table */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '14px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.2)' }}>
              {['User', 'Email', 'Broker', 'Client ID', 'Status', 'Connected Today', 'Connection Date', 'Token Expiry', 'Last Sync'].map(h => (
                <th key={h} style={{ padding: '14px 16px', textAlign: 'left', fontSize: '0.72rem', color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
                <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', color: '#a78bfa' }} />
                <div style={{ marginTop: '10px' }}>Loading broker accounts…</div>
              </td></tr>
            ) : users.length === 0 ? (
              <tr><td colSpan={9} style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
                <Link2 size={36} style={{ opacity: 0.3, display: 'block', margin: '0 auto 12px' }} />
                No broker accounts found. Users need to connect a broker first.
              </td></tr>
            ) : users.map((u, i) => (
              <tr key={`${u.userId}-${u.brokerCode}`}
                style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.12s' }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <td style={{ padding: '14px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{
                      width: '34px', height: '34px', borderRadius: '50%',
                      background: `hsl(${(u.userId * 47) % 360}, 65%, 20%)`,
                      border: `2px solid hsl(${(u.userId * 47) % 360}, 65%, 45%)`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '0.75rem', fontWeight: 800, color: `hsl(${(u.userId * 47) % 360}, 65%, 75%)`,
                      flexShrink: 0,
                    }}>
                      {(u.userName || 'U')[0].toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#e2e8f0' }}>{u.userName || `User #${u.userId}`}</div>
                      <div style={{ fontSize: '0.7rem', color: '#475569' }}>ID: {u.userId}</div>
                    </div>
                  </div>
                </td>
                <td style={{ padding: '14px 16px', fontSize: '0.8rem', color: '#94a3b8' }}>{u.userEmail}</td>
                <td style={{ padding: '14px 16px' }}><BrokerBadge brokerCode={u.brokerCode} /></td>
                <td style={{ padding: '14px 16px', fontFamily: 'monospace', fontSize: '0.8rem', color: '#a5b4fc' }}>{u.clientId}</td>
                <td style={{ padding: '14px 16px' }}><StatusBadge status={u.status} /></td>
                <td style={{ padding: '14px 16px' }}><TodayBadge isConnectedToday={u.isConnectedToday} /></td>
                <td style={{ padding: '14px 16px', fontSize: '0.78rem', color: '#64748b' }}>{u.connectionDate || '—'}</td>
                <td style={{ padding: '14px 16px', fontSize: '0.78rem' }}>{formatExpiry(u.tokenExpiry)}</td>
                <td style={{ padding: '14px 16px', fontSize: '0.75rem', color: '#475569' }}>
                  {u.lastSyncAt ? new Date(u.lastSyncAt).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginTop: '20px' }}>
        <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0 || loading}
          style={{ padding: '8px 20px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8', cursor: 'pointer', fontSize: '0.82rem', opacity: page === 0 ? 0.4 : 1 }}>
          ← Previous
        </button>
        <button onClick={() => setPage(p => p + 1)} disabled={users.length < 50 || loading}
          style={{ padding: '8px 20px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8', cursor: 'pointer', fontSize: '0.82rem', opacity: users.length < 50 ? 0.4 : 1 }}>
          Next →
        </button>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default ConnectedBrokersPage;
