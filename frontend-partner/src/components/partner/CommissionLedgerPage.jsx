import React, { useState, useEffect } from 'react';
import { DollarSign, RefreshCw, Filter, ArrowDownRight, CheckCircle2, Clock } from 'lucide-react';
import { partnerApi } from '../../api/partnerApi';
import { Pagination } from '../common/Pagination';
import { useToast } from '../../context/ToastContext';

export const CommissionLedgerPage = () => {
  const { addToast } = useToast();
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState('ALL');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  const loadCommissions = async () => {
    setLoading(true);
    try {
      const res = await partnerApi.getCommissions({ page, size: pageSize });
      setCommissions(res.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load commission ledger', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCommissions();
  }, [page, pageSize]);

  const displayedCommissions = filterType === 'ALL'
    ? commissions
    : commissions.filter((c) => c.eventType === filterType);

  const totalFiltered = displayedCommissions.reduce((acc, c) => acc + Number(c.amount), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Commission Ledger & Revenue Share</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Real-time breakdown of recurring plan cuts and copy-trading performance fees.
          </p>
        </div>

        <button onClick={loadCommissions} disabled={loading} className="btn btn-secondary">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Ledger</span>
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Filter size={16} color="var(--text-dim)" />
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Event Type:</span>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="input-field"
            style={{ width: '180px', padding: '6px 10px' }}
          >
            <option value="ALL">All Revenue Events</option>
            <option value="PLAN_SUBSCRIPTION">Plan Subscriptions</option>
            <option value="PROFIT_SHARE">Profit Share Cuts</option>
            <option value="RENEWAL">Recurring Renewals</option>
          </select>
        </div>

        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Total Filtered Revenue: <strong style={{ color: 'var(--accent-emerald)', fontSize: '1rem' }}>₹{totalFiltered.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Tx ID</th>
                <th>Client Source</th>
                <th>Revenue Event</th>
                <th>Rev-Share Rate</th>
                <th>Commission Amount</th>
                <th>Description</th>
                <th>Status</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    Loading commission transactions...
                  </td>
                </tr>
              ) : displayedCommissions.length === 0 ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No commission events found for this filter.
                  </td>
                </tr>
              ) : (
                displayedCommissions.map((t) => (
                  <tr key={t.id}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontSize: '0.8rem', fontWeight: 700 }}>
                      #TX-{t.id}
                    </td>
                    <td>
                      <strong style={{ color: '#fff' }}>{t.clientName}</strong>
                      <div className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{t.clientEmail}</div>
                    </td>
                    <td>
                      <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                        {t.eventType}
                      </span>
                    </td>
                    <td style={{ fontWeight: 700, color: 'var(--accent-amber)' }}>
                      {t.commissionRate}%
                    </td>
                    <td>
                      <strong style={{ color: 'var(--accent-emerald)', fontSize: '0.95rem' }}>
                        +₹{Number(t.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </strong>
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '280px' }}>
                      {t.description}
                    </td>
                    <td>
                      <span className={`badge ${t.status === 'CREDITED' ? 'badge-active' : 'badge-pending'}`}>
                        {t.status === 'CREDITED' ? '● CREDITED' : '● CLEARING'}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      {new Date(t.timestamp).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
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
          totalItems={commissions.length}
          onPageChange={(p) => setPage(p)}
          onPageSizeChange={(s) => { setPageSize(s); setPage(0); }}
        />
      </div>
    </div>
  );
};

export default CommissionLedgerPage;
