import React, { useState, useEffect, useRef } from 'react';
import { StatusBadge } from '../common/StatusBadge';
import { Layers, RefreshCw, Users, CheckCircle2, XCircle, Search, Eye, Zap, Info, ArrowRight, ShieldCheck, User, Mail, Award, Filter } from 'lucide-react';
import { executionApi } from '../../api/executionApi';
import { strategyApi } from '../../api/strategyApi';
import UserTraceStepperModal from './UserTraceStepperModal';
import { Pagination } from '../common/Pagination';
import { useToast } from '../../context/ToastContext';

export const BatchAuditingPage = ({ selectedStrategyId }) => {
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [currentStrategyId, setCurrentStrategyId] = useState(selectedStrategyId || '');
  const [batches, setBatches] = useState([]);
  const [selectedBatchId, setSelectedBatchId] = useState(null);
  const [traces, setTraces] = useState([]);
  const [activeTraceId, setActiveTraceId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingTraces, setLoadingTraces] = useState(false);
  const [triggering, setTriggering] = useState(false);

  // Batch Filters & Pagination
  const [batchStatusFilter, setBatchStatusFilter] = useState('ALL');
  const [batchPage, setBatchPage] = useState(0);
  const [batchPageSize, setBatchPageSize] = useState(5);

  // Subscriber Filters & Pagination
  const [subscriberSearch, setSubscriberSearch] = useState('');
  const [subscriberStatusFilter, setSubscriberStatusFilter] = useState('ALL');
  const [subscriberPage, setSubscriberPage] = useState(0);
  const [subscriberPageSize, setSubscriberPageSize] = useState(5);

  const subscriberSectionRef = useRef(null);

  useEffect(() => {
    strategyApi.getStrategies().then((res) => {
      const list = res.data || [];
      setStrategies(list);
      if (!currentStrategyId && list.length > 0) {
        setCurrentStrategyId(list[0].id);
      }
    });
  }, []);

  const loadBatches = async () => {
    if (!currentStrategyId) return;
    setLoading(true);
    try {
      const params = {
        page: batchPage,
        size: batchPageSize,
        status: batchStatusFilter !== 'ALL' ? batchStatusFilter : undefined,
      };
      const res = await executionApi.getStrategyBatches(currentStrategyId, params);
      const bList = res.data || [];
      setBatches(bList);
      if (bList.length > 0) {
        setSelectedBatchId(bList[0].batchId);
      } else {
        setSelectedBatchId(null);
        setTraces([]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentStrategyId) {
      loadBatches();
    }
  }, [currentStrategyId, batchPage, batchPageSize, batchStatusFilter]);

  const loadBatchTraces = async (bId) => {
    if (!bId) return;
    setLoadingTraces(true);
    try {
      const params = {
        page: subscriberPage,
        size: subscriberPageSize,
        status: subscriberStatusFilter !== 'ALL' ? subscriberStatusFilter : undefined,
        search: subscriberSearch || undefined,
      };
      const res = await executionApi.getBatchTraces(bId, params);
      setTraces(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingTraces(false);
    }
  };

  useEffect(() => {
    if (selectedBatchId) {
      loadBatchTraces(selectedBatchId);
    }
  }, [selectedBatchId, subscriberPage, subscriberPageSize, subscriberStatusFilter]);

  useEffect(() => {
    const handler = setTimeout(() => {
      setSubscriberPage(0);
      if (selectedBatchId) loadBatchTraces(selectedBatchId);
    }, 300);
    return () => clearTimeout(handler);
  }, [subscriberSearch]);

  const handleSelectBatch = (bId) => {
    setSelectedBatchId(bId);
    setSubscriberPage(0);
    if (subscriberSectionRef.current) {
      subscriberSectionRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleSimulateTrade = async () => {
    if (!currentStrategyId) return;
    setTriggering(true);
    try {
      await executionApi.simulateExecution(currentStrategyId);
      addToast(`Batch signal and subscriber traces created for Strategy #${currentStrategyId}!`, 'success');
      loadBatches();
    } catch (err) {
      addToast(err.message || 'Simulation failed', 'error');
    } finally {
      setTriggering(false);
    }
  };

  const selectedStrategy = strategies.find((s) => String(s.id) === String(currentStrategyId));

  const filteredTraces = traces.filter((t) => {
    if (!subscriberSearch) return true;
    const s = subscriberSearch.toLowerCase();
    const matchName = (t.userName || '').toLowerCase().includes(s);
    const matchEmail = (t.userEmail || '').toLowerCase().includes(s);
    const matchId = String(t.userId).includes(s);
    return matchName || matchEmail || matchId;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Page Header */}
      <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Copy-Trading Batch Auditing & Subscriber Traces</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Inspect multi-subscriber execution batches, fill ratios, trader identity, and step-by-step audit timelines.
        </p>
      </div>

      {/* Strategy Selector & Live Simulation Banner */}
      <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px', border: '1px solid var(--border-highlight)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: '300px' }}>
            <span style={{ fontWeight: 700, color: 'var(--accent-cyan)', whiteSpace: 'nowrap' }}>Active Strategy Fleet:</span>
            <select
              value={currentStrategyId}
              onChange={(e) => { setCurrentStrategyId(e.target.value); setBatchPage(0); }}
              className="input-field"
              style={{ maxWidth: '420px', fontWeight: 600 }}
            >
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  #{s.id} — {s.name} ({s.underlying || 'NIFTY'}) [{s.mode || 'PAPER'}]
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button onClick={loadBatches} disabled={loading} className="btn btn-secondary">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              <span>Refresh Batches</span>
            </button>
            <button
              onClick={handleSimulateTrade}
              disabled={triggering || !currentStrategyId}
              className="btn btn-emerald"
            >
              <Zap size={14} className={triggering ? 'animate-spin' : ''} />
              <span>{triggering ? 'Generating Batch...' : '⚡ Generate 5m Batch Signal'}</span>
            </button>
          </div>
        </div>

        {/* Selected Strategy Status Card */}
        {selectedStrategy && (
          <div style={{
            background: 'rgba(15, 23, 42, 0.5)',
            borderRadius: '8px',
            padding: '12px 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.875rem',
            border: '1px solid var(--border-subtle)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Underlying Asset:</span>
              <strong style={{ color: '#fff' }}>{selectedStrategy.underlying || 'NIFTY 50'}</strong>
              <span style={{ color: 'var(--text-dim)', margin: '0 6px' }}>•</span>
              <span style={{ color: 'var(--text-muted)' }}>Trading Mode:</span>
              <span className="badge badge-running">{selectedStrategy.mode || 'PAPER'}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <span>Total Batches Today: <strong style={{ color: 'var(--accent-cyan)' }}>{batches.length}</strong></span>
              <span>Subscriber Fill Ratio: <strong style={{ color: 'var(--accent-emerald)' }}>80% - 100%</strong></span>
            </div>
          </div>
        )}
      </div>

      {/* Execution Batches Table */}
      <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>
              1. Execution Signal Batches for Strategy #{currentStrategyId}
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
              Whenever a market candle triggers an entry signal, a batch is created to dispatch copy-orders to all subscribed users.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Filter size={14} color="var(--text-dim)" />
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Status:</span>
            <select
              value={batchStatusFilter}
              onChange={(e) => { setBatchStatusFilter(e.target.value); setBatchPage(0); }}
              className="input-field"
              style={{ width: '150px', padding: '6px 10px' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="PROCESSING">PROCESSING</option>
              <option value="FAILED">FAILED</option>
            </select>
          </div>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Batch ID</th>
                <th>Signal ID</th>
                <th>Trigger Date</th>
                <th>Subscribers</th>
                <th>Eligible</th>
                <th>Fills Succeeded</th>
                <th>Fills Failed</th>
                <th>Batch Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {batches.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No execution batches recorded for Strategy #{currentStrategyId} matching filters.
                    <div style={{ marginTop: '12px' }}>
                      <button onClick={handleSimulateTrade} className="btn btn-emerald" style={{ padding: '8px 18px' }}>
                        <Zap size={14} />
                        <span>Trigger Simulated Batch on Strategy #{currentStrategyId}</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                batches.map((b) => (
                  <tr
                    key={b.batchId}
                    style={{
                      background: selectedBatchId === b.batchId ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                      borderLeft: selectedBatchId === b.batchId ? '3px solid var(--accent-cyan)' : 'none',
                    }}
                  >
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>#{b.batchId}</td>
                    <td className="font-mono">#{b.signalId}</td>
                    <td>{b.tradingDate}</td>
                    <td style={{ fontWeight: 700 }}>{b.totalUsers} users</td>
                    <td style={{ color: 'var(--accent-cyan)' }}>{b.eligibleUsers}</td>
                    <td style={{ color: 'var(--accent-emerald)', fontWeight: 700 }}>{b.successfulUsers}</td>
                    <td style={{ color: b.failedUsers > 0 ? 'var(--accent-rose)' : 'var(--text-muted)' }}>{b.failedUsers}</td>
                    <td><StatusBadge status={b.status} /></td>
                    <td>
                      <button
                        onClick={() => handleSelectBatch(b.batchId)}
                        className={`btn ${selectedBatchId === b.batchId ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                      >
                        <Eye size={14} />
                        <span>Inspect Subscribers ({b.successfulUsers} Fills)</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Batch Pagination */}
        <Pagination
          currentPage={batchPage}
          pageSize={batchPageSize}
          totalItems={batches.length >= batchPageSize ? (batchPage + 2) * batchPageSize : (batchPage * batchPageSize) + batches.length}
          onPageChange={(newPage) => setBatchPage(newPage)}
          onPageSizeChange={(newSize) => { setBatchPageSize(newSize); setBatchPage(0); }}
          pageSizeOptions={[3, 5, 10, 20]}
        />
      </div>

      {/* Selected Batch: Subscriber User Breakdown */}
      <div ref={subscriberSectionRef} className="glass-panel" style={{ padding: '24px', border: '1px solid var(--border-highlight)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>
              2. Subscriber User Audit Breakdown {selectedBatchId ? `(Batch #${selectedBatchId})` : ''}
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
              Full trader identity, role permissions, and step-by-step risk & order placement audit trail.
            </p>
          </div>
          {selectedBatchId && (
            <button onClick={() => loadBatchTraces(selectedBatchId)} disabled={loadingTraces} className="btn btn-secondary">
              <RefreshCw size={14} className={loadingTraces ? 'animate-spin' : ''} />
              <span>Refresh Subscribers</span>
            </button>
          )}
        </div>

        {/* Subscriber Search & Status Filter */}
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '240px', maxWidth: '380px' }}>
            <Search size={18} color="var(--text-dim)" />
            <input
              type="text"
              placeholder="Search subscriber by name, email, or ID..."
              value={subscriberSearch}
              onChange={(e) => setSubscriberSearch(e.target.value)}
              className="input-field"
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Filter size={14} color="var(--text-dim)" />
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Status:</span>
            <select
              value={subscriberStatusFilter}
              onChange={(e) => { setSubscriberStatusFilter(e.target.value); setSubscriberPage(0); }}
              className="input-field"
              style={{ width: '150px', padding: '6px 10px' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="EXECUTED">EXECUTED</option>
              <option value="REJECTED">REJECTED</option>
            </select>
          </div>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Subscriber Trader</th>
                <th>Role & Referral</th>
                <th>Audit Step</th>
                <th>Execution Status</th>
                <th>Risk / Fill Reason</th>
                <th>Audit Stepper Timeline</th>
              </tr>
            </thead>
            <tbody>
              {loadingTraces ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    Loading subscriber traces...
                  </td>
                </tr>
              ) : !selectedBatchId ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    Please select a batch above or click <strong>"Inspect Subscribers"</strong>.
                  </td>
                </tr>
              ) : filteredTraces.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    No subscriber trace records found matching filters.
                  </td>
                </tr>
              ) : (
                filteredTraces.map((t, idx) => {
                  const traceId = t.traceId || t.id || 1448;
                  const isRejected = t.status === 'REJECTED';
                  const roleName = t.userRole || 'TRADER';
                  const refCode = t.referralCode || `REF-U${t.userId}`;
                  const displayName = t.userName || (roleName === 'SUPER_ADMIN' ? 'Super Admin' : `Trader #${t.userId}`);
                  const displayEmail = t.userEmail || `user_${t.userId}@trading.com`;

                  return (
                    <tr key={idx}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div style={{
                            width: '32px',
                            height: '32px',
                            borderRadius: '50%',
                            background: roleName === 'SUPER_ADMIN' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(56, 189, 248, 0.15)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: roleName === 'SUPER_ADMIN' ? 'var(--accent-purple)' : 'var(--accent-cyan)',
                            fontWeight: 700,
                            fontSize: '0.85rem',
                          }}>
                            {displayName.charAt(0)}
                          </div>
                          <div>
                            <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.9rem' }}>{displayName}</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <Mail size={11} />
                              <span>{displayEmail}</span>
                              <span style={{ color: 'var(--text-dim)' }}>• #{t.userId}</span>
                            </div>
                          </div>
                        </div>
                      </td>

                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <span className="badge" style={{
                            background: roleName === 'SUPER_ADMIN' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(16, 185, 129, 0.15)',
                            color: roleName === 'SUPER_ADMIN' ? 'var(--accent-purple)' : 'var(--accent-emerald)',
                            fontSize: '0.7rem',
                            alignSelf: 'flex-start',
                          }}>
                            {roleName}
                          </span>
                          <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                            {refCode}
                          </span>
                        </div>
                      </td>

                      <td className="font-mono" style={{ color: isRejected ? 'var(--accent-rose)' : 'var(--accent-cyan)', fontWeight: 600 }}>
                        {t.currentStep || 'ORDER_PLACEMENT'}
                      </td>

                      <td>
                        <span className={`badge ${!isRejected ? 'badge-running' : 'badge-failed'}`}>
                          {t.status || 'EXECUTED'}
                        </span>
                      </td>

                      <td style={{ color: t.failureReason ? 'var(--accent-rose)' : 'var(--accent-emerald)', fontSize: '0.85rem' }}>
                        {t.failureReason ? `⚠️ ${t.failureReason}` : '✅ All risk limits approved & paper order placed'}
                      </td>

                      <td>
                        <button
                          onClick={() => setActiveTraceId(traceId)}
                          className="btn btn-primary"
                          style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                        >
                          <ShieldCheck size={14} />
                          <span>View 4-Step Timeline</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Subscriber Pagination */}
        <Pagination
          currentPage={subscriberPage}
          pageSize={subscriberPageSize}
          totalItems={filteredTraces.length >= subscriberPageSize ? (subscriberPage + 2) * subscriberPageSize : (subscriberPage * subscriberPageSize) + filteredTraces.length}
          onPageChange={(newPage) => setSubscriberPage(newPage)}
          onPageSizeChange={(newSize) => { setSubscriberPageSize(newSize); setSubscriberPage(0); }}
          pageSizeOptions={[5, 10, 20]}
        />
      </div>

      {/* Vertical Stepper Modal */}
      <UserTraceStepperModal
        isOpen={!!activeTraceId}
        onClose={() => setActiveTraceId(null)}
        traceId={activeTraceId}
      />
    </div>
  );
};

export default BatchAuditingPage;
