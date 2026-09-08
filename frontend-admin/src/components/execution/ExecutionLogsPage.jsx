import React, { useState, useEffect, useCallback } from 'react';
import {
  ScrollText, RefreshCw, Filter, ChevronDown, ChevronRight,
  CheckCircle, XCircle, AlertTriangle, Clock, Users, Zap,
  Search, Calendar, TrendingUp, TrendingDown
} from 'lucide-react';
import { executionApi } from '../../api/executionApi';

const STATUS_CONFIG = {
  COMPLETED: { color: '#10b981', bg: 'rgba(16,185,129,0.1)', icon: CheckCircle, label: 'Completed' },
  COMPLETED_WITH_ERRORS: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', icon: AlertTriangle, label: 'Partial' },
  PROCESSING: { color: '#38bdf8', bg: 'rgba(56,189,248,0.1)', icon: Clock, label: 'Processing' },
  FAILED: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', icon: XCircle, label: 'Failed' },
};

const TRACE_STATUS = {
  EXECUTED: { color: '#10b981', label: 'Executed' },
  FAILED: { color: '#ef4444', label: 'Failed' },
  PENDING: { color: '#f59e0b', label: 'Pending' },
  BROKER_SESSION_INVALID: { color: '#f97316', label: 'Invalid Session' },
  NOT_EXECUTED: { color: '#6b7280', label: 'Not Executed' },
  REJECTED: { color: '#ef4444', label: 'Rejected' },
};

const STEP_COLORS = {
  SUCCESS: '#10b981',
  FAILED: '#ef4444',
  PENDING: '#f59e0b',
};

function StatusChip({ status }) {
  const cfg = STATUS_CONFIG[status] || { color: '#6b7280', bg: 'rgba(107,114,128,0.1)', label: status };
  const Icon = cfg.icon || Clock;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      padding: '3px 10px', borderRadius: '20px',
      background: cfg.bg, color: cfg.color,
      fontSize: '0.75rem', fontWeight: 700,
    }}>
      <Icon size={11} />
      {cfg.label}
    </span>
  );
}

function ProgressBar({ value, total, color }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={{ flex: 1, height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.08)' }}>
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: '3px', background: color, transition: 'width 0.4s ease' }} />
      </div>
      <span style={{ fontSize: '0.72rem', color: color, fontWeight: 700, minWidth: '32px' }}>{pct}%</span>
    </div>
  );
}

function TraceRow({ trace }) {
  const [open, setOpen] = useState(false);
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadDetails = async () => {
    if (details || loading) return;
    setLoading(true);
    try {
      const res = await executionApi.getTraceDetails(trace.traceId);
      setDetails(res.data?.data);
    } catch (e) { /* ignore */ }
    setLoading(false);
  };

  const tc = TRACE_STATUS[trace.status] || { color: '#6b7280', label: trace.status };

  return (
    <>
      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <td style={{ padding: '10px 14px', color: '#94a3b8', fontSize: '0.8rem' }}>#{trace.userId}</td>
        <td style={{ padding: '10px 14px' }}>
          <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#e2e8f0' }}>{trace.userName || `User #${trace.userId}`}</div>
          <div style={{ fontSize: '0.73rem', color: '#64748b' }}>{trace.userEmail}</div>
        </td>
        <td style={{ padding: '10px 14px' }}>
          <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.72rem', fontWeight: 700, background: `${tc.color}18`, color: tc.color }}>
            {tc.label}
          </span>
        </td>
        <td style={{ padding: '10px 14px', fontSize: '0.78rem', color: '#94a3b8', fontFamily: 'monospace' }}>
          {trace.failureCode || '—'}
        </td>
        <td style={{ padding: '10px 14px', fontSize: '0.78rem', color: '#64748b', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {trace.failureReason || '—'}
        </td>
        <td style={{ padding: '10px 14px', textAlign: 'center' }}>
          <button
            onClick={() => { setOpen(o => !o); if (!open) loadDetails(); }}
            style={{ background: 'rgba(56,189,248,0.1)', border: '1px solid rgba(56,189,248,0.25)', borderRadius: '6px', color: '#38bdf8', padding: '4px 10px', fontSize: '0.75rem', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          >
            {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            {open ? 'Hide' : 'Steps'}
          </button>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={6} style={{ padding: '0 14px 14px 40px', background: 'rgba(0,0,0,0.2)' }}>
            {loading ? (
              <div style={{ color: '#64748b', fontSize: '0.8rem', padding: '12px 0' }}>Loading timeline…</div>
            ) : details?.timeline?.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', paddingTop: '10px' }}>
                {details.timeline.map((ev, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: STEP_COLORS[ev.status] || '#6b7280', marginTop: '5px', flexShrink: 0 }} />
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#e2e8f0' }}>{ev.step}</span>
                        <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '8px', background: `${STEP_COLORS[ev.status] || '#6b7280'}22`, color: STEP_COLORS[ev.status] || '#6b7280' }}>{ev.status}</span>
                      </div>
                      {ev.message && <div style={{ fontSize: '0.73rem', color: '#64748b', marginTop: '2px' }}>{ev.message}</div>}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: '#64748b', fontSize: '0.8rem', padding: '12px 0' }}>No step events recorded.</div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function BatchRow({ batch, strategies }) {
  const [expanded, setExpanded] = useState(false);
  const [traces, setTraces] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadTraces = async () => {
    if (traces || loading) return;
    setLoading(true);
    try {
      const res = await executionApi.getBatchTraces(batch.batchId, { size: 100 });
      setTraces(res.data?.data || []);
    } catch (e) { setTraces([]); }
    setLoading(false);
  };

  const cfg = STATUS_CONFIG[batch.status] || { color: '#6b7280', bg: 'rgba(107,114,128,0.1)' };
  const stratName = strategies[batch.strategyId] || `Strategy #${batch.strategyId}`;

  return (
    <>
      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', cursor: 'pointer', transition: 'background 0.15s' }}
        onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
      >
        <td style={{ padding: '14px 16px', color: '#64748b', fontSize: '0.8rem' }}>#{batch.batchId}</td>
        <td style={{ padding: '14px 16px' }}>
          <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#e2e8f0' }}>{stratName}</div>
          <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Signal #{batch.signalId}</div>
        </td>
        <td style={{ padding: '14px 16px', fontSize: '0.82rem', color: '#94a3b8' }}>{batch.tradingDate}</td>
        <td style={{ padding: '14px 16px', textAlign: 'center', fontSize: '0.85rem', fontWeight: 700, color: '#94a3b8' }}>{batch.totalUsers}</td>
        <td style={{ padding: '14px 16px', minWidth: '160px' }}>
          <div style={{ fontSize: '0.72rem', color: '#10b981', marginBottom: '3px' }}>✓ {batch.successfulUsers} Success</div>
          <ProgressBar value={batch.successfulUsers} total={batch.totalUsers} color="#10b981" />
          <div style={{ fontSize: '0.72rem', color: '#ef4444', marginTop: '4px', marginBottom: '3px' }}>✗ {batch.failedUsers} Failed</div>
          <ProgressBar value={batch.failedUsers} total={batch.totalUsers} color="#ef4444" />
        </td>
        <td style={{ padding: '14px 16px' }}>
          <StatusChip status={batch.status} />
        </td>
        <td style={{ padding: '14px 16px', fontSize: '0.75rem', color: '#475569' }}>
          {batch.createdAt ? new Date(batch.createdAt).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—'}
        </td>
        <td style={{ padding: '14px 16px' }}>
          <button
            onClick={() => { setExpanded(e => !e); if (!expanded) loadTraces(); }}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '5px',
              background: expanded ? 'rgba(56,189,248,0.15)' : 'rgba(255,255,255,0.05)',
              border: `1px solid ${expanded ? 'rgba(56,189,248,0.4)' : 'rgba(255,255,255,0.08)'}`,
              color: expanded ? '#38bdf8' : '#94a3b8',
              borderRadius: '7px', padding: '5px 12px', fontSize: '0.78rem', cursor: 'pointer',
            }}
          >
            {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            User Traces
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={8} style={{ padding: 0, background: 'rgba(0,0,0,0.3)' }}>
            {loading ? (
              <div style={{ padding: '20px', color: '#64748b', fontSize: '0.85rem' }}>Loading user traces…</div>
            ) : traces?.length > 0 ? (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.2)' }}>
                    {['User ID', 'Name / Email', 'Status', 'Failure Code', 'Failure Reason', 'Steps'].map(h => (
                      <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '0.72rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {traces.map(t => <TraceRow key={t.traceId} trace={t} />)}
                </tbody>
              </table>
            ) : (
              <div style={{ padding: '20px', color: '#64748b', fontSize: '0.85rem' }}>No user traces found for this batch.</div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export const ExecutionLogsPage = () => {
  const [logs, setLogs] = useState([]);
  const [strategies, setStrategies] = useState({});
  const [loading, setLoading] = useState(false);
  const [filterDate, setFilterDate] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [page, setPage] = useState(0);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, size: 30 };
      if (filterDate) params.trading_date = filterDate;
      if (filterStatus) params.status = filterStatus;
      const res = await executionApi.getAllExecutionLogs(params);
      const data = res.data?.data || [];
      setLogs(data);

      // Build strategy name map from returned data
      const map = {};
      data.forEach(b => { map[b.strategyId] = `Strategy #${b.strategyId}`; });
      setStrategies(map);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [page, filterDate, filterStatus]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  const totalSuccess = logs.reduce((s, b) => s + b.successfulUsers, 0);
  const totalFailed = logs.reduce((s, b) => s + b.failedUsers, 0);
  const totalUsers = logs.reduce((s, b) => s + b.totalUsers, 0);

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px' }}>
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '10px', margin: 0 }}>
            <ScrollText size={26} color="#38bdf8" /> Execution Logs
          </h1>
          <p style={{ color: '#64748b', fontSize: '0.875rem', marginTop: '4px' }}>Full audit trail — every signal, batch, user order, and failure reason</p>
        </div>
        <button onClick={fetchLogs} disabled={loading} style={{
          display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 18px',
          background: 'rgba(56,189,248,0.12)', border: '1px solid rgba(56,189,248,0.3)',
          color: '#38bdf8', borderRadius: '9px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600,
        }}>
          <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '24px' }}>
        {[
          { label: 'Batches Shown', value: logs.length, icon: Zap, color: '#38bdf8' },
          { label: 'Total Users', value: totalUsers, icon: Users, color: '#a78bfa' },
          { label: 'Successful', value: totalSuccess, icon: TrendingUp, color: '#10b981' },
          { label: 'Failed', value: totalFailed, icon: TrendingDown, color: '#ef4444' },
        ].map(card => (
          <div key={card.label} style={{ padding: '18px 20px', background: 'var(--bg-card, rgba(255,255,255,0.04))', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <card.icon size={16} color={card.color} />
              <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>{card.label}</span>
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: card.color }}>{card.value}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '9px' }}>
          <Calendar size={14} color="#64748b" />
          <input
            type="date"
            value={filterDate}
            onChange={e => { setFilterDate(e.target.value); setPage(0); }}
            style={{ background: 'transparent', border: 'none', outline: 'none', color: '#e2e8f0', fontSize: '0.82rem' }}
          />
        </div>
        <select
          value={filterStatus}
          onChange={e => { setFilterStatus(e.target.value); setPage(0); }}
          style={{ padding: '8px 14px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '9px', color: filterStatus ? '#e2e8f0' : '#64748b', fontSize: '0.82rem', cursor: 'pointer' }}
        >
          <option value="">All Statuses</option>
          <option value="COMPLETED">Completed</option>
          <option value="COMPLETED_WITH_ERRORS">Partial (With Errors)</option>
          <option value="PROCESSING">Processing</option>
        </select>
        {(filterDate || filterStatus) && (
          <button onClick={() => { setFilterDate(''); setFilterStatus(''); setPage(0); }}
            style={{ padding: '8px 14px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444', borderRadius: '9px', fontSize: '0.82rem', cursor: 'pointer' }}>
            Clear Filters
          </button>
        )}
        <div style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#64748b' }}>Page {page + 1}</div>
      </div>

      {/* Table */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '14px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.2)' }}>
              {['Batch ID', 'Strategy', 'Date', 'Users', 'Success / Failure', 'Status', 'Time', 'Traces'].map(h => (
                <th key={h} style={{ padding: '14px 16px', textAlign: 'left', fontSize: '0.72rem', color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                  <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', color: '#38bdf8' }} />
                  <span>Loading execution logs…</span>
                </div>
              </td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan={8} style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
                <ScrollText size={36} style={{ opacity: 0.3, marginBottom: '12px' }} />
                <div>No execution logs found. Trigger a strategy execution to see results here.</div>
              </td></tr>
            ) : (
              logs.map(batch => <BatchRow key={batch.batchId} batch={batch} strategies={strategies} />)
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginTop: '20px' }}>
        <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0 || loading}
          style={{ padding: '8px 20px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8', cursor: 'pointer', fontSize: '0.82rem', opacity: page === 0 ? 0.4 : 1 }}>
          ← Previous
        </button>
        <button onClick={() => setPage(p => p + 1)} disabled={logs.length < 30 || loading}
          style={{ padding: '8px 20px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8', cursor: 'pointer', fontSize: '0.82rem', opacity: logs.length < 30 ? 0.4 : 1 }}>
          Next →
        </button>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default ExecutionLogsPage;
